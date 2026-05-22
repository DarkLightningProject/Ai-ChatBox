# chat/utils.py
import uuid
from typing import Optional

from django.core.exceptions import PermissionDenied
from django.utils.text import Truncator

from .models import ChatSession

def _new_session_id(prefix=""):
    sid = str(uuid.uuid4())[:8]
    return f"{prefix}{sid}" if prefix else sid

def _ensure_session(session_id: Optional[str], mode: str, user=None) -> str:
    # ---------------------------
    # CASE 1: Existing session
    # ---------------------------
    if session_id:
        try:
            session = ChatSession.objects.get(session_id=session_id)
        except ChatSession.DoesNotExist:
            raise PermissionDenied("Session does not exist")

        if user and session.user and session.user != user:
            raise PermissionDenied("You do not own this session")

        return session.session_id

    # ---------------------------
    # CASE 2: Create new session
    # ---------------------------
    prefix = (
        "uncensored-" if mode == "uncensored"
        else "ocr-" if mode == "ocr"
        else "debugger-" if mode == "multi_debugger"
        else ""
    )

    new_sid = _new_session_id(prefix)

    ChatSession.objects.create(
        session_id=new_sid,
        mode=mode,
        user=user
    )

    return new_sid

def _update_title_if_empty(session_id, user_text):
    cs = ChatSession.objects.filter(session_id=session_id).first()
    if cs and not cs.title:
        cs.title = Truncator(user_text).words(6, truncate="…")
        cs.save(update_fields=["title"])
