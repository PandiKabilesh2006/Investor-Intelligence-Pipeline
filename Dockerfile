# Stage 1: Build the Next.js frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Stage 2: Create the final production container
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies (build-essential for compiling C-extensions if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all codebase (respecting .dockerignore)
COPY . .

# Copy compiled frontend static files from Stage 1 into the location served by FastAPI
COPY --from=frontend-builder /app/frontend/out ./frontend/out

# Port configuration
EXPOSE 8000

# Run the app
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
