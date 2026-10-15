# Contributing to Folio

Welcome to Folio! Thank you for your interest in contributing to our source-grounded AI study companion.

Folio is designed to provide verifiable, hallucination-resistant academic tutoring by grounding every explanation, quiz, and study recommendation directly in course materials (lecture PDFs, slide decks, and timestamped transcripts).

This document outlines our development workflows, coding conventions, testing standards, and contribution processes.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Report Bugs](#how-to-report-bugs)
- [How to Suggest Features](#how-to-suggest-features)
- [Development Setup](#development-setup)
  - [Prerequisites](#prerequisites)
  - [Backend Setup (with uv)](#backend-setup-with-uv)
  - [Frontend Setup](#frontend-setup)
  - [Mock Mode vs Live Mode](#mock-mode-vs-live-mode)
- [Project Architecture & Conventions](#project-architecture--conventions)
  - [Python & Backend Conventions](#python--backend-conventions)
  - [Frontend Conventions](#frontend-conventions)
  - [Prompt Engineering Standards](#prompt-engineering-standards)
  - [Database & Threading Rules](#database--threading-rules)
  - [Offline Mock Parity](#offline-mock-parity)
- [Branching & Workflow](#branching--workflow)
  - [Branch Naming](#branch-naming)
  - [Commit Message Guidelines](#commit-message-guidelines)
  - [Pull Request Checklist](#pull-request-checklist)
- [Testing & Verification](#testing--verification)
  - [Running the Verification Suite](#running-the-verification-suite)
  - [Subsystem Verification Matrix](#subsystem-verification-matrix)
  - [Adding a New Verification Suite](#adding-a-new-verification-suite)
  - [Regenerating OpenAPI Specifications](#regenerating-openapi-specifications)
- [Security & Vulnerability Disclosure](#security--vulnerability-disclosure)

---

## Code of Conduct

We are committed to providing a welcoming, inclusive, and harassment-free environment for all contributors.
- **Be respectful and collaborative:** Value differing perspectives and give constructive feedback.
- **Focus on educational impact:** Ensure student privacy, data isolation, and pedagogical integrity.
- **Maintain academic honesty:** Build features that explain concepts and guide students rather than supplying blind answers without citations.

---

## How to Report Bugs

Before creating an issue, search the issue tracker to ensure the problem has not already been reported.

When filing a bug report, please include:
1. **Clear description:** A concise summary of what went wrong.
2. **Steps to reproduce:** Minimal, step-by-step instructions.
3. **Expected vs Actual behavior:** What should have happened versus what actually occurred.
4. **Execution Mode:** Indicate whether the bug occurred under Mock Mode (`LLM_MOCK=true`) or Live Gemini Mode (`LLM_MOCK=false`).
5. **Request ID:** The `X-Request-ID` header returned in the HTTP response (or logged in server console).
6. **Logs & Stack Trace:** Relevant server or console logs with all API keys and secrets sanitized.
7. **Environment details:** Operating system, Python version (`python --version`), Node.js version, and browser (if UI-related).

---

## How to Suggest Features

We welcome ideas that enhance student learning, retrieval accuracy, and system resilience. When proposing a new feature:
- Describe the student or instructor problem you are solving.
- Detail how the feature preserves source grounding and provenance.
- Note any changes required across the database schema, LLM prompts, and frontend views.
- Outline how offline mock mode will mirror the feature for deterministic automated testing.

---

## Development Setup

### Prerequisites

- **Python:** 3.12 or newer
- **uv:** Ultra-fast Python package and project manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Node.js:** 18.x, 20.x, or 22.x LTS with `npm`
- **Google Gemini API Key:** Optional for local development; required only when testing live generation (`LLM_MOCK=false`). Obtainable from [Google AI Studio](https://aistudio.google.com/).

### Backend Setup (with uv)

```bash
# Navigate to the backend directory
cd backend

# Create virtual environment and synchronize dependencies using uv
uv sync

# Create local environment file from template
cp .env.example .env

# Run database migrations and start development server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The interactive OpenAPI documentation will be available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Frontend Setup

```bash
# Navigate to the frontend directory
cd frontend

# Install dependencies
npm install

# Start the Vite development server
npm run dev
```

The frontend application runs by default at `http://localhost:5173`.

### Mock Mode vs Live Mode

Folio defaults to **Mock Mode** (`LLM_MOCK=true` in `.env`). This mode:
- Runs entirely offline without making network requests to Gemini.
- Uses deterministic 64-dimensional lexical embeddings and heuristic mock responses.
- Enables instant verification of the entire system without consuming API quotas.

**Switching to Live Mode:**
1. In `backend/.env`, set:
   ```ini
   LLM_MOCK=false
   GEMINI_API_KEY=your_actual_gemini_api_key
   LLM_MODEL=gemini-2.5-flash
   EMBEDDING_MODEL=gemini-embedding-001
   ```
2. Reset vector store embeddings (required due to dimension difference between 64-dim mock vectors and 768-dim Gemini embeddings):
   ```bash
   curl -X POST http://localhost:8000/api/v1/dev/vector-reset
   ```
   *Alternatively, remove `backend/storage/chroma` while the backend is stopped.*
3. Re-embed course material:
   ```bash
   curl -X POST http://localhost:8000/api/v1/dev/reembed-all
   ```

---

## Project Architecture & Conventions

### Python & Backend Conventions

- **Strict Type Annotations:** Every function and method must declare argument and return types. Avoid untyped `Any` wherever possible.
- **Pydantic Validation:** All request payloads and response contracts must use Pydantic models. Every route in `app/api/routes/` MUST define a `response_model` and OpenAPI tags.
- **Standardized Error Handling:** Never raise unhandled exceptions or return bare HTTP status dictionaries. Use `AppError`:
  ```python
  from app.core.errors import AppError

  raise AppError(
      message="Student has not attempted diagnostic assessment",
      code="diagnostic_required",
      status_code=400,
  )
  ```
  This guarantees standard JSON error payloads: `{"error": {"code": "...", "message": "..."}}`.
- **Additive API Changes:** Public API contracts in `/api/v1` must remain backward compatible. Deprecate fields with documentation rather than deleting them.

### Frontend Conventions

- **React 19 & TypeScript:** Build modular, strictly typed components.
- **Tailwind CSS v4:** Utilize project theme tokens (e.g. `bg-surface-card`, `text-brand-600`, `dark:bg-dark-card`).
- **Semantic HTML & Accessibility:** Maintain semantic landmarks (`header`, `nav`, `main`, `aside`), visible focus indicators, and keyboard navigability.
- **Component Colocation:** Place reusable UI primitives in `src/components/ui/` and page-level layouts in `src/components/layout/`.

### Prompt Engineering Standards

- **Centralized Prompts:** Prompts MUST NOT be defined inline inside routes or services. Store all prompts in dedicated `prompts.py` files within each service directory:
  - `backend/app/services/tutor/prompts.py`
  - `backend/app/services/assessment/prompts.py`
  - `backend/app/services/grading/prompts.py`
  - `backend/app/services/kb/prompts.py`
- **Dynamic Configuration:** NEVER hard-code model identifiers in code or prompts. Always reference `settings.llm_model`, `settings.embedding_model`, or `settings.verify_model`.
- **System and User Role Separation:** Distinctly separate system behavioral guardrails from user contextual inputs.
- **Structured JSON Schema:** When expecting structured output, use `llm.generate_json(prompt, schema=MySchema, system=SYSTEM_PROMPT)` to enforce schema adherence with automatic validation retries.

### Database & Threading Rules

- **Background Tasks & Concurrency:** FastAPI request database sessions (`db: Session = Depends(get_db)`) close when the HTTP response completes. Background threads or worker tasks MUST create and manage their own database sessions using `SessionLocal()`:
  ```python
  from app.db.session import SessionLocal

  def _background_worker(course_id: int):
      with SessionLocal() as db:
          # perform operations and commit safely
          db.commit()
  ```
- **Thread Safety:** When modifying student mastery or knowledge base structures, use thread-safe mutexes or student-specific locks (e.g. `_get_student_lock(student_id)` in `mastery.py`).

### Offline Mock Parity

Every LLM-dependent feature MUST implement deterministic offline mock behavior:
- Verify that features run seamlessly under `LLM_MOCK=true`.
- Place mock algorithms in `mock.py` or within client fallbacks (e.g., `MockTutor`, `MockQuestionGenerator`, `MockQuestionVerifier`).
- Ensure mock behavior validates identical schema outputs so frontend and verification scripts function identically offline.

---

## Branching & Workflow

### Branch Naming

Follow conventional branch prefixes:
- `feat/` for new features (e.g., `feat/audio-transcript-sync`)
- `fix/` for bug fixes (e.g., `fix/bkt-slip-calculation`)
- `docs/` for documentation updates (e.g., `docs/troubleshooting-guide`)
- `test/` for new test cases or evaluation suites (e.g., `test/ragas-retrieval-eval`)
- `refactor/` for code restructuring without behavior changes

### Commit Message Guidelines

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:
```text
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

**Allowed types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`.

**Examples:**
- `feat(tutor): add topic scoping parameter to tutor conversation endpoint`
- `fix(ingestion): validate webvtt magic header before scheduling chunk worker`
- `docs(readme): add troubleshooting section for embedding dimension mismatch`
- `test(grading): add edge-case test for numerical scientific notation tolerance`

### Pull Request Checklist

Before submitting a pull request, verify that:
- [ ] All 9 backend verification suites pass: `python scripts/verify_all.py`.
- [ ] Frontend builds cleanly without TypeScript or ESLint errors: `npm run build && npm run lint`.
- [ ] Any new API endpoint has tags, descriptions, and a Pydantic `response_model`.
- [ ] `backend/openapi.json` is updated via `python scripts/export_openapi.py`.
- [ ] No API keys, credentials, or personal secrets are present in code or `.env`.
- [ ] New functionality includes offline mock support (`LLM_MOCK=true`).
- [ ] Documentation in `README.md` and inline docstrings are updated.

---

## Testing & Verification

### Running the Verification Suite

From the `backend/` directory:

```bash
# Execute all 9 verification suites
python scripts/verify_all.py
```

### Subsystem Verification Matrix

When modifying specific subsystems, run the corresponding verification script:

| Subsystem | Script | Coverage |
| :--- | :--- | :--- |
| **Ingestion & Parsing** | `scripts/verify_ingestion.py` | PDF, PPTX, WebVTT, SRT, JSON parsing, chunking bounds, magic byte sniffing |
| **Knowledge Base** | `scripts/verify_kb.py` | Topic hierarchy synthesis, concept extraction, prerequisite DAG, cycle detection |
| **Grounded Tutor** | `scripts/verify_tutor.py` | Gating, grounding states, query rewriting, citation validation, topic scoping |
| **Assessments** | `scripts/verify_quiz.py` | Question generation (MCQ, Short Answer, Numerical), second-pass verification, deduplication |
| **Grading & Rubrics** | `scripts/verify_grading.py` | Rule-based MCQ & numeric evaluation, rubric short-answer scoring, misconception detection |
| **Learner Model** | `scripts/verify_learner.py` | BKT updates, Ebbinghaus retention decay, recommendations engine, study planner |
| **Final Hardening** | `scripts/verify_final.py` | Error schemas, request tracing, pagination bounds, health checks |
| **Live LLM Contract** | `scripts/verify_llm_contract.py` | Gemini model signatures, JSON schema adherence, embedding shapes |
| **Auth & Security** | `scripts/verify_auth.py` | JWT token issuing, Argon2 password rules, brute-force lockout, tenant data isolation |

### Adding a New Verification Suite

1. Place the test script in `backend/scripts/` (e.g., `verify_new_feature.py`).
2. Implement standalone execution with `if __name__ == "__main__":`.
3. Ensure exit code is `0` on success and non-zero on failure.
4. Register the suite in `backend/scripts/verify_all.py` within `TEST_SUITES`.

### Regenerating OpenAPI Specifications

Whenever endpoints, schemas, or models change, regenerate `backend/openapi.json`:

```bash
cd backend
python scripts/export_openapi.py
```
This script validates that all endpoints define tags and response models, failing if any endpoints violate specification standards.

---

## Security & Vulnerability Disclosure

- **Never commit credentials:** Do not commit `.env` files, API keys, or JWT secrets. Use `.gitignore` to prevent secret leaks.
- **Private Disclosure:** If you discover a security vulnerability or sensitive data exposure in Folio, please report it privately:
 
  Contact: `aniketbhil88@gmail.com`

Please do not disclose security issues on public GitHub issue trackers until the team has reviewed and addressed the report.
