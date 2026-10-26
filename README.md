⭐ Features of This AI Chat Backend

This backend provides regular and uncensored chat, OCR and document Q&A, image analysis, and a multi-agent debugging assistant. It uses Django REST Framework, OpenRouter, and Google Gemini.

🚀 1. Multi-Mode Chat System
✔ Regular Chat (Mistral through OpenRouter)

Uses `mistralai/mistral-medium-3` through OpenRouter.

The legacy `MISTRAL_MODEL=mistral-medium-latest` value is automatically mapped to this OpenRouter model ID.

Maintains conversation history per session

Automatically generates short chat titles

✔ Uncensored Chat (OpenRouter)

Uses OpenRouter model:
cognitivecomputations/dolphin-mistral-24b-venice-edition

Same features as regular chat, but with uncensored responses. This model may
incur OpenRouter charges. The legacy `:free` model setting is mapped to the
supported model ID above.

🧠 2. Multi-Debugger

The Multi-Debugger runs three specialist analyses in parallel and combines them into one response.

Free tier:

- Logic Analyst — Mistral Medium 3 through OpenRouter
- Syntax & Runtime Inspector — the regular-chat model through OpenRouter
- Performance & Security Auditor — Gemini 2.5 Flash, with an OpenRouter fallback
- Synthesizer — the regular-chat model through OpenRouter

Premium tier:

- Logic Analyst — Gemini 4 Argon through OpenRouter
- Syntax & Runtime Inspector — GPT-5.4 through OpenRouter
- Performance & Security Auditor — Claude Opus 4.7 through OpenRouter
- Synthesizer — Claude Sonnet 4.6 through OpenRouter

Each specialist receives a role-specific prompt. Premium model IDs can be overridden with the `DEBUG_PREMIUM_*_MODEL` environment variables listed below. The OpenRouter account must have access to the selected models.

🧠 3. Smart Session Management

Each chat mode uses session tracking:

Create new session

Reuse existing session

Auto-save chat title

Delete sessions

List all sessions with last updated time

Supports separate histories for:

regular mode

uncensored mode

OCR mode

📄 4. OCR (Text Extraction from Files)
✔ Upload Images / PDFs / TXT

POST /api/ocr/

Backend uses Gemini (gemini-2.5-flash) to:

Read images

Read PDFs

Extract all text

Save extracted text as "system" message in OCR session

Supports:

Multi-page documents

Large images

All file types supported by Gemini

❓ 5. OCR-Based Question Answering
POST /api/ocr-qa/

Two modes:

If document text exists →
Answer strictly from the document

If no document uploaded →
General AI answer

Returns:

Answer

Session ID

Whether answer came from document or general AI

🖼️ 6. Multi-Image AI Analysis
POST /api/ocr/images/

Upload up to 4 images at once

Uses Gemini Vision (gemini-2.5-flash)

Saves images in Django MEDIA/ folder

Saves user query + assistant response + attachments

Returns:

AI response

saved image URLs

session ID

Great for:

Chart analysis

Homework problem solving

Document screenshots

Comparison tasks

💬 7. Chat History API
GET /api/history/?session_id=...&mode=...

Returns complete history:

role (user/assistant/system)

content

attachments

mode (regular/uncensored/ocr)

✏️ 8. Rename Chat Session
PUT /api/sessions/<session_id>/

Rename any chat session with a custom title.

🗑️ 9. Delete Chat Session
DELETE /api/sessions/<session_id>/

Remove chat and history completely.

🔁 10. Automatic Retry Handling

All LLM calls include:

Retry on API rate limits

Retry on 500-series errors

Respect server retry-after headers

Returns clean error messages

📦 11. Full Media Storage Support

Uploaded images, PDF files, and OCR temp files are:

Safely stored

Cleaned automatically

Returned to user as URLs

🛡️ 12. CORS + Security Setup

CORS allowed for development

Custom headers supported

Django REST Framework for clean API structure



## Setup

Create a file named .env inside the root directory of your project:

chatgpt_clone_backend/
│── backend/
│── chat/
│── chatgpt-frontend/
│── venv/
│── .env   ← CREATE THIS FILE HERE


Inside this .env file, add the following environment variables:

🔐 Environment Variables (.env)

Copy & paste this block exactly, then replace the placeholder values with your own API keys.

# ================================
# OpenRouter (Regular Chat Mode)
# ================================
OPENROUTER_API_KEY=your_openrouter_api_key_here
# Regular chat and Free-tier Syntax/Synthesis model on OpenRouter.
# mistral-medium-latest is accepted as a legacy value and mapped automatically.
MISTRAL_MODEL=mistralai/mistral-medium-3

# Optional: path to your organization's trusted proxy/root CA certificate.
# TLS certificate verification remains enabled.
# OPENROUTER_CA_BUNDLE=C:/certs/organization-root-ca.pem


# ================================
# OpenRouter (Uncensored Chat Mode)
# ================================
# This model may incur OpenRouter charges.
UNCENSORED_MODEL=cognitivecomputations/dolphin-mistral-24b-venice-edition


# ================================
# Google Gemini (OCR + File Processing)
# ================================
GOOGLE_API_KEY=your_google_api_key_here
GEMINI_TEXT_MODEL=gemini-2.5-flash
GEMINI_FILE_MODEL=gemini-2.5-flash

# Multi-Debugger Free-tier Logic Analyst
DEBUG_MISTRAL_MODEL=mistralai/mistral-medium-3

# Multi-Debugger Premium specialist models
DEBUG_PREMIUM_LOGIC_MODEL=google/gemini-4-argon
DEBUG_PREMIUM_SYNTAX_MODEL=openai/gpt-5.4
DEBUG_PREMIUM_PERF_MODEL=anthropic/claude-opus-4.7
DEBUG_PREMIUM_SYNTH_MODEL=anthropic/claude-sonnet-4.6

# The DEBUG_PREMIUM_*_MODEL entries are optional; these values are the defaults.

📌 Notes for Developers
✔ Do NOT wrap keys in quotes

Correct:

OPENROUTER_API_KEY=your_openrouter_api_key_here


Incorrect:

OPENROUTER_API_KEY="your_openrouter_api_key_here"

✔ Make sure .env is in your project root

Same level as manage.py.

✔ Add .env to .gitignore

(Already recommended — prevents exposing your API keys)

.env
