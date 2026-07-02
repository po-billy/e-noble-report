#!/bin/bash
# crama.app 서버에 배포하는 스크립트
# 사용법: bash deploy.sh

# 1. 의존성 설치
pip install -r requirements.txt

# 2. 디렉터리 생성
mkdir -p uploads output

# 3. .env 파일이 있는지 확인
if [ ! -f .env ]; then
  echo "ERROR: .env 파일이 없습니다. .env.example을 참고하여 생성하세요."
  exit 1
fi

# 4. 서비스 등록 (systemd)
cat > /etc/systemd/system/ad-report.service << EOF
[Unit]
Description=Ad Report Automation
After=network.target

[Service]
User=ubuntu
WorkingDirectory=$(pwd)
ExecStart=$(which python) -m uvicorn web.app:app --host 0.0.0.0 --port 8000
Restart=always
Environment=PYTHONPATH=$(pwd)

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ad-report
systemctl start ad-report
echo "서비스 등록 완료. systemctl status ad-report 로 확인하세요."
