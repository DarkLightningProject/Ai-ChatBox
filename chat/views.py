


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
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from openai import APIStatusError, APIError
from django.utils.decorators import method_decorator
from .models import Message, ChatSession
import google.generativeai as genai
from openai import OpenAI as OpenAIClient
from cloudinary.utils import cloudinary_url
from rest_framework.permissions import IsAuthenticated
from typing import Optional
from django.core.exceptions import PermissionDenied
 
# ================================
# Clients & Model IDs
# ================================

# --- Mistral for REGULAR mode ---
import os

print("🔎 OPENROUTER_API_KEY exists:", bool(os.getenv("OPENROUTER_API_KEY")))
print("🔎 FRONTEND_URL:", os.getenv("FRONTEND_URL"))
print("🔎 UNCENSORED_MODEL:", os.getenv("UNCENSORED_MODEL"))
print("🔎 get_uncensored_client called, key exists:", bool(os.getenv("OPENROUTER_API_KEY")))

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_BASE_URL = os.getenv("MISTRAL_BASE_URL")
REGULAR_MODEL = os.getenv("MISTRAL_MODEL")

mistral_client = OpenAIClient(
    api_key=MISTRAL_API_KEY,
    base_url=MISTRAL_BASE_URL,
)

# --- OpenRouter for UNCENSORED mode ---
import os
from openai import OpenAI as OpenAIClient

# =========================
# Environment Variables
# =========================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

UNCENSORED_MODEL = os.getenv(
    "UNCENSORED_MODEL",
    "cognitivecomputations/dolphin-mistral-24b-venice-edition"
)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# =========================
# Safety Check
# =========================
if not OPENROUTER_API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY is not set")

# =========================
# OpenRouter Client
# =========================
def get_uncensored_client():
    api_key = os.getenv("OPENROUTER_API_KEY")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY missing at runtime")

    return OpenAIClient(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "Referer": frontend_url,   # REQUIRED by OpenRouter
            "X-Title": "AI Chatbox",
        },
    )
# =========================
# Chat Function
# =========================
def uncensored_chat(messages):
    try:
        client = get_uncensored_client()

        response = client.chat.completions.create(
            model=os.getenv(
                "UNCENSORED_MODEL",
                "cognitivecomputations/dolphin-mistral-24b-venice-edition"
            ),
            messages=messages,
            temperature=1.1,
            top_p=0.95,
            frequency_penalty=0.2,
            max_tokens=2048,
            timeout=90,
        )

        return response.choices[0].message.content

    except Exception as e:
        print("❌ Uncensored chat error:", repr(e))
        return "⚠️ Uncensored model is temporarily unavailable."
# --- Gemini ONLY for OCR flows ---

def chat_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    data = json.loads(request.body)
    messages = data.get("messages", [])

    reply = uncensored_chat(messages)

    return JsonResponse({"reply": reply})

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL")
GEMINI_FILE_MODEL = os.getenv("GEMINI_FILE_MODEL")

# ===========
# Helpers
# ===========

def _new_session_id(prefix: str = "") -> str:
    sid = str(uuid.uuid4())[:8]
    return f"{prefix}{sid}" if prefix else sid


def _ensure_session(session_id: Optional[str], mode: str, user=None) -> str:
    """
    Ensures a session exists and belongs to the given user.
    Creates a new session if session_id is None.
    """

    # ---------------------------
    # CASE 1: Existing session
    # ---------------------------
    if session_id:
        try:
            session = ChatSession.objects.get(session_id=session_id)
        except ChatSession.DoesNotExist:
            raise PermissionDenied("Session does not exist")

        # 🔐 Ownership check (CRITICAL)
        if session.user != user:
            raise PermissionDenied("You do not own this session")

        return session.session_id

    # ---------------------------
    # CASE 2: Create new session
    # ---------------------------
    prefix = (
        "uncensored-" if mode == "uncensored"
        else "ocr-" if mode == "ocr"
        else ""
    )

    new_sid = _new_session_id(prefix)

    ChatSession.objects.create(
        session_id=new_sid,
        mode=mode,
        user=user
    )

    return new_sid

    ChatSession.objects.create(
        session_id=new_sid,
        mode=mode,
        user=user
    )
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

from .authentication import CsrfExemptSessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def create_session(request):
    if not request.user.is_authenticated:
        return Response({"error": "Unauthorized"}, status=401)

    mode = request.data.get("mode", "regular")
    sid = _ensure_session(None, mode, user=request.user)

    return Response({
        "session_id": sid,
        "title": "New chat",
        "mode": mode
    }, status=201)


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

from .authentication import CsrfExemptSessionAuthentication
class ChatView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            mode = request.data.get("mode", "regular")
            user_message = request.data.get("message")

            if not user_message:
                return Response(
                    {"error": "Message is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            incoming_session_id = request.data.get("session_id")

            # ✅ STEP 1: validate or create session safely
            if incoming_session_id:
                session = ChatSession.objects.filter(
                    session_id=incoming_session_id,
                    user=request.user
                ).first()

                if not session:
                    return Response(
                        {"error": "Session not found"},
                        status=status.HTTP_404_NOT_FOUND
                    )

                session_id = session.session_id
            else:
                # create a new session for this user
                session_id = _ensure_session(None, mode, user=request.user)
                session = ChatSession.objects.get(session_id=session_id)

            # ✅ STEP 2: save user message
            Message.objects.create(
                role="user",
                content=user_message,
                session_id=session_id,
                mode=mode,
            )

            _update_title_if_empty(session_id, user_message)

            # ✅ STEP 3: short history (unchanged logic)
            history_qs = (
                Message.objects
                .filter(session_id=session_id, mode=mode)
                .order_by("-timestamp")[:10][::-1]
            )

            messages = [
                {"role": m.role, "content": m.content}
                for m in history_qs
            ]

            def _call():
                if mode == "uncensored":
                    return _uncensored_chat_reply(messages)
                return _mistral_chat_reply(messages)

            result = _with_retries(_call, max_attempts=2)

            if isinstance(result, Response):
                return result

            reply = result

            Message.objects.create(
                role="assistant",
                content=reply,
                session_id=session_id,
                mode=mode,
            )

            return Response({
                "response": reply,
                "session_id": session_id,
                "title": session.title or "New chat",
            })

        except Exception as e:
            return Response(
                {"error": f"Server error: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ChatHistoryView(APIView):
    """
    GET /api/history/?session_id=...&mode=...
    returns: { history: [{role, content, attachments, mode}] }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        session_id = request.query_params.get("session_id")
        mode = request.query_params.get("mode", "regular")

        if not session_id:
            return Response(
                {"error": "session_id required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ SECURITY CHECK (does NOT affect old data)
        session = ChatSession.objects.filter(
            session_id=session_id,
            user=request.user
        ).first()

        if not session:
            return Response(
                {"error": "Not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # ✅ Existing logic preserved
        messages = Message.objects.filter(
            session_id=session_id,
            mode=mode
        ).order_by("timestamp")

        history = [
            {
                "role": m.role,
                "content": m.content,
                "attachments": m.attachments or [],
                "mode": m.mode,
            }
            for m in messages
        ]

        return Response({"history": history})


@api_view(["GET"])
def list_sessions(request):
    """
    GET /api/sessions/?mode=optional
    returns: [{ session_id, title, mode, last_time }]
    """
    mode = request.query_params.get("mode")
    qs = ChatSession.objects.filter(user=request.user)

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


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .authentication import CsrfExemptSessionAuthentication
from .models import ChatSession, Message
from .authentication import CsrfExemptSessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import ChatSession, Message


@api_view(["DELETE"])
@authentication_classes([CsrfExemptSessionAuthentication])

@permission_classes([IsAuthenticated])
def delete_session(request, session_id):
    """
    DELETE /api/sessions/<session_id>/
    Only deletes sessions owned by the logged-in user
    """
    session = ChatSession.objects.filter(
        session_id=session_id,
        user=request.user
    ).first()

    if not session:
        return Response(
            {"error": "Session not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    # delete messages first
    Message.objects.filter(session_id=session_id).delete()

    # delete session
    session.delete()

    return Response(
        {"deleted": session_id},
        status=status.HTTP_200_OK
    )



from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
import tempfile, os


class OcrUploadView(APIView):
    permission_classes = [IsAuthenticated]

    """
    POST /api/ocr/
    file: image/pdf/txt
    session_id?: keep same OCR session
    returns: { text, session_id }
    """

    def post(self, request):
        try:
            fileobj = request.FILES.get("file")
            if not fileobj:
                return Response(
                    {"error": "No file uploaded"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            incoming_session_id = request.data.get("session_id")

            # 🔐 Validate or create session (USER-SCOPED)
            if incoming_session_id:
                session = ChatSession.objects.filter(
                    session_id=incoming_session_id,
                    user=request.user,
                    mode="ocr"
                ).first()

                if not session:
                    return Response(
                        {"error": "Session not found"},
                        status=status.HTTP_404_NOT_FOUND
                    )

                session_id = session.session_id
            else:
                session_id = _ensure_session(None, "ocr", user=request.user)

            # ---------- Save temp file ----------
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

            mime = fileobj.content_type or None

            if not GOOGLE_API_KEY:
                return Response(
                    {"error": "GOOGLE_API_KEY not configured"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            extracted_text = _gemini_extract_text_from_file(
                temp_path,
                mime_type=mime
            )

            # ---------- Save OCR text ----------
            Message.objects.create(
                role="system",
                content=extracted_text,
                session_id=session_id,
                mode="ocr"
            )

            if os.path.exists(temp_path):
                os.unlink(temp_path)

            return Response(
                {
                    "text": extracted_text,
                    "session_id": session_id
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {"error": f"OCR server error: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status


class OcrQaView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    """
    POST /api/ocr-qa/
    JSON: { session_id?: string, question: string }
    returns: { answer, session_id, source }
    """

    def post(self, request):
        try:
            question = (request.data.get("question") or "").strip()
            incoming_session_id = request.data.get("session_id")

            if not question:
                return Response(
                    {"error": "question is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not GOOGLE_API_KEY:
                return Response(
                    {"error": "GOOGLE_API_KEY not configured"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # 🔐 Validate or create session (USER-SCOPED)
            if incoming_session_id:
                session = ChatSession.objects.filter(
                    session_id=incoming_session_id,
                    user=request.user,
                    mode="ocr"
                ).first()

                if not session:
                    return Response(
                        {"error": "Session not found"},
                        status=status.HTTP_404_NOT_FOUND
                    )

                session_id = session.session_id
            else:
                session_id = _ensure_session(None, "ocr", user=request.user)

            # ---------- Fetch latest OCR text ----------
            ocr_msg = (
                Message.objects.filter(
                    session_id=session_id,
                    mode="ocr",
                    role="system"
                )
                .order_by("-timestamp")
                .first()
            )

            model = genai.GenerativeModel(GEMINI_TEXT_MODEL)

            if ocr_msg:
                prompt = (
                    "You are given the raw text extracted from a document.\n"
                    "Answer the user's question using ONLY this text. "
                    "If the answer is not in the text, say 'Not found in the document.'\n\n"
                    f"--- DOCUMENT TEXT START ---\n{ocr_msg.content}\n"
                    f"--- DOCUMENT TEXT END ---\n\n"
                    f"User question: {question}\n"
                )
                source = "document"
            else:
                prompt = (
                    "Answer the user's question helpfully and concisely.\n\n"
                    f"User question: {question}\n"
                )
                source = "general"

            resp = model.generate_content(prompt)
            answer = (resp.text or "").strip()

            # ---------- Save Q/A ----------
            Message.objects.create(
                role="user",
                content=question,
                session_id=session_id,
                mode="ocr"
            )

            Message.objects.create(
                role="assistant",
                content=answer,
                session_id=session_id,
                mode="ocr"
            )

            return Response(
                {
                    "answer": answer,
                    "session_id": session_id,
                    "source": source
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {"error": f"OCR-QA server error: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



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
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated

@api_view(["PUT"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
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
