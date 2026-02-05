# RTSP to HLS Conversion Server

Docker-based server for converting RTSP streams to HLS format.

## Quick Start (Oracle Cloud Free Tier)

1. **Create Oracle Cloud Instance**
   - Shape: VM.Standard.A1.Flex (ARM, FREE)
   - Image: Ubuntu 22.04
   - [Setup Guide](../../.gemini/antigravity/brain/061eb1ff-67f6-48b0-8fb3-3de4b2674066/RTSP_Server_Setup.md)

2. **Deploy**
   ```bash
   # Install Docker
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER
   
   # Clone and start
   git clone https://github.com/pyw31337/cctv.git
   cd cctv/rtsp-server
   docker-compose up -d
   ```

3. **Extract RTSP URLs**
   ```bash
   python3 extract_rtsp.py
   docker-compose restart
   ```

## Files

| File | Description |
|---|---|
| `docker-compose.yml` | Service orchestration |
| `Dockerfile` | FFmpeg container build |
| `nginx.conf` | HLS streaming server |
| `convert.py` | RTSP→HLS conversion manager |
| `streams.json` | Stream configurations |
| `extract_rtsp.py` | Extract RTSP URLs from cctv_data.json |

## Architecture

```
RTSP Sources → [FFmpeg Container] → HLS Segments → [Nginx] → Browser
                                          ↓
                               /streams/{id}/playlist.m3u8
```

## API Endpoints

- `GET /streams/{id}/playlist.m3u8` - HLS stream
- `GET /health` - Health check
- `GET /api/streams` - List all streams

## RTSP URL Patterns

| Kind | Region | RTSP Pattern |
|---|---|---|
| C | 수원 | `rtsp://{ip}:554/live/{id}.stream` |
| y | 여수 | `rtsp://{ip}:554/{id}` |
| J | 울산 | `rtsp://{ip}:554/live/{id}` |
| H | 대구 | `rtsp://{ip}:554/{id}` |
| F | 전주 | `rtsp://{ip}:554/live/{id}` |
| Y | 창원 | `rtsp://{ip}:554/{id}` |

## Cost

- **Oracle Cloud Free Tier**: $0/month (forever free)
- Includes: 4 OCPU, 24GB RAM, 200GB storage, 10TB bandwidth
