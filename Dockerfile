# Multi-stage Docker build for ForgeAgent V1

# Stage 1: Build Frontend Assets
FROM node:22-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Runtime Backend & Application
FROM python:3.12-slim
WORKDIR /app

# Install system utilities & git
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install backend dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m playwright install --with-deps chromium

# Copy backend application
COPY backend/app ./app
COPY backend/pyproject.toml ./

# Copy compiled frontend from Stage 1 into static delivery
COPY --from=frontend-builder /build/frontend/dist /app/static

ENV FORGEAGENT_HOST=0.0.0.0
ENV FORGEAGENT_PORT=8000
ENV FORGEAGENT_EXECUTION_MODE=docker

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

