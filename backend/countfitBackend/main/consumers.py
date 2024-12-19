import json
from channels.generic.websocket import AsyncWebsocketConsumer
import base64
import os
import sys
import cv2
import numpy as np
import torch
import torch.backends.cudnn as cudnn
import torchvision
import boto3
import argparse
import asyncio

sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(os.path.abspath(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))))))
from AI.demo.get_count import predict_image
from AI.lib.config import cfg, update_config
from AI.lib.models.pose_hrnet import get_pose_net

CTX = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')

def parse_args():
    parser = argparse.ArgumentParser(description='Train keypoints network')
    # parser.add_argument('--cfg', type=str, default='/Users/gwho/Desktop/CountFit/AI/demo/inference-config.yaml')
    parser.add_argument('--cfg', type=str, default='/countfit/AI/demo/inference-config.yaml')
    parser.add_argument('opts', help='Modify config options using the command-line', default=None, nargs=argparse.REMAINDER)
    args = parser.parse_args()
    args.modelDir = ''
    args.logDir = ''
    args.dataDir = ''
    args.prevModelDir = ''
    return args

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.PUSH_UP = 0
        self.PULL_UP = 1
        self.SQUAT = 2
        self.chk = 0
        self.count = 0
        self.exercise_type = self.SQUAT  # 기본값
        self.exercise_finished = False
        

        # 모델 초기화
        cudnn.benchmark = cfg.CUDNN.BENCHMARK
        torch.backends.cudnn.deterministic = cfg.CUDNN.DETERMINISTIC
        torch.backends.cudnn.enabled = cfg.CUDNN.ENABLED

        args = parse_args()
        update_config(cfg, args)

        self.box_model = torchvision.models.detection.fasterrcnn_resnet50_fpn(pretrained=True)
        self.box_model.to(CTX)
        self.box_model.eval()

        self.pose_model = get_pose_net(cfg, is_train=False)

        aws_key = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret = os.getenv('AWS_SECRET_ACCESS_KEY')

        s3 = boto3.client('s3', aws_access_key_id=aws_key, aws_secret_access_key=aws_secret)
        bucket_name = 'pose-hrnet-path'
        file_name = 'pose_hrnet_w32_384x288.pth'
        local_file_path = os.path.join(os.path.dirname(__file__), file_name)

        if not os.path.isfile(local_file_path):
            s3.download_file(bucket_name, file_name, local_file_path)

        if cfg.TEST.MODEL_FILE:
            self.pose_model.load_state_dict(torch.load(local_file_path, map_location=torch.device('cpu')), strict=False)
        else:
            print('expected model defined in config at TEST.MODEL_FILE')

        self.pose_model = torch.nn.DataParallel(self.pose_model, device_ids=cfg.GPUS)
        self.pose_model.to(CTX)
        self.pose_model.eval()

        # 클라이언트에 연결 확인 메시지 전송
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'You are now connected!'
        }))

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)

        # 운동 종료 신호 처리
        if text_data_json['type'] == 'finish_exercise':
            self.exercise_finished = True  # 운동 종료 상태 플래그 설정
            await self.send_final_count()

        # 운동 유형 설정 처리
        elif text_data_json['type'] == 'set_exercise_type':
            exercise = text_data_json['exercise']
            if exercise == 'push_up':
                self.exercise_type = self.PUSH_UP
            elif exercise == 'pull_up':
                self.exercise_type = self.PULL_UP
            elif exercise == 'squat':
                self.exercise_type = self.SQUAT

        elif text_data_json['type'] == 'video_frame':
            if self.exercise_finished:
                # 운동이 종료된 경우 새로운 프레임을 무시합니다.
                return

            if text_data_json['data']:
                frame_data = base64.b64decode(text_data_json['data'])
                np_arr = np.frombuffer(frame_data, np.uint8)
                image_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                # predict_image는 동기 함수로 호출합니다. 
                count_chk, self.chk = predict_image(image_bgr, self.chk, self.exercise_type, self.box_model, self.pose_model)
                if count_chk:
                    self.count += 1
                    await self.send(text_data=json.dumps({
                        'type': 'count_update',
                        'count': self.count
                    }))

    async def send_final_count(self):
        # await asyncio.sleep(0.5)
        await self.send(text_data=json.dumps({
            'type': 'final_count',
            'final_count': self.count
        }))
