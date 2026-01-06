#!/bin/bash

# 1. 프로젝트 폴더로 이동 (경로 확인 필수!)
cd /home/ubuntu/recuit_filter

# 2. 가상환경 켜기
source venv/bin/activate

# 3. 기존 서버 끄기
echo "기존 서버 종료 중..."
pkill -f streamlit || true

# 4. 서버 실행 (로그 남기기 & 백그라운드 실행)
echo "새 서버 실행 중..."
nohup streamlit run app.py --server.headless true --browser.gatherUsageStats false > output.log 2>&1 &

echo "배포 완료!"