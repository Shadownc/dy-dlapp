FROM node:22-alpine AS frontend
WORKDIR /build/admin
COPY admin/package*.json ./
RUN npm ci --no-audit --no-fund
COPY admin/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY server/requirements.txt ./server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt
COPY server/ ./server/
COPY --from=frontend /build/admin/dist/ ./admin/dist/
RUN mkdir -p /app/server/data
EXPOSE 8000
CMD ["gunicorn", "-w", "2", "--threads", "4", "-b", "0.0.0.0:8000", "--timeout", "180", "server:create_app()"]
