FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    openjdk-11-jre-headless \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY backend /app/backend


RUN mkdir -p /app/uploads /app/documents && \
    chmod -R 755 /app/uploads /app/documents


EXPOSE 8000


CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]