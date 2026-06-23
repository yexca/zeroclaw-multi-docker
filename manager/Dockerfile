FROM node:22-alpine AS frontend-build

WORKDIR /src/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM python:3.12-alpine

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY --from=frontend-build /src/frontend/dist/ /app/frontend/

ENV MANAGER_BIND_HOST=0.0.0.0
ENV MANAGER_PORT=7652
ENV MANAGER_FRONTEND_DIR=/app/frontend

EXPOSE 7652

CMD ["python", "/app/backend/app.py"]
