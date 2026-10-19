# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm
RUN --mount=type=secret,id=proxy_ca apt-get -o Acquire::https::CaInfo=/run/secrets/proxy_ca update && apt-get -o Acquire::https::CaInfo=/run/secrets/proxy_ca install -y --no-install-recommends ffmpeg tesseract-ocr tesseract-ocr-kor tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY apps/worker/requirements.lock /app/requirements.lock
RUN --mount=type=secret,id=proxy_ca PIP_CERT=/run/secrets/proxy_ca pip install --no-cache-dir -r requirements.lock
COPY apps/worker/factlens /app/factlens
RUN useradd --uid 1000 --create-home worker
RUN chmod -R a+rX /app
USER worker
ENV PYTHONUNBUFFERED=1
CMD ["python","-m","factlens.main"]
