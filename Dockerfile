# OfficeEye in a container: the VPS (docker-compose.yml, DEPLOY_VPS.md) or Render.
# The cameras must be reachable from wherever this runs: on a cloud host
# that means the office cameras are NOT visible - see README, "Deploying".
FROM python:3.12-slim

# OpenCV needs libgl1/libglib even without a screen; tzdata for the clock.
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 tzdata \
    && rm -rf /var/lib/apt/lists/*
# Events and reports use local time: the office's, not the server's UTC.
ENV TZ=Asia/Kolkata

WORKDIR /app
COPY requirements.txt .
# The CPU build of PyTorch: the default one pulls ~2 GB of GPU libraries.
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# NetraAttend's face models are not in git (InsightFace licence): fetched from
# the official release, checksum-verified.
COPY netra/download_models.py netra/download_models.py
RUN python netra/download_models.py

COPY . .
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["python", "app.py"]
