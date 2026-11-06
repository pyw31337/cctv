#!/bin/bash
# Deploy this checkout to the Oracle proxy host with rsync and restart gunicorn.
#
#   CCTV_ORACLE_KEY=~/.ssh/cctv_oracle ./deploy_to_oracle.sh <오라클_서버_IP>
#
# ~/cctv on the server is also the Flask static root, so nothing secret may be
# copied there: an earlier version of this script uploaded the SSH private key
# itself (oracle_key), which then became publicly downloadable.
set -euo pipefail

if [ -z "${1:-}" ]; then
    echo "사용법: CCTV_ORACLE_KEY=<개인키 경로> ./deploy_to_oracle.sh <오라클_서버_IP>"
    exit 1
fi

ORACLE_IP=$1
KEY_FILE="${CCTV_ORACLE_KEY:-oracle_key}"
if [ ! -f "$KEY_FILE" ]; then
    echo "SSH 개인키를 찾을 수 없습니다: $KEY_FILE (CCTV_ORACLE_KEY로 경로를 지정하세요)"
    exit 1
fi
chmod 600 "$KEY_FILE"

# accept-new trusts a server on first contact but refuses a changed host key,
# instead of silently accepting any key as StrictHostKeyChecking=no did.
SSH_OPTS=(-i "$KEY_FILE" -o StrictHostKeyChecking=accept-new)

echo "=== 오라클 서버 ($ORACLE_IP) 배포 시작 (RSYNC 모드) ==="

# 1. Create the directory and remove secrets earlier deploys left in the web root
ssh "${SSH_OPTS[@]}" ubuntu@"$ORACLE_IP" \
    "mkdir -p ~/cctv && rm -f ~/cctv/oracle_key ~/cctv/oracle_key.pub"

# 2. Sync files, never the key, env files, logs or local scratch output
echo "1. 파일 전송 중..."
rsync -avz -e "ssh ${SSH_OPTS[*]}" \
    --exclude 'venv' \
    --exclude '.venv' \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '.DS_Store' \
    --exclude 'node_modules' \
    --exclude 'oracle_key*' \
    --exclude '.env' \
    --exclude '.env.*' \
    --exclude '*.log' \
    --exclude '*.log.*' \
    --exclude 'logs/' \
    --exclude 'server.pid' \
    --exclude 'debug_html/' \
    --exclude 'artifacts_backup/' \
    --exclude '*.bak' \
    ./ ubuntu@"$ORACLE_IP":~/cctv/

# 3. Setup and Run
echo "2. 서버 설정 및 재시작 중..."
ssh "${SSH_OPTS[@]}" ubuntu@"$ORACLE_IP" << EOF
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

    # Setup venv. Reuse the environment when possible; recreating it on every
    # deploy causes avoidable downtime and makes emergency fixes slower.
    if [ ! -d "venv" ]; then
        echo "Creating venv..."
        python3 -m venv venv || { echo "Venv creation failed"; exit 1; }
    else
        echo "Reusing existing venv..."
    fi

    echo "Activating venv..."
    source venv/bin/activate || { echo "Activation failed"; exit 1; }

    # Install dependencies. The production service is managed by systemd/gunicorn,
    # so keep these packages in the deploy path as well as the fallback Flask path.
    if [ -f "server/requirements.txt" ]; then
        pip install -r server/requirements.txt flask-cors
    else
        pip install flask requests flask-cors gunicorn gevent
    fi

    # Update IP in json
    sed -i "s/YOUR_ORACLE_SERVER_IP/$ORACLE_IP/g" cctv_data.json

    # Restart production service first. Fall back to the simple Flask process only
    # on older hosts that do not have the systemd unit installed yet.
    if systemctl list-unit-files | grep -q '^cctv.service'; then
        sudo systemctl restart cctv
        sudo systemctl --no-pager --full status cctv | tail -40 || true
    else
        pkill -f "python3 server/app.py" || true
        nohup python3 server/app.py > server.log 2>&1 &
    fi

    sleep 3
    if curl -fsS --max-time 10 http://127.0.0.1:8080/health; then
        echo
        echo "=== 배포 완료! (/health 정상) ==="
    else
        echo "!!! /health 응답 없음: sudo journalctl -u cctv -n 50 으로 로그를 확인하세요"
    fi
EOF
