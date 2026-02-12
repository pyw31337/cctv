#!/bin/bash

# Check if IP is provided
if [ -z "$1" ]; then
    echo "사용법: ./deploy_to_oracle.sh <오라클_서버_IP>"
    exit 1
fi

ORACLE_IP=$1
KEY_FILE="oracle_key"
REPO_URL="https://github.com/pyw31337/cctv.git" # Replace with actual repo URL if known, or assume public/private logic.
# Since I don't know the exact git repo URL from context, I'll try to find it or ask user. 
# Wait, the user already uses git. I can check .git/config.
# For now, I will assume the folder might be empty and try to clone.
# Actually, the user's local path is .../cctv. I should check `git remote -v`.

# Let's verify remote first in a separate step? No, let's just use what we know.
# If I can't clone, I'll `rsync` the code up. PROBABLY BETTER TO RSYNC given I have local code.
# Yes, `rsync` is robust and doesn't require git credentials on the server.

chmod 600 "$KEY_FILE"

echo "=== 오라클 서버 ($ORACLE_IP) 배포 시작 (RSYNC 모드) ==="

# 1. Create directory
ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$ORACLE_IP" "mkdir -p ~/cctv"

# 2. Sync files (exclude venv, .git, __pycache__)
echo "1. 파일 전송 중..."
rsync -avz -e "ssh -i $KEY_FILE -o StrictHostKeyChecking=no" \
    --exclude 'venv' \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '.DS_Store' \
    ./ ubuntu@"$ORACLE_IP":~/cctv/

# 3. Setup and Run
echo "2. 서버 설정 및 재시작 중..."
ssh -o StrictHostKeyChecking=no -i "$KEY_FILE" ubuntu@"$ORACLE_IP" << EOF
    cd cctv
    
    # Install Python/Pip if missing
    if ! command -v python3 &> /dev/null; then
        echo "Installing Python..."
        sudo apt update && sudo apt install -y python3-full python3-pip python3-venv ffmpeg
    else
        # If python3 exists, ensure venv is installed
        sudo apt install -y python3-venv
    fi
    
    # Check for ffmpeg (needed for HLS)
    if ! command -v ffmpeg &> /dev/null; then
         echo "Installing FFmpeg..."
         sudo apt update && sudo apt install -y ffmpeg
    fi

    # Setup venv
    if [ -d "venv" ]; then
        echo "Removing existing venv..."
        rm -rf venv
    fi
    
    echo "Creating venv..."
    python3 -m venv venv || { echo "Venv creation failed"; exit 1; }
    
    echo "Activating venv..."
    source venv/bin/activate || { echo "Activation failed"; exit 1; }
    
    # Install dependencies
    pip install flask requests flask-cors
    
    # Update IP in json
    sed -i "s/YOUR_ORACLE_SERVER_IP/$ORACLE_IP/g" cctv_data.json
    
    # Kill old process
    pkill -f "python3 server/app.py"
    
    # Run
    nohup python3 server/app.py > server.log 2>&1 &
    
    echo "=== 배포 완료! ==="
EOF
