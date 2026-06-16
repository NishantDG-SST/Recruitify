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
Ensure Docker is running. If updating from a previous version, clean up old containers and volumes first to ensure database schemas and seeds are re-applied:
```bash
docker compose down -v
docker compose up -d
```

### 2. Configure Environment Variables
Copy the environment variables template to a local `.env` file and insert your API keys (e.g. Groq, Gemini):
```bash
cp .env.example .env
```

### 3. Start the Backend API
From the **root directory** of the project, create a Python virtual environment (use `python3` on macOS/Linux), install dependencies, and start the FastAPI service:
```bash
# Make sure you are in the root of the repository
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the API server
PYTHONPATH=apps/api/src uvicorn main:app --reload --port 8000
```

### 4. Start the Web UI
In a separate terminal, install Node dependencies and launch the Next.js development server:
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
