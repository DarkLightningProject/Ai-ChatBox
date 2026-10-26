# Note
Dont add any sensitive information only dummy information im not responisble for any leak data it is just a prototype


# AI Chat Backend

A Django-based AI chat backend with multi-mode chat, OCR/document Q&A, image analysis, and a multi-agent debugging workflow. It supports both regular chat and uncensored model flows, and is designed to work with a separate frontend app in the `chatgpt-frontend/` directory.

## Overview

This project provides a backend API for:

- Regular chat conversations
- Uncensored chat mode
- OCR/document text extraction
- Document-based Q&A
- Multi-image analysis
- Session history and rename/delete support
- Multi-agent code analysis and debugging

The backend uses:

- Django
- Django REST Framework
- OpenRouter for LLM access
- Google Gemini for OCR and document processing
- SQLite/PostgreSQL-compatible Django database setup

## Project Structure

```bash
chatgpt_clone_backend/
├── backend/                 # Django project and app logic
├── chat/                    # app-level chat logic
├── chatgpt-frontend/        # separate frontend project (React app)
├── .env                     # local environment variables
├── manage.py                # Django management entry point
├── requirements.txt         # Python dependencies
├── README.md                # project documentation
└── venv/                    # local virtual environment
```

> Note: The frontend is kept in a separate repository/folder and is not part of the backend Git history.

## Features

### 1. Multi-mode chat

- Regular chat through OpenRouter
- Uncensored chat mode
- Session-aware conversation history
- Auto-generated chat titles
- Reuse existing sessions
- Delete and rename sessions

### 2. Multi-agent debugging assistant

The backend can run multiple specialist analyzers in parallel and synthesize one final result.

Example specialist roles include:

- Logic Analyst
- Syntax & Runtime Inspector
- Performance & Security Auditor
- Synthesizer

Premium model tiers can be configured with environment variables for advanced model routing.

### 3. OCR and document processing

- Upload images, PDFs, and text files
- Extract text from documents
- Save OCR output into a session
- Answer questions using the document context when available
- Support for multi-page and multi-image use cases

### 4. Media and image analysis

- Upload up to 4 images at once
- Process visual content using Gemini Vision
- Store uploaded media in Django media storage
- Return saved attachments and URLs to the client

### 5. API convenience features

- Chat history retrieval
- Session rename/delete
- Automatic retry handling for OpenRouter/Gemini errors
- Rate-limit-aware retries
- Cleaner error handling for upstream API failures

## Tech Stack

- Python
- Django
- Django REST Framework
- OpenRouter
- Google Gemini
- React frontend (separate app in `chatgpt-frontend/`)

## Requirements

- Python 3.10+
- pip
- virtual environment
- API keys for OpenRouter and Google Gemini

## Local Setup

1. Clone the repository.
2. Create and activate a virtual environment.
3. Install dependencies.

```bash
python -m venv venv
source venv/bin/activate   # macOS/Linux
venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

4. Create a `.env` file in the project root.
5. Add the required environment variables shown below.
6. Run Django migrations.

```bash
python manage.py migrate
```

7. Start the development server.

```bash
python manage.py runserver
```

## Environment Variables

Create a `.env` file in the project root with the following values:

```env
# OpenRouter (Regular Chat Mode)
OPENROUTER_API_KEY=your_openrouter_api_key_here
MISTRAL_MODEL=mistralai/mistral-medium-3

# OpenRouter (Uncensored Chat Mode)
UNCENSORED_MODEL=cognitivecomputations/dolphin-mistral-24b-venice-edition

# Google Gemini (OCR + File Processing)
GOOGLE_API_KEY=your_google_api_key_here
GEMINI_TEXT_MODEL=gemini-2.5-flash
GEMINI_FILE_MODEL=gemini-2.5-flash

# Multi-Debugger Free-tier model
DEBUG_MISTRAL_MODEL=mistralai/mistral-medium-3

# Optional premium specialist models
DEBUG_PREMIUM_LOGIC_MODEL=google/gemini-4-argon
DEBUG_PREMIUM_SYNTAX_MODEL=openai/gpt-5.4
DEBUG_PREMIUM_PERF_MODEL=anthropic/claude-opus-4.7
DEBUG_PREMIUM_SYNTH_MODEL=anthropic/claude-sonnet-4.6
```

### Notes

- Do not wrap keys in quotes.
- Keep the `.env` file out of version control.
- If your OpenRouter account uses an internal certificate chain, you can optionally set `OPENROUTER_CA_BUNDLE`.

## Common API Endpoints

Examples of main API flows include:

- `POST /api/chat/` — regular chat
- `POST /api/uncensored/` — uncensored model chat
- `POST /api/ocr/` — image/PDF/text extraction
- `POST /api/ocr-qa/` — document Q&A
- `POST /api/ocr/images/` — multi-image analysis
- `GET /api/history/` — session history
- `PUT /api/sessions/<session_id>/` — rename session
- `DELETE /api/sessions/<session_id>/` — delete session

The exact endpoint names may vary slightly depending on your app version, so check the project route files and Django app URLs before integrating externally.

## Authentication and Session Behavior

This project uses Django session-based authentication patterns and has separate handling for admin and customer-facing flows. If the frontend and Django admin share the same browser session space without separation, login states can collide. In production, ensure that admin and frontend cookies are isolated using separate names and paths.

## Development Notes

- Frontend is not included in the same Git branch as the backend in this setup.
- For local frontend development, run the separate React app in `chatgpt-frontend/`.
- Keep the backend and frontend deployed independently when using separate hosting providers or branch strategies.

## Security

- Store secrets in environment variables, not in source code.
- Do not commit `.env` files.
- Restrict admin access and use strong credentials in production.
- Review CORS and session cookie settings before public deployment.

## License

This project is intended for internal or project-specific use. Add your licensing details here if you plan to distribute it publicly.

## Contributing

Contributions are welcome. For larger changes, open an issue or discuss the intended behavior before making a substantial PR.

## Support

For environment issues, check:

- `.env` values
- Python dependencies
- model API keys
- Django settings and session/cookie configuration
- frontend/backend deployment URLs

## Quick Tips

- Keep `.env` in the project root, next to `manage.py`.
- Add `.env` to `.gitignore` to avoid committing secrets.
- For production, isolate frontend and admin cookies to avoid session collisions.

