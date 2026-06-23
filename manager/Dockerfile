FROM python:3.12-alpine

WORKDIR /app

COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

ENV MANAGER_BIND_HOST=0.0.0.0
ENV MANAGER_PORT=8080

EXPOSE 8080

CMD ["python", "/app/backend/app.py"]
