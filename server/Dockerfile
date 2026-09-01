FROM python:3.11-alpine

# Install FFmpeg
RUN apk add --no-cache ffmpeg

# Install Python deps
WORKDIR /app
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the proxy, shared runtime, and the static assets it serves.
COPY server/app.py .
COPY cctv_runtime.py .
COPY index.html cctv_data.json cctv_data_new.json ./
COPY js ./js
COPY css ./css
COPY data ./data

# Environment
ENV HLS_DIR=/tmp/hls
ENV CCTV_ROOT_DIR=/app
ENV STATIC_ROOT=/app
ENV PYTHONUNBUFFERED=1

# Expose port (Fly.io default is 8080)
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/health || exit 1

# Run Gunicorn
# 1 worker is enough as we offload to FFmpeg
# threads=4 to handle concurrent proxy requests
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--bind", "0.0.0.0:8080", "app:app"]
