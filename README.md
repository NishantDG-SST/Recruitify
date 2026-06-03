# Recruitment Platform

Production-grade recruitment intelligence platform with AI-driven extraction, dynamic candidate-to-job ranking, and automated interview question generation.

## Features

- **Automated Resume Parsing:** Upload candidate PDFs and automatically extract structured profiles using LLMs.
- **Dynamic Job Matching:** Job requirements are extracted automatically upon creation and candidates are scored out of 100 based on their experience and exact matching skills.
- **AI Interview Generation:** Automatically generate tailored technical and behavioral interview questions based on the candidate's specific profile and the job they are applying for.

## Repository layout

- `apps/web`: Recruiter UI dashboard (Next.js & Tailwind CSS)
- `apps/api`: API gateway and service endpoints (FastAPI)
- `services`: Python service modules for LLM extraction, bias analysis, and scoring
- `db`: Database schema for Postgres / pgvector
- `docker-compose.yml`: Local infrastructure including Postgres and Redpanda (Kafka)

## Prerequisites

1. Docker & Docker Compose
2. Node.js (for Next.js frontend)
3. Python 3.10+ (for FastAPI backend)
4. A Groq API key (for fast LLM extraction using Llama 3)

## How to Run

### 1. Start Infrastructure
Run the database and message broker:
```bash
docker compose up -d
```

### 2. Start the Backend API
The backend requires some environment variables to connect to Groq and Postgres:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the API server
DATABASE_DSN="postgresql://recruitment:recruitment@localhost:5432/recruitment" \
STORAGE_ROOT="/tmp/recruitment-platform" \
OPENAI_API_KEY="your_groq_api_key_here" \
OPENAI_BASE_URL="https://api.groq.com/openai/v1" \
LLM_MODEL="llama-3.1-8b-instant" \
uvicorn apps.api.src.main:app --reload --port 8000
```

### 3. Start the Web UI
In a separate terminal:
```bash
cd apps/web
npm install
npm run dev
```
Access the application at `http://localhost:3000`.

## Architecture principles

- **Synchronous Extraction:** The candidate upload endpoint performs inline, synchronous LLM extraction for immediate feedback in the UI, bypassing traditional delayed workers.
- **Evidence-first explainability:** Features emit evidence alongside scores.
- **Stateless AI Integration:** Groq's high-speed API powers the natural language extraction and parsing layers.

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for detailed instructions on how to fork the repository, create a branch, and submit a pull request.
