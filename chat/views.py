


import os
import uuid
import tempfile
from typing import Optional

from django.utils.text import Truncator
from django.db.models import Max
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from rest_framework.views import APIView
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from openai import APIStatusError, APIError

from .models import Message, ChatSession
import google.generativeai as genai
from openai import OpenAI as OpenAIClient
from cloudinary.utils import cloudinary_url
 
# ================================
# Clients & Model IDs
# ================================

# --- Mistral for REGULAR mode ---


MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_BASE_URL = os.getenv("MISTRAL_BASE_URL")
REGULAR_MODEL = os.getenv("MISTRAL_MODEL")

mistral_client = OpenAIClient(
    api_key=MISTRAL_API_KEY,
    base_url=MISTRAL_BASE_URL,
)

# --- OpenRouter for UNCENSORED mode ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
UNCENSORED_MODEL = os.getenv("UNCENSORED_MODEL")

uncensored_client = OpenAIClient(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

# --- Gemini ONLY for OCR flows ---


GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL")
GEMINI_FILE_MODEL = os.getenv("GEMINI_FILE_MODEL")

# ===========
# Helpers
# ===========

def _new_session_id(prefix: str = "") -> str:
    sid = str(uuid.uuid4())[:8]
    return f"{prefix}{sid}" if prefix else sid

def _ensure_session(session_id: Optional[str], mode: str) -> str:
    if session_id:
        ChatSession.objects.get_or_create(session_id=session_id, defaults={"mode": mode})
        return session_id
    prefix = "uncensored-" if mode == "uncensored" else ("ocr-" if mode == "ocr" else "")
    new_sid = _new_session_id(prefix)
    ChatSession.objects.create(session_id=new_sid, mode=mode)
    return new_sid

def _update_title_if_empty(session_id: str, user_text: str):
    cs = ChatSession.objects.filter(session_id=session_id).first()
    if cs and not cs.title:
        snippet = Truncator((user_text or "").strip()).words(6, truncate="…") or "New chat"
        cs.title = snippet
        cs.save(update_fields=["title", "updated_at"])

def _mistral_chat_reply(messages: list[dict]) -> str:
    """Regular mode → Mistral."""
    r = mistral_client.chat.completions.create(
        model=REGULAR_MODEL,
        messages=messages
    )
    return (r.choices[0].message.content or "").strip()

def _uncensored_chat_reply(messages: list[dict]) -> str:
    r = uncensored_client.chat.completions.create(
        model=UNCENSORED_MODEL,
        messages=messages
    )
    return (r.choices[0].message.content or "").strip()

def _gemini_extract_text_from_file(file_path: str, mime_type: Optional[str] = None) -> str:
    """Upload a file (image/pdf/txt) to Gemini and ask it to extract raw text."""
    file = genai.upload_file(file_path, mime_type=mime_type)
    model = genai.GenerativeModel(GEMINI_FILE_MODEL)
    prompt = (
        "Extract the raw text content from this file as accurately as possible. "
        "No extra commentary—just the text in reading order."
    )
    resp = model.generate_content([prompt, file])
    return (resp.text or "").strip()

def _with_retries(call_fn, max_attempts=2, base_delay=1.5):
    """
    Run a callable with small backoff on 429/5xx. Return its value or re-raise.
    """
    attempt = 0
    while True:
        try:
            return call_fn()
        except APIStatusError as e:
            code = getattr(e, "status_code", None)
            # Respect server hint if present
            retry_after = 0
            try:
                retry_after = int(e.response.headers.get("retry-after", "0"))
            except Exception:
                pass

            if code in (429, 502, 503, 504) and attempt < max_attempts - 1:
                delay = retry_after or (base_delay * (2 ** attempt))
                time.sleep(delay)
                attempt += 1
                continue

            # 👇 propagate proper HTTP code & hint to client
            if code == 429:
                ra = retry_after or 2
                return Response(
                    {"error": "Rate limited", "retry_after": ra},
                    status=429
                )
            # other HTTP errors -> pass through status if known
            return Response(
                {"error": f"Upstream error ({code})"},
                status=code or 502
            )
        except APIError as e:
            # non-HTTP client errors
            return Response({"error": f"LLM client error: {e}"}, status=502)

# =================
# API Endpoints
# =================

@api_view(["POST"])
def create_session(request):
    mode = request.data.get("mode", "regular")
    sid = _ensure_session(None, mode)
    return Response({"session_id": sid, "title": "New chat", "mode": mode}, status=201)


# views.py
import time
from openai import APIStatusError, APIError  # same package you already use

def _with_retries(call_fn, max_attempts=2, base_delay=1.5):
    """
    Run a callable with small backoff on 429/5xx. Return its value or re-raise.
    """
    attempt = 0
    while True:
        try:
            return call_fn()
        except APIStatusError as e:
            code = getattr(e, "status_code", None)
            # Respect server hint if present
            retry_after = 0
            try:
                retry_after = int(e.response.headers.get("retry-after", "0"))
            except Exception:
                pass

            if code in (429, 502, 503, 504) and attempt < max_attempts - 1:
                delay = retry_after or (base_delay * (2 ** attempt))
                time.sleep(delay)
                attempt += 1
                continue

            # 👇 propagate proper HTTP code & hint to client
            if code == 429:
                ra = retry_after or 2
                return Response(
                    {"error": "Rate limited", "retry_after": ra},
                    status=429
                )
            # other HTTP errors -> pass through status if known
            return Response(
                {"error": f"Upstream error ({code})"},
                status=code or 502
            )
        except APIError as e:
            # non-HTTP client errors
            return Response({"error": f"LLM client error: {e}"}, status=502)

class ChatView(APIView):
    def post(self, request):
        try:
            mode = request.data.get("mode", "regular")
            user_message = request.data.get("message")
            if not user_message:
                return Response({"error": "Message is required"}, status=400)

            session_id = _ensure_session(request.data.get("session_id"), mode)
            Message.objects.create(role="user", content=user_message,
                                   session_id=session_id, mode=mode)
            _update_title_if_empty(session_id, user_message)

            # short history
            history_qs = (Message.objects
                          .filter(session_id=session_id, mode=mode)
                          .order_by("-timestamp")[:10][::-1])
            messages = [{"role": m.role, "content": m.content} for m in history_qs]

            def _call():
                if mode == "uncensored":
                    return _uncensored_chat_reply(messages)
                return _mistral_chat_reply(messages)

            # ✅ perform call with small backoff + proper status mapping
            result = _with_retries(_call, max_attempts=2)

            # If result is already a DRF Response (e.g., 429), just return it
            if isinstance(result, Response):
                return result

            reply = result
            Message.objects.create(role="assistant", content=reply,
                                   session_id=session_id, mode=mode)

            # include current title
            session = ChatSession.objects.get(session_id=session_id)
            return Response({
                "response": reply,
                "session_id": session_id,
                "title": session.title or "New chat"
            })
        except Exception as e:
            # last-resort safety
            return Response({"error": f"Server error: {e}"}, status=500)


class ChatHistoryView(APIView):
    """
    GET /api/history/?session_id=...&mode=...
    returns: { history: [{role, content,, attachments}] }
    """
    def get(self, request):
        session_id = request.query_params.get("session_id")
        mode = request.query_params.get("mode", "regular")
        if not session_id:
            return Response({"error": "session_id required"}, status=400)

        messages = Message.objects.filter(session_id=session_id,mode=mode).order_by("timestamp")
        history = [{"role": m.role, "content": m.content, "attachments": getattr(m, "attachments",[]),"mode": getattr(m, "mode", "regular"),} for m in messages]
        return Response({"history": history})


@api_view(["GET"])
def list_sessions(request):
    """
    GET /api/sessions/?mode=optional
    returns: [{ session_id, title, mode, last_time }]
    """
    mode = request.query_params.get("mode")
    qs = ChatSession.objects.all()
    if mode:
        qs = qs.filter(mode=mode)

    last_map = Message.objects.values("session_id").annotate(last_time=Max("timestamp"))
    last_lookup = {row["session_id"]: row["last_time"] for row in last_map}

    data = []
    for s in qs:
        data.append({
            "session_id": s.session_id,
            "title": s.title or "New chat",
            "mode": s.mode,
            "last_time": last_lookup.get(s.session_id, s.created_at),
        })
    data.sort(key=lambda d: d["last_time"] or s.created_at, reverse=True)
    return Response(data)


@api_view(["DELETE"])
def delete_session(request, session_id):
    """
    DELETE /api/sessions/<session_id>/
    """
    Message.objects.filter(session_id=session_id).delete()
    ChatSession.objects.filter(session_id=session_id).delete()
    return Response({"deleted": session_id})


class OcrUploadView(APIView):
    """
    POST /api/ocr/    (multipart/form-data)
      file: image/pdf/txt
      session_id?: keep same OCR session
      mode: "ocr" (ignored if not provided)
    returns: { text, session_id }
    """
    def post(self, request):
        try:
            fileobj = request.FILES.get("file")
            if not fileobj:
                return Response({"error": "No file uploaded"}, status=400)

            # ensure an OCR session
            session_id = _ensure_session(request.data.get("session_id"), "ocr")

            # Save temp file
            if isinstance(fileobj, InMemoryUploadedFile):
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    for chunk in fileobj.chunks():
                        tmp.write(chunk)
                    temp_path = tmp.name
            elif isinstance(fileobj, TemporaryUploadedFile):
                temp_path = fileobj.temporary_file_path()
            else:
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    for chunk in fileobj.chunks():
                        tmp.write(chunk)
                    temp_path = tmp.name

            # MIME hint
            mime = fileobj.content_type or None

            if not GOOGLE_API_KEY:
                return Response({"error": "GOOGLE_API_KEY not configured on server"}, status=500)

            extracted_text = _gemini_extract_text_from_file(temp_path, mime_type=mime)

            # Store the extracted text as a 'system' message in OCR mode
            Message.objects.create(
                role="system",
                content=extracted_text,
                session_id=session_id,
                mode="ocr"
            )

            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

            return Response({"text": extracted_text, "session_id": session_id})
        except Exception as e:
            return Response({"error": f"OCR server error: {e}"}, status=500)


class OcrQaView(APIView):
    """
    POST /api/ocr-qa/
      JSON: { session_id?: string, question: string, mode: "ocr" }
    Behavior:
      - If the session has OCR text (latest system msg), answer ONLY from that text.
      - If no OCR text yet, answer the question generally (no doc context).
    returns: { answer, session_id, source: "document"|"general" }
    """
    def post(self, request):
        try:
            question = (request.data.get("question") or "").strip()
            session_id = _ensure_session(request.data.get("session_id"), "ocr")

            if not question:
                return Response({"error": "question is required"}, status=400)

            if not GOOGLE_API_KEY:
                return Response({"error": "GOOGLE_API_KEY not configured on server"}, status=500)

            # Try to find the latest OCR text for this session
            ocr_msg = (
                Message.objects.filter(session_id=session_id, mode="ocr", role="system")
                .order_by("-timestamp")
                .first()
            )

            model = genai.GenerativeModel(GEMINI_TEXT_MODEL)

            if ocr_msg:
                # Answer strictly from the document text
                prompt = (
                    "You are given the raw text extracted from a document.\n"
                    "Answer the user's question using ONLY this text. "
                    "If the answer is not in the text, say 'Not found in the document.'\n\n"
                    f"--- DOCUMENT TEXT START ---\n{ocr_msg.content}\n--- DOCUMENT TEXT END ---\n\n"
                    f"User question: {question}\n"
                )
                source = "document"
            else:
                # No OCR uploaded yet -> general answer
                prompt = (
                    "Answer the user's question helpfully and concisely.\n\n"
                    f"User question: {question}\n"
                )
                source = "general"

            resp = model.generate_content(prompt)
            answer = (resp.text or "").strip()

            # Save Q/A in OCR session history so UI shows it
            Message.objects.create(role="user", content=question, session_id=session_id, mode="ocr")
            Message.objects.create(role="assistant", content=answer, session_id=session_id, mode="ocr")

            return Response({"answer": answer, "session_id": session_id, "source": source})
        except Exception as e:
            return Response({"error": f"OCR-QA server error: {e}"}, status=500)


import os
import uuid
import tempfile

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from django.core.files.base import ContentFile

from .models import Message
from .utils import _ensure_session, _update_title_if_empty  # adjust if needed

import google.generativeai as genai
import cloudinary.uploader


@csrf_exempt
@require_POST
def gemini_with_images(request):
    try:
        # -----------------------------
        # Basic request data
        # -----------------------------
        message = (request.POST.get("message") or "").strip() or "Analyze these images"
        session_id = request.POST.get("session_id")
        mode = request.POST.get("mode", "ocr")

        # Ensure session exists
        session_id = _ensure_session(session_id, mode)

        # -----------------------------
        # Images (max 4)
        # -----------------------------
        images = request.FILES.getlist("images")[:4]
        if not images:
            return JsonResponse({"error": "No images provided"}, status=400)

        saved_attachments = []      # sent to frontend + stored in DB
        uploads_for_gemini = []     # Gemini file handles

        model = genai.GenerativeModel("gemini-2.5-flash")

        for image_file in images:
            # Read image once
            data = image_file.read()
            ext = os.path.splitext(image_file.name)[1] or ".png"

            # -----------------------------
            # ✅ Upload to Cloudinary (IMPORTANT)
            # -----------------------------
            upload_result = cloudinary.uploader.upload(
                data,
                folder="uploads",
                resource_type="image",
            )

            cloudinary_url = upload_result["secure_url"]  # FULL HTTPS URL

            saved_attachments.append({
                "url": cloudinary_url,  # ✅ THIS FIXES YOUR 404
                "name": image_file.name,
                "mime": image_file.content_type or "application/octet-stream",
            })

            # -----------------------------
            # Gemini upload (temp file)
            # -----------------------------
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(data)
                tmp_path = tmp.name

            uploaded = genai.upload_file(tmp_path)
            uploads_for_gemini.append(uploaded)

            os.unlink(tmp_path)

        # -----------------------------
        # Ask Gemini
        # -----------------------------
        response = model.generate_content([message, *uploads_for_gemini])
        answer_text = (getattr(response, "text", "") or "").strip()

        # -----------------------------
        # Save messages
        # -----------------------------
        Message.objects.create(
            role="user",
            content=message,
            session_id=session_id,
            mode=mode,
            attachments=saved_attachments,
        )

        Message.objects.create(
            role="assistant",
            content=answer_text,
            session_id=session_id,
            mode=mode,
            attachments=[],
        )

        _update_title_if_empty(session_id, message)

        # -----------------------------
        # Response to frontend
        # -----------------------------
        return JsonResponse({
            "response": answer_text,
            "session_id": session_id,
            "attachments": saved_attachments,
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

    
from rest_framework.decorators import api_view

@api_view(["PUT"])
def rename_session(request, session_id):
    """PUT /api/sessions/<session_id>/  {title: "..."}"""
    try:
        cs = ChatSession.objects.get(session_id=session_id)
        new_title = request.data.get("title")
        if not new_title:
            return Response({"error": "Title required"}, status=400)
        cs.title = new_title
        cs.save(update_fields=["title", "updated_at"])
        return Response({"session_id": cs.session_id, "title": cs.title})
    except ChatSession.DoesNotExist:
        return Response({"error": "Not found"}, status=404)
