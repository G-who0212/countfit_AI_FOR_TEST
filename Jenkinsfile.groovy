pipeline {
    agent any

    stages {
        stage('Clone repository') {
            steps {
                checkout scm
            }
        }

        stage('Build image') {
            steps {
                script {
                    app = docker.build("gwho0212/countfit-ai:${env.BUILD_NUMBER}")
                }
            }
        }

        stage('Push image') {
            steps {
                script {
                    docker.withRegistry('https://registry.hub.docker.com', 'dockerhub') {
                        app.push("${env.BUILD_NUMBER}")
                        app.push("latest")
                    }
                }
            }
        }

        stage('Deploy to EC2') {
            steps {
                sshagent(['countfit-backend-ec2-ssh-key']) {
                    withCredentials([
                        string(credentialsId: 'AWS_ACCESS_KEY_ID', variable: 'AWS_ACCESS_KEY_ID'),
                        string(credentialsId: 'AWS_SECRET_ACCESS_KEY', variable: 'AWS_SECRET_ACCESS_KEY')
                    ]) {
                        sh '''
ssh -o StrictHostKeyChecking=no ubuntu@43.200.245.185 <<EOF
export AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
export AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}

docker pull gwho0212/countfit-ai:latest
docker stop countfit-ai || true
docker rm countfit-ai || true
docker run -d --name countfit-ai -p 8000:8000 gwho0212/countfit-ai:latest
EOF
                        '''
                    }
                }
            }
        }
    }
}
