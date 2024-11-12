# 베이스 이미지 설정 (Python 3.11.4 버전 사용)
FROM python:3.11.4

# 업데이트 및 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config

# 작업 디렉토리 설정
WORKDIR /countfit

# 의존성 파일 복사 및 설치
COPY requirements.txt /countfit/
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . /countfit/

# 환경 변수 설정 (Django 설정에서 디버그 모드를 비활성화)
ENV DJANGO_ENV=production
ENV PYTHONUNBUFFERED=1

WORKDIR /countfit/backend/countfitBackend

# # 모델에 대한 변경 사항을 감지하고 마이그레이션 파일 생성
# RUN python manage.py makemigrations

# # 생성된 마이그레이션 파일을 데이터베이스에 적용
# RUN python manage.py migrate --noinput

# Collect static files
RUN python manage.py collectstatic --noinput

# 8000 포트 노출 (Django의 기본 포트)
EXPOSE 8000

# Django 애플리케이션 실행 명령어
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
# CMD ["gunicorn", "--bind", "0.0.0.0:8000", "CountfitBackend.wsgi:application"]