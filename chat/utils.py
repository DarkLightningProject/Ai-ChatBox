# chat/utils.py
import uuid
from django.utils.text import Truncator
from .models import ChatSession

def _new_session_id(prefix=""):
    sid = str(uuid.uuid4())[:8]
    return f"{prefix}{sid}" if prefix else sid

def _ensure_session(session_id, mode):
    if session_id:
        ChatSession.objects.get_or_create(
            session_id=session_id,
            defaults={"mode": mode}
        )
        return session_id

    prefix = "ocr-" if mode == "ocr" else "uncensored-" if mode == "uncensored" else ""
    new_sid = _new_session_id(prefix)
    ChatSession.objects.create(session_id=new_sid, mode=mode)
    return new_sid

def _update_title_if_empty(session_id, user_text):
    cs = ChatSession.objects.filter(session_id=session_id).first()
    if cs and not cs.title:
        cs.title = Truncator(user_text).words(6, truncate="…")
        cs.save(update_fields=["title"])
