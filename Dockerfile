# syntax=docker/dockerfile:1
# Серверный режим: интерфейс + API + обучение (по умолчанию на CPU).
# Базовые образы закреплены по тегу и digest (проверено 2026-11-09).

# ---------- 1. сборка интерфейса ----------
FROM node:26.13.0-trixie-slim@sha256:5adad64f9a1fca2d51972caa65983634c8a774eb300d72b20f7f2a0f60368072 AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---------- 2. Python-пакеты в venv ----------
FROM python:3.13.18-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS deps
# CPU-сборка torch (≈200 МБ). Для видеокарты: --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu126
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY requirements.txt ./
RUN pip install --index-url "$TORCH_INDEX" torch torchvision \
 && pip install -r requirements.txt

# ---------- 3. итоговый образ ----------
FROM python:3.13.18-slim-trixie@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 10001 --create-home --home-dir /home/app app \
 && mkdir -p /data /models && chown app:app /data
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 PORT=8765 \
    RUST_DATA_DIR=/data \
    RUST_OUT_DIR=/models \
    HF_HOME=/data/hf_cache \
    TORCH_HOME=/data/torch_cache \
    MPLCONFIGDIR=/tmp/matplotlib
WORKDIR /app
COPY --from=deps /opt/venv /opt/venv
COPY app.py ./
COPY core/ core/
COPY server/ server/
COPY --from=web /web/dist web/dist
USER app
VOLUME ["/data"]
EXPOSE 8765
# /api/auth открыт без токена; RUST_BASE_PATH учитывается, если задан
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import os,urllib.request as u;u.urlopen('http://127.0.0.1:%s%s/api/auth'%(os.environ['PORT'],os.environ.get('RUST_BASE_PATH','').rstrip('/')),timeout=4)"
CMD ["python", "app.py", "--no-browser"]
