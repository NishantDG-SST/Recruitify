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

# Set python path to include the root and the api source
ENV PYTHONPATH=/app/apps/api/src:/app
ENV APP_ENV=production

EXPOSE 8000

CMD ["uvicorn", "apps.api.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
