FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (e.g. for psycopg2, pdfplumber)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set python path
ENV PYTHONPATH=/app/apps/api/src:/app
ENV APP_ENV=production

# Run the Kafka consumer script
CMD ["python", "services/workers/bootstrap.py"]
