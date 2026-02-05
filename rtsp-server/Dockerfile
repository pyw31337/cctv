FROM alpine:3.19

# Install FFmpeg
RUN apk add --no-cache ffmpeg python3 py3-pip bash

# Create app directory
WORKDIR /app

# Copy converter script
COPY convert.py /app/
COPY streams.json /app/

# Run converter
CMD ["python3", "/app/convert.py"]
