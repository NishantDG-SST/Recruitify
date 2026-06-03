# Contributing to Recruitify

We love your input! We want to make contributing to this project as easy and transparent as possible, whether it's:
- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features

## We Develop with Github
We use GitHub to host code, to track issues and feature requests, as well as accept pull requests.

## How to Contribute

### 1. Fork & Clone
First, fork the repository on GitHub to your own account, then clone it to your local machine:
```bash
git clone https://github.com/YOUR_USERNAME/Recruitify.git
cd Recruitify
```

### 2. Add the Upstream Remote
Connect your local repository to the original "upstream" repository to keep it in sync:
```bash
git remote add upstream https://github.com/NishantDG-SST/Recruitify.git
```

### 3. Create a Branch
Always create a new branch for your work. Use a descriptive name like `feature/add-new-scoring-metric` or `bugfix/fix-upload-timeout`:
```bash
git checkout -b feature/your-feature-name
```

### 4. Make your Changes
Make your changes to the codebase. Ensure that you test your changes locally using the instructions in the `README.md`.

### 5. Commit & Push
Commit your changes with a clear, descriptive commit message:
```bash
git add .
git commit -m "feat: Add new scoring metric for soft skills"
git push origin feature/your-feature-name
```

### 6. Create a Pull Request
Go to the original Recruitify repository on GitHub and click "New pull request". Select your branch and provide a clear description of what your pull request does.

## Development Setup

See the [README.md](README.md) for detailed instructions on how to set up the Postgres database, Redpanda, FastAPI backend, and Next.js frontend locally using Docker Compose.

## Code Style
- **Python (Backend):** Follow PEP 8 guidelines. Type hints are highly encouraged.
- **TypeScript (Frontend):** Use strong typing, avoid `any`, and follow the existing Prettier/ESLint configuration.

## Report Bugs Using GitHub's Issues
We use GitHub issues to track public bugs. Report a bug by opening a new issue; it's that easy!

*Thank you for contributing!*
