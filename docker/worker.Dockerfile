# syntax=docker/dockerfile:1
FROM python:3.12-alpine3.24
RUN --mount=type=secret,id=proxy_ca,target=/etc/apk/ca.pem apk upgrade --no-cache \
    && apk add --no-cache ffmpeg tesseract-ocr tesseract-ocr-data-kor tesseract-ocr-data-eng font-dejavu \
    && mkdir -p /usr/share/fonts/truetype/dejavu \
    && font="$(find /usr/share/fonts -name DejaVuSans.ttf -print -quit)" \
    && test -n "$font" \
    && if [ ! -e /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf ]; then ln -s "$font" /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf; fi
WORKDIR /app
COPY apps/worker/requirements.lock /app/requirements.lock
RUN --mount=type=secret,id=proxy_ca PIP_CERT=/run/secrets/proxy_ca pip install --no-cache-dir --only-binary=:all: -r requirements.lock
COPY apps/worker/factlens /app/factlens
RUN addgroup -g 1000 worker && adduser -u 1000 -D -G worker worker
RUN chmod -R a+rX /app
USER worker
ENV PYTHONUNBUFFERED=1
CMD ["python","-m","factlens.main"]
