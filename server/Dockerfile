FROM python:3.11-alpine

# Install FFmpeg
RUN apk add --no-cache ffmpeg

# Install Python deps
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy App
COPY app.py .

# Environment
ENV HLS_DIR=/tmp/hls
ENV PYTHONUNBUFFERED=1

# Expose port (Fly.io default is 8080)
EXPOSE 8080

# Run Gunicorn
# 1 worker is enough as we offload to FFmpeg
# threads=4 to handle concurrent proxy requests
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--bind", "0.0.0.0:8080", "app:app"]
