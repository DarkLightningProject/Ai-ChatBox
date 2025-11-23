⭐ Features of This AI Chat Backend

This backend provides a powerful multi-model chat system with support for text chat, uncensored chat mode, OCR (image/PDF text extraction), and document-based Q&A. Built using Django REST Framework, Mistral, OpenRouter, and Google Gemini.

🚀 1. Multi-Mode Chat System
✔ Regular Chat (Mistral API)

Uses Mistral models (e.g., mistral-medium-latest)

Maintains conversation history per session

Automatically generates short chat titles

✔ Uncensored Chat (OpenRouter)

Uses OpenRouter model:
cognitivecomputations/dolphin-mistral-24b-venice-edition:free

Same features as regular chat, but with uncensored responses

🧠 2. Smart Session Management

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

📄 3. OCR (Text Extraction from Files)
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

❓ 4. OCR-Based Question Answering
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

🖼️ 5. Multi-Image AI Analysis
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

💬 6. Chat History API
GET /api/history/?session_id=...&mode=...

Returns complete history:

role (user/assistant/system)

content

attachments

mode (regular/uncensored/ocr)

✏️ 7. Rename Chat Session
PUT /api/sessions/<session_id>/

Rename any chat session with a custom title.

🗑️ 8. Delete Chat Session
DELETE /api/sessions/<session_id>/

Remove chat and history completely.

🔁 9. Automatic Retry Handling

All LLM calls include:

Retry on API rate limits

Retry on 500-series errors

Respect server retry-after headers

Returns clean error messages

📦 10. Full Media Storage Support

Uploaded images, PDF files, and OCR temp files are:

Safely stored

Cleaned automatically

Returned to user as URLs

🛡️ 11. CORS + Security Setup

CORS allowed for development

Custom headers supported

Django REST Framework for clean API structure



How yoou setup-

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
# Mistral (Regular Chat Mode)
# ================================
MISTRAL_API_KEY=your_mistral_api_key_here
MISTRAL_BASE_URL=https://api.mistral.ai/v1
MISTRAL_MODEL=mistral-medium-latest


# ================================
# OpenRouter (Uncensored Chat Mode)
# ================================
OPENROUTER_API_KEY=your_openrouter_api_key_here
UNCENSORED_MODEL=cognitivecomputations/dolphin-mistral-24b-venice-edition:free


# ================================
# Google Gemini (OCR + File Processing)
# ================================
GOOGLE_API_KEY=your_google_api_key_here
GEMINI_TEXT_MODEL=gemini-2.5-flash
GEMINI_FILE_MODEL=gemini-2.5-flash

📌 Notes for Developers
✔ Do NOT wrap keys in quotes

Correct:

MISTRAL_API_KEY=abcd1234


Incorrect:

MISTRAL_API_KEY="abcd1234"

✔ Make sure .env is in your project root

Same level as manage.py.

✔ Add .env to .gitignore

(Already recommended — prevents exposing your API keys)

.env
