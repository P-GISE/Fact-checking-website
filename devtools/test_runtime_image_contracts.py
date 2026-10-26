"""Source boundaries complemented by actual offline built-image smoke in the pilot."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


class RuntimeImageContracts(unittest.TestCase):
    def test_api_preserves_runtime_contract_with_only_production_dependencies(self):
        source=(ROOT/'docker/api.Dockerfile').read_text()
        self.assertIn('FROM node:24-alpine3.24 AS build',source)
        self.assertIn('FROM node:24-alpine3.24 AS production-dependencies',source)
        self.assertIn('npm ci --omit=dev --workspace apps/api --include-workspace-root',source)
        runtime=source.rsplit('FROM ',1)[1]
        for required in ('COPY --from=production-dependencies','/usr/local/lib/node_modules',
                         'COPY --from=build /app/apps/api/dist','COPY apps/api/migrations',
                         'USER node','ENV NODE_ENV=production API_HOST=0.0.0.0 MEDIA_ROOT=/data/media',
                         'CMD ["node","apps/api/dist/server.js"]','io.factlens.migration-control="v1"'):
            self.assertIn(required,runtime)
        self.assertNotIn('npm run build',runtime)

    def test_worker_keeps_python_minor_and_nonroot_tool_contracts(self):
        source=(ROOT/'docker/worker.Dockerfile').read_text()
        self.assertIn('FROM python:3.12-alpine3.24',source)
        for required in ('--only-binary=:all:','ffmpeg','tesseract-ocr-data-eng','tesseract-ocr-data-kor',
                         'adduser -u 1000','USER worker','ENV PYTHONUNBUFFERED=1',
                         'CMD ["python","-m","factlens.main"]'):
            self.assertIn(required,source)
        for forbidden in ('gcc','build-base','apk add --no-cache git','python:3.13'):
            self.assertNotIn(forbidden,source)

    def test_web_patches_vendor_runtime_without_changing_configuration(self):
        source=(ROOT/'docker/web.Dockerfile').read_text()
        self.assertIn('FROM nginxinc/nginx-unprivileged:stable-alpine',source)
        self.assertIn('apk upgrade --no-cache',source)
        self.assertIn('COPY docker/${NGINX_CONFIG} /etc/nginx/conf.d/default.conf',source)
        self.assertTrue(source.rstrip().endswith('USER nginx'))


if __name__=='__main__':unittest.main()
