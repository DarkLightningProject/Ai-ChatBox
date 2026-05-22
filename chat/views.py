import concurrent.futures
import logging
import math
import os
import struct
import tempfile
import time
from typing import Optional

logger = logging.getLogger(__name__)

import cloudinary.uploader
import google.generativeai as genai
from openai import OpenAI as OpenAIClient, APIStatusError, APIError

from django.core.files.uploadedfile import TemporaryUploadedFile
from django.db import transaction
from django.db.models import Max
from django.utils import timezone as tz

from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from accounts.models import Profile as UserProfile


def _ban_matches(ban, feature, tier):
    """Return True if this FeatureBan row applies to the given feature/tier."""
    if ban.feature == "full_account":
        return True
    if ban.feature == feature:
        return True
    return (
        ban.feature == "multi_debugger_premium"
        and feature == "multi_debugger"
        and tier == "premium"
    )


_BAN_CACHE_TTL = 60  # seconds — max lag before a new ban is enforced


def _invalidate_ban_cache(user_id: int) -> None:
    """Call this whenever a ban is applied or removed for a user."""
    from django.core.cache import cache
    cache.delete(f"bans:{user_id}")


def _check_feature_ban(user, feature, tier=None):
    """
    Returns a 403 Response if the user is banned from `feature` (optionally `tier`),
    otherwise None.

    Ban rows are cached per-user for _BAN_CACHE_TTL seconds to avoid a DB hit
    on every single chat message. Expired bans are cleaned from the DB lazily
    when the cache entry expires and a fresh DB read is triggered.

    feature: "regular" | "uncensored" | "ocr" | "multi_debugger"
    tier:    "free" | "premium"  (only relevant for multi_debugger)
    """
    from django.core.cache import cache

    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return None

    cache_key = f"bans:{user.id}"
    cached    = cache.get(cache_key)

    if cached is None:
        # Cache miss — read from DB, auto-delete expired rows
        now     = tz.now()
        expired = []
        active  = []  # list of (feature, expires_at_iso_or_None, reason)

        for ban in profile.feature_bans.all():
            if ban.expires_at and now >= ban.expires_at:
                expired.append(ban.pk)
                continue
            active.append({
                "feature":    ban.feature,
                "expires_at": ban.expires_at.isoformat() if ban.expires_at else None,
                "reason":     ban.reason or "Violation of terms of service",
            })

        if expired:
            from accounts.models import FeatureBan as _FB
            _FB.objects.filter(pk__in=expired).delete()

        cache.set(cache_key, active, timeout=_BAN_CACHE_TTL)
        cached = active

    # Check cached ban list against requested feature/tier
    now = tz.now()
    for ban in cached:
        # Skip if this cached entry has since expired (fine-grained within TTL window)
        if ban["expires_at"] and tz.datetime.fromisoformat(ban["expires_at"]) <= now:
            continue

        f = ban["feature"]
        if f == "full_account":
            pass  # matches everything
        elif f == feature:
            pass
        elif (f == "multi_debugger_premium"
              and feature == "multi_debugger"
              and tier == "premium"):
            pass
        else:
            continue  # this ban doesn't apply

        return Response(
            {
                "error":          "banned",
                "feature":        f,
                "ban_expires_at": ban["expires_at"],
                "ban_reason":     ban["reason"],
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    return None


def _check_email_verified(user):
    """
    Returns a 403 Response if the user's email is not verified, otherwise None.
    A missing Profile is treated as unverified.
    """
    try:
        if not user.profile.email_verified:
            return Response(
                {"error": "email_not_verified",
                 "detail": "Please verify your email address before using the chat."},
                status=status.HTTP_403_FORBIDDEN,
            )
    except UserProfile.DoesNotExist:
        return Response(
            {"error": "email_not_verified",
             "detail": "Please verify your email address before using the chat."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


# ================================
# Per-user LLM throttle classes
# Rates are configured in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
# ================================

class _DebugBypassMixin:
    """Skip throttling entirely when DEBUG=True (local dev only)."""
    def allow_request(self, request, view):
        if os.getenv("DEBUG", "").lower() in ("true", "1", "yes"):
            return True
        return super().allow_request(request, view)

class _LLMChatThrottle(_DebugBypassMixin, UserRateThrottle):
    scope = "llm_chat"   # 60/hour — regular & uncensored chat

class _LLMOcrThrottle(_DebugBypassMixin, UserRateThrottle):
    scope = "llm_ocr"    # 30/hour — OCR Q&A and image analysis

class _LLMDebugThrottle(_DebugBypassMixin, UserRateThrottle):
    scope = "llm_debug"  # 20/hour — multi-debugger (most expensive)

from .authentication import CsrfExemptSessionAuthentication
from .models import Message, ChatSession
from .utils import _ensure_session, _update_title_if_empty

# Shared constants used across views
_SESSION_NOT_FOUND = "Session not found"
_NEW_CHAT_TITLE = "New chat"
_SERVER_ERROR = "An unexpected server error occurred. Please try again."
_VALID_MODES = {"regular", "uncensored", "ocr", "multi_debugger"}

# ================================
# LLM Client Configuration
# ================================

# ── Env-var loader with early failure ────────────────────────────────────────
def _require_env(name: str) -> str:
    """Return env var or raise at startup with a clear message."""
    val = os.getenv(name)
    if not val:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Check your .env file."
        )
    return val


# Mistral — used for regular (non-uncensored) chat
MISTRAL_API_KEY  = _require_env("MISTRAL_API_KEY")
MISTRAL_BASE_URL = _require_env("MISTRAL_BASE_URL")
REGULAR_MODEL    = _require_env("MISTRAL_MODEL")

mistral_client = OpenAIClient(
    api_key=MISTRAL_API_KEY,
    base_url=MISTRAL_BASE_URL,
)

# OpenRouter — used for uncensored chat mode
UNCENSORED_MODEL = os.getenv(
    "UNCENSORED_MODEL",
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free"
)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Google Gemini — used exclusively for OCR (file text extraction) and image analysis
GOOGLE_API_KEY    = _require_env("GOOGLE_API_KEY")
GEMINI_TEXT_MODEL = _require_env("GEMINI_TEXT_MODEL")
GEMINI_FILE_MODEL = _require_env("GEMINI_FILE_MODEL")

genai.configure(api_key=GOOGLE_API_KEY)

# ================================
# Multi-Debugger Configuration
# ================================

OPENAI_API_KEY    = _require_env("OPENAI_API_KEY")
ANTHROPIC_API_KEY = _require_env("ANTHROPIC_API_KEY")

# Premium tier models
GEMINI_DEBUG_MODEL = os.getenv("GEMINI_DEBUG_MODEL", "gemini-2.5-pro")
DEBUG_SYNTAX_MODEL = os.getenv("DEBUG_SYNTAX_MODEL", "gpt-4.1")
DEBUG_PERF_MODEL   = os.getenv("DEBUG_PERF_MODEL",   "claude-opus-4-5")
DEBUG_SYNTH_MODEL  = os.getenv("DEBUG_SYNTH_MODEL",  "claude-sonnet-4-5")

GEMINI_FREE_MODEL = os.getenv("GEMINI_FREE_MODEL", "gemini-2.5-flash")

# ================================
# Per-model Pricing & Usage Tracking
# ================================

# Cost per 1 million tokens (USD) — first substring match wins
# Sources: anthropic.com/pricing, ai.google.dev/gemini-api/docs/pricing,
#          openai.com/api/pricing, docs.mistral.ai, openrouter.ai
_MODEL_PRICING = [
    ("gpt-4.1-mini",      0.40,  1.60),   # OpenAI GPT-4.1 mini
    ("gpt-4.1",           2.00,  8.00),   # OpenAI GPT-4.1
    ("gpt-4o-mini",       0.15,  0.60),   # OpenAI GPT-4o mini
    ("gpt-4o",            5.00, 15.00),   # OpenAI GPT-4o
    ("claude-opus-4-5",   5.00, 25.00),   # Anthropic Claude Opus 4.5
    ("claude-sonnet-4-5", 3.00, 15.00),   # Anthropic Claude Sonnet 4.5
    ("claude-haiku",      0.80,  4.00),   # Anthropic Claude Haiku 3.5
    ("gemini-2.5-pro",    1.25, 10.00),   # Google Gemini 2.5 Pro (≤200k ctx)
    ("gemini-2.5-flash",  0.30,  2.50),   # Google Gemini 2.5 Flash
    ("gemini-flash",      0.30,  2.50),   # Google Gemini Flash (generic)
    ("gemini-pro",        1.25, 10.00),   # Google Gemini Pro (generic)
    ("dolphin",           0.00,  0.00),   # Free via OpenRouter
    ("mistral",           0.10,  0.30),   # Mistral Small
]


def _get_model_pricing(model_name: str) -> dict:
    lower = (model_name or "").lower()
    for key, inp, out in _MODEL_PRICING:
        if key in lower:
            return {"input": inp, "output": out}
    return {"input": 0.10, "output": 0.30}


def _record_usage(user, model_name: str, input_tokens: int, output_tokens: int) -> None:
    """Persist one API call's token counts to the DB (best-effort, never raises)."""
    try:
        from .models import ModelUsage
        ModelUsage.objects.create(
            user=user,
            model_name=model_name,
            input_tokens=max(0, input_tokens or 0),
            output_tokens=max(0, output_tokens or 0),
        )
    except Exception:
        logger.exception("Failed to record token usage")


# ================================
# Gemini Image Token Estimation
# ================================

_GEMINI_TOKENS_PER_TILE = 258
_GEMINI_SMALL_DIM = 384   # both dims must be ≤ this to stay in the 258-token tier


def _gemini_image_tokens(width: int, height: int) -> int:
    """
    Official Gemini tiling formula (source: ai.google.dev/gemini-api/docs/vision).
    Any image where both dimensions ≤ 384 px costs exactly 258 tokens.
    Larger images are sliced into tiles of ~768 px; each tile costs 258 tokens.

    Example: 960×540  →  crop_unit=360, 3×2 tiles = 6 × 258 = 1 548 tokens
    """
    if width <= _GEMINI_SMALL_DIM and height <= _GEMINI_SMALL_DIM:
        return _GEMINI_TOKENS_PER_TILE
    crop_unit = int(min(width, height) / 1.5)
    if crop_unit == 0:
        return _GEMINI_TOKENS_PER_TILE
    tiles_x = math.ceil(width  / crop_unit)
    tiles_y = math.ceil(height / crop_unit)
    return tiles_x * tiles_y * _GEMINI_TOKENS_PER_TILE


def _read_image_dimensions(data: bytes):
    """
    Return (width, height) from raw image bytes — no PIL required.
    Supports PNG (exact), JPEG (SOF marker scan), WebP VP8/VP8L.
    Returns None if the format is unrecognised or the header is truncated.
    """
    try:
        # ── PNG: IHDR chunk starts at byte 16 (4 B width + 4 B height, big-endian) ──
        if data[:8] == b'\x89PNG\r\n\x1a\n' and len(data) >= 24:
            w, h = struct.unpack('>II', data[16:24])
            return w, h

        # ── WebP: RIFF....WEBP ────────────────────────────────────────────────────────
        if data[:4] == b'RIFF' and data[8:12] == b'WEBP' and len(data) >= 30:
            chunk = data[12:16]
            if chunk == b'VP8 ':                              # lossy
                w = struct.unpack_from('<H', data, 26)[0] & 0x3fff
                h = struct.unpack_from('<H', data, 28)[0] & 0x3fff
                return w, h
            if chunk == b'VP8L' and len(data) >= 25:         # lossless
                bits = struct.unpack_from('<I', data, 21)[0]
                w = 1 + (bits & 0x3fff)
                h = 1 + ((bits >> 14) & 0x3fff)
                return w, h

        # ── JPEG: scan for SOF0/SOF1/SOF2/SOF3 marker ────────────────────────────────
        if data[:2] == b'\xff\xd8':
            offset = 2
            while offset + 4 <= len(data):
                if data[offset] != 0xff:
                    break
                marker = data[offset + 1]
                if marker in (0xc0, 0xc1, 0xc2, 0xc3):      # SOFn with dimensions
                    if offset + 9 <= len(data):
                        h = struct.unpack_from('>H', data, offset + 5)[0]
                        w = struct.unpack_from('>H', data, offset + 7)[0]
                        return w, h
                    break
                if marker in (0xd8, 0xd9):                   # SOI / EOI — no length
                    offset += 2
                    continue
                seg_len = struct.unpack_from('>H', data, offset + 2)[0]
                offset += 2 + seg_len

    except Exception:
        pass
    return None


_LOGIC_ANALYST_PROMPT = (
    "You are the Logic Analyst in a 3-specialist debugging pipeline. "
    "A Synthesizer will combine your findings with a Syntax Inspector and a Performance & Security Auditor "
    "to produce ONE unified fix. Your role is DIAGNOSIS ONLY — do not write corrected code or attempt a full fix. "
    "The Synthesizer owns the solution.\n\n"
    "Analyze for:\n"
    "- Incorrect algorithms, wrong logic flow\n"
    "- Flawed conditions (inverted checks, off-by-one, missing guards)\n"
    "- Unhandled edge cases (null, empty input, boundary values, overflow)\n"
    "- Incorrect data flow, state mutations, control flow issues\n"
    "- Faulty assumptions about inputs or system state\n\n"
    "IMPORTANT: If the input is a greeting, question, or does not contain actual code or a "
    "bug description, respond with ONLY this exact token and nothing else: [NO_CODE_PROVIDED]\n\n"
    "Structure your response EXACTLY as:\n"
    "### 🔍 Logical Issues Found\n"
    "[Each issue: exact location → what is wrong → consequence if unfixed]\n\n"
    "### 🧩 Root Cause Analysis\n"
    "[Underlying reason for each issue — be precise]\n\n"
    "### 🔗 Cross-Domain Flags\n"
    "[Note any issues here that also likely affect syntax/runtime correctness or security — "
    "flag them so the Synthesizer can connect the dots across agents]"
)

_SYNTAX_INSPECTOR_PROMPT = (
    "You are the Syntax & Runtime Inspector in a 3-specialist debugging pipeline. "
    "A Synthesizer will combine your findings with a Logic Analyst and a Performance & Security Auditor "
    "to produce ONE unified fix. Your role is DIAGNOSIS ONLY — do not write corrected code or attempt a full fix. "
    "The Synthesizer owns the solution.\n\n"
    "Analyze for:\n"
    "- Syntax errors, typos, missing tokens\n"
    "- Type errors and type mismatches\n"
    "- Undefined variables, missing imports, wrong references\n"
    "- Runtime exceptions (null pointer, index out of bounds, division by zero)\n"
    "- Language-specific gotchas, deprecated APIs, anti-patterns\n\n"
    "IMPORTANT: If the input is a greeting, question, or does not contain actual code or a "
    "bug description, respond with ONLY this exact token and nothing else: [NO_CODE_PROVIDED]\n\n"
    "Structure your response EXACTLY as:\n"
    "### 🐛 Syntax & Runtime Issues Found\n"
    "[Each issue: exact location → error type → consequence if unfixed]\n\n"
    "### ⚠️ Error Classification\n"
    "[Each issue: compile-time / runtime / logic-runtime]\n\n"
    "### 🔗 Cross-Domain Flags\n"
    "[Note any issues that likely stem from a logic flaw or create a security risk — "
    "flag them so the Synthesizer can connect the dots across agents]"
)

_PERF_SECURITY_PROMPT = (
    "You are the Performance & Security Auditor in a 3-specialist debugging pipeline. "
    "A Synthesizer will combine your findings with a Logic Analyst and a Syntax Inspector "
    "to produce ONE unified fix. Your role is DIAGNOSIS ONLY — do not write corrected code or attempt a full fix. "
    "The Synthesizer owns the solution.\n\n"
    "Analyze for:\n"
    "- Performance bottlenecks (unnecessary loops, O(n²) where O(n) works, redundant queries, N+1)\n"
    "- Memory inefficiencies (leaks, unnecessary allocations, large retained objects)\n"
    "- Security vulnerabilities (SQL injection, XSS, CSRF, auth bypass, insecure deserialization, hardcoded secrets)\n"
    "- Race conditions and concurrency bugs\n"
    "- Use of deprecated or unsafe functions\n\n"
    "IMPORTANT: If the input is a greeting, question, or does not contain actual code or a "
    "bug description, respond with ONLY this exact token and nothing else: [NO_CODE_PROVIDED]\n\n"
    "Structure your response EXACTLY as:\n"
    "### ⚡ Performance Issues\n"
    "[Each issue: location → impact assessment → severity: Low/Medium/High/Critical]\n\n"
    "### 🔐 Security Vulnerabilities\n"
    "[Each issue: location → vulnerability type → severity: Low/Medium/High/Critical → exploit scenario]\n\n"
    "### 🔗 Cross-Domain Flags\n"
    "[Note any issues that likely originate from a logic error or syntax mistake — "
    "flag them so the Synthesizer can connect the dots across agents]"
)

_SYNTHESIZER_PROMPT = (
    "You are the Synthesizer — the ONLY agent in this pipeline that writes code fixes. "
    "Three specialist agents have independently diagnosed the code and flagged their findings. "
    "They do NOT fix the code — you do.\n\n"
    "You received:\n"
    "1. Logic Analyst — logical/algorithmic issues and cross-domain flags\n"
    "2. Syntax & Runtime Inspector — syntax/type/runtime issues and cross-domain flags\n"
    "3. Performance & Security Auditor — perf/security issues and cross-domain flags\n\n"
    "Your job:\n"
    "1. Build a UNIFIED ISSUE MAP — connect findings across agents where they share a root cause\n"
    "   (e.g., a logic flaw that causes both a runtime exception AND a security hole should be ONE entry)\n"
    "2. Resolve any CONTRADICTIONS between agents — pick the correct interpretation and explain why\n"
    "3. Prioritize: Critical > High > Medium > Low\n"
    "4. Write ONE complete, coherent, immediately-applicable fix that addresses ALL agents' findings together\n"
    "   — not three separate fixes patched together, but a single solution aware of all issues at once\n\n"
    "Structure your response EXACTLY as:\n"
    "## 🗺️ Unified Issue Map\n"
    "[Cross-referenced issue list — group related findings from different agents under one entry, "
    "note contradictions and how you resolved them, order by severity]\n\n"
    "## ✅ Complete Fix\n"
    "[Full corrected code or precise diff — this is the ONLY fix in the pipeline; make it complete, "
    "coherent, and correct. Explicitly address findings from all three agents.]\n\n"
    "## 📋 Why This Fix Works\n"
    "[Explain how the fix resolves each agent's findings — show the cross-agent coherence]\n\n"
    "## 🚀 Remaining Recommendations\n"
    "[Non-blocking improvements — do not include anything already fixed above]"
)


# ================================
# Multi-Debugger Agent Functions
# ================================

def _agent_logic_analyst(message: str, model: str = None) -> tuple:
    """Agent 1 — Logic Analyst: Google Gemini (free: Flash / premium: Pro).
    Returns (text, input_tokens, output_tokens)."""
    model = model or GEMINI_DEBUG_MODEL
    try:
        m = genai.GenerativeModel(model, system_instruction=_LOGIC_ANALYST_PROMPT)
        resp = m.generate_content(message)
        text = (resp.text or "").strip()
        _um = getattr(resp, 'usage_metadata', None)
        return (
            text,
            getattr(_um, 'prompt_token_count', 0) or 0,
            getattr(_um, 'candidates_token_count', 0) or 0,
        )
    except Exception as e:
        logger.exception("Multi-debug Agent 1 (Logic Analyst) failed")
        return f"[Logic Analyst unavailable: {str(e)[:300]}]", 0, 0


def _agent_syntax_inspector(message: str, model: str = None) -> tuple:
    """Agent 2 — Syntax & Runtime Inspector: OpenAI (premium: GPT-4.1).
    Returns (text, input_tokens, output_tokens)."""
    model = model or DEBUG_SYNTAX_MODEL
    try:
        if not OPENAI_API_KEY:
            return "[Syntax Inspector unavailable: OPENAI_API_KEY not configured]", 0, 0
        client = OpenAIClient(api_key=OPENAI_API_KEY)
        r = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYNTAX_INSPECTOR_PROMPT},
                {"role": "user",   "content": message},
            ],
            max_tokens=2048,
            timeout=90,
        )
        text = (r.choices[0].message.content or "").strip()
        u = getattr(r, 'usage', None)
        return text, getattr(u, 'prompt_tokens', 0) or 0, getattr(u, 'completion_tokens', 0) or 0
    except Exception as e:
        logger.exception("Multi-debug Agent 2 (Syntax Inspector) failed")
        return f"[Syntax Inspector unavailable: {str(e)[:300]}]", 0, 0


def _agent_mistral_logic_analyst(message: str) -> tuple:
    """Agent 1 (Free) — Logic Analyst using Mistral.
    Returns (text, input_tokens, output_tokens)."""
    try:
        r = mistral_client.chat.completions.create(
            model=REGULAR_MODEL,
            messages=[
                {"role": "system", "content": _LOGIC_ANALYST_PROMPT},
                {"role": "user",   "content": message},
            ],
            max_tokens=2048,
        )
        text = (r.choices[0].message.content or "").strip()
        u = getattr(r, 'usage', None)
        return text, getattr(u, 'prompt_tokens', 0) or 0, getattr(u, 'completion_tokens', 0) or 0
    except Exception as e:
        logger.exception("Multi-debug Agent 1 Free (Mistral Logic) failed")
        return f"[Logic Analyst unavailable: {str(e)[:300]}]", 0, 0


def _agent_mistral_syntax_inspector(message: str) -> tuple:
    """Agent 2 (Free) — Syntax & Runtime Inspector using Mistral.
    Returns (text, input_tokens, output_tokens)."""
    try:
        r = mistral_client.chat.completions.create(
            model=REGULAR_MODEL,
            messages=[
                {"role": "system", "content": _SYNTAX_INSPECTOR_PROMPT},
                {"role": "user",   "content": message},
            ],
            max_tokens=2048,
        )
        text = (r.choices[0].message.content or "").strip()
        u = getattr(r, 'usage', None)
        return text, getattr(u, 'prompt_tokens', 0) or 0, getattr(u, 'completion_tokens', 0) or 0
    except Exception as e:
        logger.exception("Multi-debug Agent 2 Free (Mistral Syntax) failed")
        return f"[Syntax Inspector unavailable: {str(e)[:300]}]", 0, 0


_GEMINI_FALLBACK_MARKER = "__GEMINI_UNAVAILABLE__\n"


def _agent_gemini_perf_security(message: str) -> tuple:
    """Agent 3 (Free) — Perf & Security Auditor.
    Primary: Gemini 2.5 Flash. Fallback: Mistral.
    Returns (text, input_tokens, output_tokens)."""
    try:
        m = genai.GenerativeModel(
            GEMINI_FREE_MODEL,
            system_instruction=_PERF_SECURITY_PROMPT,
        )
        resp = m.generate_content(message)
        text = (resp.text or "").strip()
        _um = getattr(resp, 'usage_metadata', None)
        return (
            text,
            getattr(_um, 'prompt_token_count', 0) or 0,
            getattr(_um, 'candidates_token_count', 0) or 0,
        )
    except Exception as e:
        err_str = str(e)
        logger.warning("Gemini quota hit for Agent 3, falling back to Mistral: %s", err_str[:120])
        try:
            r = mistral_client.chat.completions.create(
                model=REGULAR_MODEL,
                messages=[
                    {"role": "system", "content": _PERF_SECURITY_PROMPT},
                    {"role": "user",   "content": message},
                ],
                max_tokens=2048,
            )
            mistral_analysis = (r.choices[0].message.content or "").strip()
            u = getattr(r, 'usage', None)
            return (
                f"{_GEMINI_FALLBACK_MARKER}{mistral_analysis}",
                getattr(u, 'prompt_tokens', 0) or 0,
                getattr(u, 'completion_tokens', 0) or 0,
            )
        except Exception as e2:
            logger.exception("Multi-debug Agent 3 Free fallback (Mistral Perf) also failed")
            return f"[Perf & Security Auditor unavailable: {str(e2)[:300]}]", 0, 0


def _agent_mistral_synthesizer(original: str, logic: str, syntax: str, perf: str) -> tuple:
    """Agent 4 (Free) — Synthesizer using Mistral.
    Returns (text, input_tokens, output_tokens)."""
    combined = (
        f"## Original Code / Bug Description\n{original}\n\n"
        f"---\n## Diagnosis from Agent 1 — Logic Analyst\n{logic}\n\n"
        f"---\n## Diagnosis from Agent 2 — Syntax & Runtime Inspector\n{syntax}\n\n"
        f"---\n## Diagnosis from Agent 3 — Performance & Security Auditor\n{perf}\n\n"
        f"---\n"
        f"All three agents have completed their diagnosis. "
        f"Now build the unified issue map, resolve any conflicts between agents, "
        f"and produce the single complete fix."
    )
    try:
        r = mistral_client.chat.completions.create(
            model=REGULAR_MODEL,
            messages=[
                {"role": "system", "content": _SYNTHESIZER_PROMPT},
                {"role": "user",   "content": combined},
            ],
            max_tokens=4096,
        )
        text = (r.choices[0].message.content or "").strip()
        u = getattr(r, 'usage', None)
        return text, getattr(u, 'prompt_tokens', 0) or 0, getattr(u, 'completion_tokens', 0) or 0
    except Exception as e:
        logger.exception("Multi-debug Agent 4 Free (Mistral Synth) failed")
        return (
            f"[Synthesizer error: {str(e)[:300]}]\n\n"
            f"**Logic Analyst:**\n{logic}\n\n"
            f"**Syntax Inspector:**\n{syntax}\n\n"
            f"**Perf & Security:**\n{perf}",
            0, 0,
        )


def _agent_perf_security(message: str) -> tuple:
    """Agent 3 (Premium) — Performance & Security Auditor: Claude Opus 4.5.
    Returns (text, input_tokens, output_tokens)."""
    try:
        if not ANTHROPIC_API_KEY:
            return "[Perf & Security Auditor unavailable: ANTHROPIC_API_KEY not configured]", 0, 0
        import anthropic as _anthropic
        client = _anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=DEBUG_PERF_MODEL,
            max_tokens=2048,
            system=_PERF_SECURITY_PROMPT,
            messages=[{"role": "user", "content": message}],
        )
        text = (msg.content[0].text or "").strip()
        return text, msg.usage.input_tokens or 0, msg.usage.output_tokens or 0
    except Exception as e:
        logger.exception("Multi-debug Agent 3 (Perf & Security) failed")
        return f"[Perf & Security Auditor unavailable: {str(e)[:300]}]", 0, 0


def _agent_synthesizer(original: str, logic: str, syntax: str, perf: str, model: str = None) -> tuple:
    """Agent 4 — Synthesizer: Claude Sonnet 4.5 (premium).
    Returns (text, input_tokens, output_tokens)."""
    model = model or DEBUG_SYNTH_MODEL
    combined = (
        f"## Original Code / Bug Description\n{original}\n\n"
        f"---\n## Diagnosis from Agent 1 — Logic Analyst\n{logic}\n\n"
        f"---\n## Diagnosis from Agent 2 — Syntax & Runtime Inspector\n{syntax}\n\n"
        f"---\n## Diagnosis from Agent 3 — Performance & Security Auditor\n{perf}\n\n"
        f"---\n"
        f"All three agents have completed their diagnosis. "
        f"Now build the unified issue map, resolve any conflicts between agents, "
        f"and produce the single complete fix."
    )
    try:
        if not ANTHROPIC_API_KEY:
            return (
                "[Synthesizer unavailable: ANTHROPIC_API_KEY not configured]\n\n"
                f"**Logic Analyst:**\n{logic}\n\n"
                f"**Syntax Inspector:**\n{syntax}\n\n"
                f"**Perf & Security:**\n{perf}",
                0, 0,
            )
        import anthropic as _anthropic
        client = _anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=model,
            max_tokens=4096,
            system=_SYNTHESIZER_PROMPT,
            messages=[{"role": "user", "content": combined}],
        )
        text = (msg.content[0].text or "").strip()
        return text, msg.usage.input_tokens or 0, msg.usage.output_tokens or 0
    except Exception as e:
        logger.exception("Multi-debug Agent 4 (Synthesizer) failed")
        return (
            f"[Synthesizer error: {str(e)[:300]}]\n\n"
            f"**Logic Analyst:**\n{logic}\n\n"
            f"**Syntax Inspector:**\n{syntax}\n\n"
            f"**Perf & Security:**\n{perf}",
            0, 0,
        )


# ================================
# Image validation (magic bytes)
# ================================

def _is_valid_image(data: bytes) -> bool:
    """
    Validate a file by inspecting its magic bytes rather than trusting the
    client-supplied Content-Type or file extension (both are trivially spoofed).
    Accepts JPEG, PNG, and WebP — the three formats the frontend advertises.
    """
    if len(data) < 12:
        return False
    if data[:3] == b'\xff\xd8\xff':                         # JPEG
        return True
    if data[:8] == b'\x89PNG\r\n\x1a\n':                   # PNG
        return True
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':      # WebP
        return True
    return False


# ================================
# Token / Character Limits
# ================================

# ~4 chars per token is a safe approximation for English text
_CHARS_PER_TOKEN = 4
# Keep context well under the model's 32k limit; reserve ~1000 tokens for the reply
_MAX_CONTEXT_TOKENS = 28_000
_MAX_CONTEXT_CHARS = _MAX_CONTEXT_TOKENS * _CHARS_PER_TOKEN
# Hard cap on a single incoming user message (~4000 tokens)
_MAX_MESSAGE_CHARS = 16_000


# ================================
# Internal Helper Functions
# ================================

_uncensored_client: "OpenAIClient | None" = None

def get_uncensored_client() -> OpenAIClient:
    """
    Return a cached OpenAI-compatible client pointed at OpenRouter.
    Built once on first call (lazy singleton) — avoids reconstructing the
    HTTP client on every uncensored request.
    SDK retries are disabled — _with_retries() manages retry logic instead.
    """
    global _uncensored_client
    if _uncensored_client is not None:
        return _uncensored_client

    api_key = os.getenv("OPENROUTER_API_KEY")
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY missing at runtime")

    _uncensored_client = OpenAIClient(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        max_retries=0,
        default_headers={
            "Referer": frontend_url,
            "X-Title": "AI Chatbox",
        },
    )
    return _uncensored_client


def _trim_to_token_limit(messages: list[dict]) -> list[dict]:
    """
    Drop the oldest messages from the history until the total character
    count fits within _MAX_CONTEXT_CHARS. Prevents hitting the model's
    context window limit on long conversations.
    """
    while messages:
        total = sum(len(m.get("content") or "") for m in messages)
        if total <= _MAX_CONTEXT_CHARS:
            break
        messages = messages[1:]
    return messages


def _mistral_chat_reply(messages: list[dict]) -> tuple:
    """Send a conversation history to Mistral and return (reply_text, input_tokens, output_tokens)."""
    r = mistral_client.chat.completions.create(
        model=REGULAR_MODEL,
        messages=messages,
    )
    text = (r.choices[0].message.content or "").strip()
    u = getattr(r, 'usage', None)
    return text, getattr(u, 'prompt_tokens', 0) or 0, getattr(u, 'completion_tokens', 0) or 0


def _uncensored_chat_reply(messages: list[dict]) -> tuple:
    """
    Send a conversation history to the uncensored model via OpenRouter.
    Returns (reply_text, input_tokens, output_tokens).
    """
    client = get_uncensored_client()
    r = client.chat.completions.create(
        model=UNCENSORED_MODEL,
        messages=messages,
        temperature=1.1,
        top_p=0.95,
        frequency_penalty=0.2,
        max_tokens=1024,
        timeout=90,
    )
    text = (r.choices[0].message.content or "").strip()
    u = getattr(r, 'usage', None)
    return text, getattr(u, 'prompt_tokens', 0) or 0, getattr(u, 'completion_tokens', 0) or 0


def _gemini_extract_text_from_file(file_path: str, mime_type: Optional[str] = None) -> tuple:
    """
    Upload a file (image / PDF / plain text) to Gemini and extract its
    raw text content. Used by the OCR upload endpoint.
    Returns (text, input_tokens, output_tokens).
    """
    file = genai.upload_file(file_path, mime_type=mime_type)
    model = genai.GenerativeModel(GEMINI_FILE_MODEL)
    prompt = (
        "Extract the raw text content from this file as accurately as possible. "
        "No extra commentary—just the text in reading order."
    )
    resp = model.generate_content([prompt, file])
    text = (resp.text or "").strip()
    _um = getattr(resp, 'usage_metadata', None)
    return (
        text,
        getattr(_um, 'prompt_token_count', 0) or 0,
        getattr(_um, 'candidates_token_count', 0) or 0,
    )


def _get_retry_after(e: APIStatusError) -> int:
    """
    Parse the wait time (seconds) from an API 429 error response.
    Checks standard 'Retry-After' first, then OpenRouter's
    'x-ratelimit-reset-requests' Unix-timestamp header.
    Returns 0 if neither header is present or parseable.
    """
    try:
        headers = e.response.headers
        # Standard header (value is seconds to wait)
        ra = headers.get("retry-after") or headers.get("Retry-After")
        if ra:
            return max(int(ra), 1)
        # OpenRouter free-model header: Unix timestamp of next reset
        reset_ts = headers.get("x-ratelimit-reset-requests")
        if reset_ts:
            wait = int(float(reset_ts)) - int(time.time())
            return max(wait, 1)
        return 0
    except Exception:
        return 0


def _rate_limit_response(retry_after: int, base_delay: int) -> Response:
    """Build a user-friendly 429 response that includes the wait time in seconds."""
    ra = retry_after or base_delay
    return Response(
        {
            "error": f"The AI provider is rate-limiting requests. Please wait {ra} seconds and try again.",
            "retry_after": ra,
        },
        status=429,
    )


def _with_retries(call_fn, max_attempts: int = 2, base_delay: int = 2):
    """
    Call call_fn() and retry on transient upstream errors (429, 502, 503, 504)
    using exponential backoff. Returns either the function's result or a
    DRF Response on unrecoverable failure.

    - max_attempts: total number of tries (including the first)
    - base_delay:   seconds to wait before the first retry (doubles each attempt)
    """
    attempt = 0
    while True:
        try:
            return call_fn()
        except APIStatusError as e:
            code = getattr(e, "status_code", None)
            retry_after = _get_retry_after(e)
            retryable = code in (429, 502, 503, 504)

            if retryable and attempt < max_attempts - 1:
                delay = retry_after or (base_delay * (2 ** attempt))
                # For 429: only retry if the provider told us how long to wait
                # AND the wait is short enough to hold the request open.
                # Free-tier models (e.g. OpenRouter :free) hit per-minute limits
                # with no retry-after — blind backoff just wastes time and still
                # returns 429, so fall through to the error return below.
                should_retry = not (code == 429 and (retry_after == 0 or delay > 20))
                if should_retry:
                    time.sleep(delay)
                    attempt += 1
                    continue

            if code == 429:
                return _rate_limit_response(retry_after, base_delay)
            # Map any upstream error to 502 so it is never mistaken for a
            # missing Django route (e.g. a 404 from OpenRouter becoming a
            # Django "Not Found" response).
            return Response({"error": f"Upstream error ({code})"}, status=502)
        except APIError:
            logger.exception("LLM client error in _with_retries")
            return Response({"error": _SERVER_ERROR}, status=502)


# ================================
# API Endpoints
# ================================

@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def create_session(request):
    """
    POST /api/create-session/
    Create a new chat session for the logged-in user.
    Body: { mode: "regular" | "uncensored" | "ocr" }
    Returns: { session_id, title, mode }
    """
    mode = request.data.get("mode", "regular")
    if mode not in _VALID_MODES:
        return Response({"error": f"Invalid mode. Must be one of: {', '.join(_VALID_MODES)}"}, status=status.HTTP_400_BAD_REQUEST)

    ev = _check_email_verified(request.user)
    if ev:
        return ev

    ban = _check_feature_ban(request.user, mode)
    if ban:
        return ban

    sid = _ensure_session(None, mode, user=request.user)

    return Response({
        "session_id": sid,
        "title": _NEW_CHAT_TITLE,
        "mode": mode,
    }, status=201)


class ChatView(APIView):
    """
    POST /api/chat/
    Send a message and receive an AI reply.
    Body: { message, session_id?, mode? }
    Returns: { reply, session_id, title }
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [_LLMChatThrottle]

    def post(self, request):
        try:
            mode = request.data.get("mode", "regular")
            if mode not in _VALID_MODES:
                return Response({"error": f"Invalid mode. Must be one of: {', '.join(_VALID_MODES)}"}, status=status.HTTP_400_BAD_REQUEST)

            ev = _check_email_verified(request.user)
            if ev:
                return ev

            ban = _check_feature_ban(request.user, mode)
            if ban:
                return ban

            user_message = request.data.get("message")

            # Validate the incoming message
            if not user_message:
                return Response(
                    {"error": "Message is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if len(user_message) > _MAX_MESSAGE_CHARS:
                return Response(
                    {"error": f"Message too long. Maximum {_MAX_MESSAGE_CHARS} characters allowed."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            incoming_session_id = request.data.get("session_id")

            # Resolve or create the session, always scoped to the logged-in user.
            # If the session exists but belongs to a different mode (e.g. the user
            # switched modes while a regular-session URL was still active), silently
            # create a fresh session in the correct mode instead of erroring.
            if incoming_session_id:
                session = ChatSession.objects.filter(
                    session_id=incoming_session_id,
                    user=request.user
                ).first()

                if not session:
                    return Response(
                        {"error": _SESSION_NOT_FOUND},
                        status=status.HTTP_404_NOT_FOUND
                    )

                if session.mode != mode:
                    session_id = _ensure_session(None, mode, user=request.user)
                    session = ChatSession.objects.get(session_id=session_id)
                else:
                    session_id = session.session_id
            else:
                session_id = _ensure_session(None, mode, user=request.user)
                session = ChatSession.objects.get(session_id=session_id)

            # Parse edit/version params
            raw_trim = request.data.get("trim_from_id")
            try:
                trim_from_id = int(raw_trim) if raw_trim is not None else None
                if trim_from_id is not None and trim_from_id <= 0:
                    trim_from_id = None
            except (TypeError, ValueError):
                trim_from_id = None

            version_data = request.data.get("version_data") or None

            # Auto-set the session title from the first message if still empty.
            _update_title_if_empty(session_id, user_message)
            session.refresh_from_db(fields=["title"])

            # Fetch the last 10 messages as context for the LLM (oldest first).
            # The current user message is NOT yet saved — we append it explicitly
            # so that a 429 leaves no orphaned row in the DB.
            history_qs = (
                Message.objects
                .filter(session_id=session_id, mode=mode)
                .order_by("-timestamp")[:10][::-1]
            )
            messages = [
                {"role": m.role, "content": m.content}
                for m in history_qs
            ]
            messages = _trim_to_token_limit(messages)
            # Append the current turn so the LLM sees it even though it isn't saved yet.
            messages.append({"role": "user", "content": user_message})

            def _call():
                if mode == "uncensored":
                    return _uncensored_chat_reply(messages)
                return _mistral_chat_reply(messages)

            result = _with_retries(_call, max_attempts=2, base_delay=2)

            # On LLM error return early — no messages were written so retries
            # are completely safe (no duplicates, no orphaned rows).
            if isinstance(result, Response):
                if result.status_code == 429:
                    result.data["session_id"] = session_id
                    result.data["title"] = session.title or _NEW_CHAT_TITLE
                return result

            if not isinstance(result, tuple) or len(result) != 3:
                logger.error("Unexpected LLM response format: %s", type(result))
                return Response({"error": _SERVER_ERROR}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            reply, in_tok, out_tok = result
            _record_usage(
                request.user,
                UNCENSORED_MODEL if mode == "uncensored" else REGULAR_MODEL,
                in_tok,
                out_tok,
            )

            # LLM succeeded — persist both messages atomically.
            with transaction.atomic():
                if trim_from_id:
                    Message.objects.filter(
                        session_id=session_id,
                        id__gte=trim_from_id,
                    ).delete()
                user_msg_obj = Message.objects.create(
                    role="user",
                    content=user_message,
                    session_id=session_id,
                    mode=mode,
                    agent_data=version_data,
                )
                Message.objects.create(
                    role="assistant",
                    content=reply,
                    session_id=session_id,
                    mode=mode,
                )

            return Response({
                "reply": reply,
                "msg_id": user_msg_obj.id,
                "session_id": session_id,
                "title": session.title or _NEW_CHAT_TITLE,
            })

        except Exception:
            logger.exception("ChatView unexpected error")
            return Response(
                {"error": _SERVER_ERROR},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ChatHistoryView(APIView):
    """
    GET /api/history/?session_id=...&mode=...&page=...
    Returns paginated message history for a session owned by the logged-in user.
    Returns: { history, page, page_size, total, has_next }
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        session_id = request.query_params.get("session_id")
        mode = request.query_params.get("mode", "regular")

        if not session_id:
            return Response(
                {"error": "session_id required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify the session belongs to the requesting user
        session = ChatSession.objects.filter(
            session_id=session_id,
            user=request.user
        ).first()

        if not session:
            return Response(
                {"error": "Not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        PAGE_SIZE = 50
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (ValueError, TypeError):
            page = 1

        qs = Message.objects.filter(
            session_id=session_id,
            mode=mode,
        ).order_by("timestamp")

        total = qs.count()
        offset = (page - 1) * PAGE_SIZE
        messages = qs[offset: offset + PAGE_SIZE]

        history = [
            {
                "msg_id": m.id,
                "role": m.role,
                "content": m.content,
                "attachments": m.attachments or [],
                "mode": m.mode,
                "agents": m.agent_data if m.role == "assistant" else None,
                "version_data": m.agent_data if m.role == "user" else None,
            }
            for m in messages
        ]

        return Response({
            "history": history,
            "page": page,
            "page_size": PAGE_SIZE,
            "total": total,
            "has_next": offset + PAGE_SIZE < total,
        })


@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def list_sessions(request):
    """
    GET /api/sessions/?mode=optional
    List all chat sessions for the logged-in user, sorted by most recent activity.
    Returns: [{ session_id, title, mode, last_time, created_at }]
    """
    mode = request.query_params.get("mode")
    if mode and mode not in _VALID_MODES:
        return Response(
            {"error": f"Invalid mode. Must be one of: {', '.join(_VALID_MODES)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    qs = ChatSession.objects.filter(user=request.user)
    if mode:
        qs = qs.filter(mode=mode)

    # Get the timestamp of the last message for each of this user's sessions only,
    # rather than querying all messages across all users globally.
    session_ids = qs.values_list("session_id", flat=True)
    last_map = (
        Message.objects
        .filter(session_id__in=session_ids)
        .values("session_id")
        .annotate(last_time=Max("timestamp"))
    )
    last_lookup = {row["session_id"]: row["last_time"] for row in last_map}

    data = [
        {
            "session_id": s.session_id,
            "title": s.title or _NEW_CHAT_TITLE,
            "mode": s.mode,
            "last_time": last_lookup.get(s.session_id, s.created_at),
            "created_at": s.created_at,
        }
        for s in qs
    ]
    data.sort(key=lambda d: d["last_time"] or d["created_at"], reverse=True)
    return Response(data)


@api_view(["DELETE"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def delete_session(request, session_id):
    """
    DELETE /api/sessions/<session_id>/delete/
    Delete a session and all its messages (cascade). Only the owner can delete.
    Returns: { deleted: session_id }
    """
    session = ChatSession.objects.filter(
        session_id=session_id,
        user=request.user
    ).first()

    if not session:
        return Response(
            {"error": _SESSION_NOT_FOUND},
            status=status.HTTP_404_NOT_FOUND
        )

    session.delete()

    return Response({"deleted": session_id}, status=status.HTTP_200_OK)


# =============================================================
# ⚠️  UNUSED / DEAD CODE — ENDPOINT NOT CALLED ANYWHERE IN THE APP
# -------------------------------------------------------------
# This view was built for a standalone file-upload OCR flow
# (client uploads a file → Gemini extracts text → returns raw text).
# The current app uses a different flow:
#   • Image uploads  → GeminiWithImagesView  →  POST /api/gemini-with-images/
#   • Text questions → OcrQaView             →  POST /api/ocr-qa/
# The matching frontend component is OcrUpload.js (also marked unused).
# Keep this view if you plan to re-introduce the separate file-upload
# OCR feature in the future. Otherwise it can be safely deleted along
# with its URL entry in chat/urls.py  (/api/ocr/).
# =============================================================
class OcrUploadView(APIView):
    """
    POST /api/ocr/
    Upload an image, PDF, or text file. Gemini extracts the raw text and
    stores it as a system message in an OCR session for later Q&A.
    Form data: { file, session_id? }
    Returns: { text, session_id }
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ev = _check_email_verified(request.user)
        if ev:
            return ev
        ban = _check_feature_ban(request.user, "ocr")
        if ban:
            return ban
        try:
            fileobj = request.FILES.get("file")
            if not fileobj:
                return Response(
                    {"error": "No file uploaded"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not GOOGLE_API_KEY:
                return Response(
                    {"error": "GOOGLE_API_KEY not configured"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            incoming_session_id = request.data.get("session_id")

            # Validate existing session or create a new OCR session
            if incoming_session_id:
                session = ChatSession.objects.filter(
                    session_id=incoming_session_id,
                    user=request.user,
                    mode="ocr"
                ).first()

                if not session:
                    return Response(
                        {"error": _SESSION_NOT_FOUND},
                        status=status.HTTP_404_NOT_FOUND
                    )

                session_id = session.session_id
            else:
                session_id = _ensure_session(None, "ocr", user=request.user)

            # Write the uploaded file to a temp path for Gemini to read.
            # TemporaryUploadedFile already has a path on disk; anything
            # else (InMemoryUploadedFile) needs to be written out first.
            if isinstance(fileobj, TemporaryUploadedFile):
                temp_path = fileobj.temporary_file_path()
                owned_temp = False  # Django manages this file's lifecycle
            else:
                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    for chunk in fileobj.chunks():
                        tmp.write(chunk)
                    temp_path = tmp.name
                owned_temp = True  # we created it, we must clean it up

            mime = fileobj.content_type or None

            try:
                extracted_text, in_tok, out_tok = _gemini_extract_text_from_file(temp_path, mime_type=mime)
            finally:
                # Always clean up our temp file, even if Gemini raises an exception
                if owned_temp and os.path.exists(temp_path):
                    os.unlink(temp_path)

            _record_usage(request.user, GEMINI_FILE_MODEL, in_tok, out_tok)

            # Save the extracted text as a system message for later Q&A queries
            Message.objects.create(
                role="system",
                content=extracted_text,
                session_id=session_id,
                mode="ocr",
            )

            return Response(
                {"text": extracted_text, "session_id": session_id},
                status=status.HTTP_200_OK
            )

        except Exception:
            logger.exception("OcrUploadView unexpected error")
            return Response(
                {"error": _SERVER_ERROR},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class OcrQaView(APIView):
    """
    POST /api/ocr-qa/
    Ask a question about the document previously uploaded in an OCR session.
    If no document has been uploaded, Gemini answers from general knowledge.
    Body: { question, session_id? }
    Returns: { answer, session_id, source: "document" | "general" }
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [_LLMOcrThrottle]

    def post(self, request):
        ev = _check_email_verified(request.user)
        if ev:
            return ev
        ban = _check_feature_ban(request.user, "ocr")
        if ban:
            return ban
        try:
            question = (request.data.get("question") or "").strip()
            incoming_session_id = request.data.get("session_id")

            if not question:
                return Response(
                    {"error": "question is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if len(question) > _MAX_MESSAGE_CHARS:
                return Response(
                    {"error": f"Question too long. Maximum {_MAX_MESSAGE_CHARS} characters allowed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not GOOGLE_API_KEY:
                return Response(
                    {"error": "GOOGLE_API_KEY not configured"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Validate existing session or create a new OCR session
            if incoming_session_id:
                session = ChatSession.objects.filter(
                    session_id=incoming_session_id,
                    user=request.user,
                    mode="ocr"
                ).first()

                if not session:
                    return Response(
                        {"error": _SESSION_NOT_FOUND},
                        status=status.HTTP_404_NOT_FOUND
                    )

                session_id = session.session_id
            else:
                session_id = _ensure_session(None, "ocr", user=request.user)

            # Fetch the most recently uploaded document text for this session
            ocr_msg = (
                Message.objects.filter(
                    session_id=session_id,
                    mode="ocr",
                    role="system",
                )
                .order_by("-timestamp")
                .first()
            )

            model = genai.GenerativeModel(GEMINI_TEXT_MODEL)

            if ocr_msg:
                # Ground the answer strictly in the uploaded document
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
                # No document uploaded yet — fall back to general knowledge
                prompt = (
                    "Answer the user's question helpfully and concisely.\n\n"
                    f"User question: {question}\n"
                )
                source = "general"

            resp = model.generate_content(prompt)
            answer = (resp.text or "").strip()
            _um = getattr(resp, 'usage_metadata', None)
            if _um:
                _record_usage(
                    request.user, GEMINI_TEXT_MODEL,
                    getattr(_um, 'prompt_token_count', 0) or 0,
                    getattr(_um, 'candidates_token_count', 0) or 0,
                )

            # Save the Q&A pair to session history
            Message.objects.create(
                role="user",
                content=question,
                session_id=session_id,
                mode="ocr",
            )
            Message.objects.create(
                role="assistant",
                content=answer,
                session_id=session_id,
                mode="ocr",
            )
            _update_title_if_empty(session_id, question)

            session_obj = ChatSession.objects.filter(session_id=session_id, user=request.user).first()
            return Response(
                {
                    "answer": answer,
                    "session_id": session_id,
                    "source": source,
                    "title": (session_obj.title if session_obj else None) or _NEW_CHAT_TITLE,
                },
                status=status.HTTP_200_OK
            )

        except Exception:
            logger.exception("OcrQaView unexpected error")
            return Response(
                {"error": _SERVER_ERROR},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


def _resolve_ocr_session(incoming_session_id, mode, user):
    """
    Return the session_id string for an OCR request, or a 404 Response if the
    provided session_id doesn't belong to this user.
    """
    if incoming_session_id:
        session = ChatSession.objects.filter(
            session_id=incoming_session_id,
            user=user,
            mode="ocr",
        ).first()
        if not session:
            return Response({"error": _SESSION_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)
        return session.session_id
    return _ensure_session(None, mode, user=user)


def _upload_single_image(image_file):
    """
    Validate, estimate tokens, upload to Cloudinary, and register with Gemini.
    Returns (attachment_dict, gemini_file_handle).
    Raises ValueError with a user-facing message if the file is invalid or too large.
    """
    _MAX_IMAGE_BYTES = 100 * 1024 * 1024  # 100 MB
    if image_file.size > _MAX_IMAGE_BYTES:
        raise ValueError(f"'{image_file.name}' exceeds the 100 MB size limit.")

    data = image_file.read()
    if not _is_valid_image(data):
        raise ValueError(
            f"'{image_file.name}' is not a valid image file (JPEG, PNG, or WebP required)."
        )

    dims = _read_image_dimensions(data)
    est_tokens = _gemini_image_tokens(*dims) if dims else _GEMINI_TOKENS_PER_TILE

    upload_result = cloudinary.uploader.upload(data, folder="uploads", resource_type="image")
    attachment = {
        "url": upload_result["secure_url"],
        "name": image_file.name,
        "mime": image_file.content_type or "application/octet-stream",
        "estimated_tokens": est_tokens,
    }

    ext = os.path.splitext(image_file.name)[1] or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    try:
        gemini_handle = genai.upload_file(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return attachment, gemini_handle


class GeminiWithImagesView(APIView):
    """
    POST /api/gemini-with-images/
    Send up to 4 images to Gemini for visual analysis. Images are also
    uploaded to Cloudinary for persistent storage and returned as attachments.
    Form data: { images[], message?, session_id?, mode? }
    Returns: { response, session_id, attachments }
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [_LLMOcrThrottle]

    def post(self, request):
        ev = _check_email_verified(request.user)
        if ev:
            return ev
        ban = _check_feature_ban(request.user, "ocr")
        if ban:
            return ban
        try:
            return self._handle(request)
        except Exception:
            logger.exception("GeminiWithImagesView unexpected error")
            return Response(
                {"error": _SERVER_ERROR},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _handle(self, request):
        message = (request.data.get("message") or "").strip() or "Analyze these images"
        mode = request.data.get("mode", "ocr")
        if mode not in _VALID_MODES:
            return Response(
                {"error": f"Invalid mode. Must be one of: {', '.join(_VALID_MODES)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session_id = _resolve_ocr_session(request.data.get("session_id"), mode, request.user)
        if isinstance(session_id, Response):
            return session_id

        images = request.FILES.getlist("images")[:4]
        if not images:
            return Response({"error": "No images provided"}, status=status.HTTP_400_BAD_REQUEST)

        saved_attachments = []
        uploads_for_gemini = []
        for image_file in images:
            try:
                attachment, gemini_handle = _upload_single_image(image_file)
            except ValueError as exc:
                return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            saved_attachments.append(attachment)
            uploads_for_gemini.append(gemini_handle)

        gemini_model = genai.GenerativeModel(GEMINI_FILE_MODEL)
        response = gemini_model.generate_content([message, *uploads_for_gemini])
        answer_text = (getattr(response, "text", "") or "").strip()
        _um = getattr(response, 'usage_metadata', None)
        if _um:
            _record_usage(
                request.user, GEMINI_FILE_MODEL,
                getattr(_um, 'prompt_token_count', 0) or 0,
                getattr(_um, 'candidates_token_count', 0) or 0,
            )

        Message.objects.create(
            role="user", content=message,
            session_id=session_id, mode=mode, attachments=saved_attachments,
        )
        Message.objects.create(
            role="assistant", content=answer_text,
            session_id=session_id, mode=mode, attachments=[],
        )
        _update_title_if_empty(session_id, message)

        session_obj = ChatSession.objects.filter(session_id=session_id, user=request.user).first()
        return Response({
            "response": answer_text,
            "session_id": session_id,
            "title": (session_obj.title if session_obj else None) or _NEW_CHAT_TITLE,
            "attachments": saved_attachments,
        })


_CODE_SIGNALS = frozenset([
    # Python / general keywords
    "def ", "class ", "import ", "return ", "print(",
    "if ", "elif ", "else:", "for ", "while ", "with ",
    "try:", "except", "raise ", "yield ", "lambda ",
    "self.", "none ", "true ", "false ",
    # JS/TS
    "function ", "const ", "let ", "var ", "console.",
    "async ", "await ", "typeof ", "instanceof ",
    # C / Java / C# / Go / Rust etc.
    "public ", "private ", "protected ", "static ",
    "void ", "int ", "bool ", "return;",
    "new ", "this.", "catch ", "throw ",
    # Common operators / delimiters that appear in code
    "(){", "()", "[];", "{}", "=>", "->", "::", "/*", "//",
    "&&", "||", "+=", "-=", "!=",
    # SQL
    "select ", "from ", "where ", "insert ", "update ",
    # Shell / other
    "#!/", "echo ", "export ",
    # Error / bug description words
    "error", "exception", "traceback", "stacktrace",
    "bug", "issue", "crash", "fail", "broken",
    "not work", "doesn't work", "does not work",
    "unexpected", "undefined", "null pointer",
])

_GREETING_ONLY = frozenset([
    "hi", "hello", "hey", "yo", "sup", "hii", "helo",
    "test", "ok", "okay", "yes", "no", "thanks", "thank you",
])


def _is_debuggable_input(message: str) -> bool:
    """
    Return True only when the message looks like code or a real bug description.
    Rejects pure greetings, single words, and inputs with no code-like signals.
    """
    stripped = message.strip()

    # Must be at least 20 chars — single words / short greetings fail here
    if len(stripped) < 20:
        return False

    # Pure greeting (case-insensitive, punctuation stripped)
    clean = stripped.lower().rstrip("!?.,;:")
    if clean in _GREETING_ONLY:
        return False

    # Multi-line input (3+ lines) is almost certainly code or a detailed bug report
    if stripped.count('\n') >= 2:
        return True

    # Must contain at least one code or bug-description signal
    lower = stripped.lower()
    return any(sig in lower for sig in _CODE_SIGNALS)


def _run_agents_parallel(tier: str, message: str) -> tuple:
    """Run 3 specialist agents concurrently.
    Returns (text_results, usage_data):
      text_results: {agent_name: text_str}
      usage_data:   {agent_name: (model_name, input_tokens, output_tokens)}
    """
    if tier == "premium":
        jobs = {
            "logic_analyst":         (_agent_logic_analyst,          message, GEMINI_DEBUG_MODEL),
            "syntax_inspector":      (_agent_syntax_inspector,        message, DEBUG_SYNTAX_MODEL),
            "perf_security_auditor": (_agent_perf_security,           message),
        }
        model_map = {
            "logic_analyst":         GEMINI_DEBUG_MODEL,
            "syntax_inspector":      DEBUG_SYNTAX_MODEL,
            "perf_security_auditor": DEBUG_PERF_MODEL,
        }
    else:
        jobs = {
            "logic_analyst":         (_agent_mistral_logic_analyst,    message),
            "syntax_inspector":      (_agent_mistral_syntax_inspector,  message),
            "perf_security_auditor": (_agent_gemini_perf_security,      message),
        }
        model_map = {
            "logic_analyst":         REGULAR_MODEL,
            "syntax_inspector":      REGULAR_MODEL,
            "perf_security_auditor": GEMINI_FREE_MODEL,
        }

    results = {}
    usage = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {name: executor.submit(fn, *args) for name, (fn, *args) in jobs.items()}
        for name, future in futures.items():
            try:
                raw = future.result(timeout=120)
                if isinstance(raw, tuple) and len(raw) == 3:
                    text, in_tok, out_tok = raw
                elif isinstance(raw, str):
                    text, in_tok, out_tok = raw, 0, 0
                else:
                    text, in_tok, out_tok = str(raw), 0, 0
                results[name] = text
                usage[name] = (model_map[name], in_tok, out_tok)
            except concurrent.futures.TimeoutError:
                results[name] = f"[{name.replace('_', ' ').title()} timed out after 120 s]"
                usage[name] = (model_map[name], 0, 0)
            except Exception as exc:
                results[name] = f"[{name.replace('_', ' ').title()} failed: {str(exc)[:200]}]"
                usage[name] = (model_map[name], 0, 0)
    return results, usage


_NO_CODE_TOKEN = "[NO_CODE_PROVIDED]"


def _synthesize(tier: str, message: str, agent_results: dict) -> tuple:
    """
    Run Agent 4 (Synthesizer).
    Returns (synthesis_text, input_tokens, output_tokens).

    Before calling the LLM this function:
    1. Strips the Gemini-fallback marker (_GEMINI_FALLBACK_MARKER).
    2. Strips the [NO_CODE_PROVIDED] token from agent values.
    3. Replaces agent error strings (starting with '[') with a clear note
       so the synthesizer is never fed raw error brackets.
    4. Counts how many agents produced meaningful output — if fewer than 2
       did, skip the LLM call entirely and return a clear explanation.
    """
    AGENT_KEYS = ("logic_analyst", "syntax_inspector", "perf_security_auditor")

    # --- Step 1 & 2: strip internal markers -----------------------------------
    clean = {}
    for k, v in agent_results.items():
        if k not in AGENT_KEYS:
            continue
        s = v or ""
        if s.startswith(_GEMINI_FALLBACK_MARKER):
            s = s[len(_GEMINI_FALLBACK_MARKER):]
        s = s.replace(_NO_CODE_TOKEN, "").strip()
        clean[k] = s

    # --- Step 3: replace error strings with a synthesizer-friendly note -------
    _REQUIRED_AGENTS = {"logic_analyst": "Logic Analyst",
                        "syntax_inspector": "Syntax & Runtime Inspector",
                        "perf_security_auditor": "Performance & Security Auditor"}
    final = {}
    failed = []
    for key, label in _REQUIRED_AGENTS.items():
        val = clean.get(key, "")
        if not val or val.startswith("[") or len(val) < 30:
            final[key] = f"[{label} did not produce a result — skip this agent in your analysis]"
            failed.append(label)
        else:
            final[key] = val

    # --- Step 4: guard — need at least 2 agents to synthesize ----------------
    succeeded = 3 - len(failed)
    if succeeded == 0:
        return (
            "**No code or bug description was detected.**\n\n"
            "Please paste the code you want debugged, or describe the bug in detail — "
            "including what it does, what it should do, and any error messages you see.",
            0, 0,
        )
    if succeeded == 1:
        failed_str = ", ".join(failed)
        only_result = next(
            (v for v in final.values() if not v.startswith("[")),
            "No meaningful analysis available.",
        )
        return (
            f"**Partial analysis only — {failed_str} did not respond.**\n\n"
            "Only one specialist completed the analysis. The result below may be incomplete:\n\n"
            + only_result,
            0, 0,
        )

    if tier == "premium":
        return _agent_synthesizer(
            message,
            final["logic_analyst"],
            final["syntax_inspector"],
            final["perf_security_auditor"],
            model=DEBUG_SYNTH_MODEL,
        )
    return _agent_mistral_synthesizer(
        message,
        final["logic_analyst"],
        final["syntax_inspector"],
        final["perf_security_auditor"],
    )


class MultiDebugView(APIView):
    """
    POST /api/multi-debug/
    Run multi-agent debugging on the provided code or bug description.

    Free tier:    Mistral (Logic + Syntax) · Gemini 2.5 Flash (Perf/Sec) · Mistral (Synth)
    Premium tier: Gemini 2.5 Pro (Logic) · GPT-4.1 (Syntax) · Claude Opus (Perf) · Claude Sonnet (Synth)

    Body:    { message, session_id?, tier? }
    Returns: { reply, agents: {logic_analyst, syntax_inspector, perf_security_auditor},
               tier, session_id, title }
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [_LLMDebugThrottle]

    def post(self, request):
        try:
            user_message = (request.data.get("message") or "").strip()
            incoming_session_id = request.data.get("session_id")
            tier = (request.data.get("tier") or "free").strip()
            if tier not in ("free", "premium"):
                tier = "free"

            ev = _check_email_verified(request.user)
            if ev:
                return ev

            ban = _check_feature_ban(request.user, "multi_debugger", tier)
            if ban:
                return ban

            # Server-side enforcement — premium tier requires a paid account
            if tier == "premium":
                try:
                    profile = request.user.profile
                    is_premium = profile.is_premium
                except Exception:
                    # Profile missing (user created before Profile model existed) or DB error.
                    # Create the profile on the fly so the user is not permanently locked out.
                    try:
                        from accounts.models import Profile as _Profile
                        profile, _ = _Profile.objects.get_or_create(user=request.user)
                        is_premium = profile.is_premium
                    except Exception as exc:
                        logger.error("MultiDebugView: failed to resolve profile for user=%s: %s", request.user.id, exc)
                        return Response(
                            {"error": "Could not verify your subscription status. Please try again."},
                            status=status.HTTP_403_FORBIDDEN,
                        )
                if not is_premium:
                    return Response(
                        {"error": "Premium tier requires an active subscription. Please upgrade your plan."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

            if not user_message:
                return Response({"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST)
            if len(user_message) > _MAX_MESSAGE_CHARS:
                return Response(
                    {"error": f"Message too long. Maximum {_MAX_MESSAGE_CHARS} characters allowed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not _is_debuggable_input(user_message):
                return Response(
                    {"error": (
                        "Multi-Debugger needs actual code or a bug description to analyze. "
                        "Please paste your code or describe the bug in detail "
                        "(e.g., what it does, what it should do, any error messages)."
                    )},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Resolve or create a multi_debugger session (mode-scoped)
            # If the incoming session_id belongs to a different mode (e.g. user
            # switched from regular chat without navigating away), silently create
            # a fresh multi_debugger session instead of rejecting with 404.
            if incoming_session_id:
                session = ChatSession.objects.filter(
                    session_id=incoming_session_id,
                    user=request.user,
                    mode="multi_debugger",
                ).first()
                if not session:
                    session_id = _ensure_session(None, "multi_debugger", user=request.user)
                    session = ChatSession.objects.get(session_id=session_id)
            else:
                session_id = _ensure_session(None, "multi_debugger", user=request.user)
                session = ChatSession.objects.get(session_id=session_id)

            session_id = session.session_id
            raw_trim = request.data.get("trim_from_id")
            try:
                trim_from_id = int(raw_trim) if raw_trim is not None else None
                if trim_from_id is not None and trim_from_id <= 0:
                    trim_from_id = None
            except (TypeError, ValueError):
                trim_from_id = None

            version_data = request.data.get("version_data") or None
            with transaction.atomic():
                if trim_from_id:
                    Message.objects.filter(session_id=session_id, id__gte=trim_from_id).delete()
                user_msg_obj = Message.objects.create(role="user", content=user_message, session_id=session_id, mode="multi_debugger", agent_data=version_data)
            _update_title_if_empty(session_id, user_message)
            session.refresh_from_db(fields=["title"])

            agent_results, agent_usage = _run_agents_parallel(tier, user_message)
            synthesis, synth_in_tok, synth_out_tok = _synthesize(tier, user_message, agent_results)

            # Record real token usage from API responses
            for _, (_model, _in, _out) in agent_usage.items():
                _record_usage(request.user, _model, _in, _out)
            _synth_model = DEBUG_SYNTH_MODEL if tier == "premium" else REGULAR_MODEL
            _record_usage(request.user, _synth_model, synth_in_tok, synth_out_tok)

            Message.objects.create(role="assistant", content=synthesis, session_id=session_id, mode="multi_debugger", agent_data={**agent_results, "_tier": tier})

            return Response({
                "reply":      synthesis,
                "agents":     agent_results,
                "tier":       tier,
                "msg_id":     user_msg_obj.id,
                "session_id": session_id,
                "title":      session.title or _NEW_CHAT_TITLE,
            })

        except Exception:
            logger.exception("MultiDebugView unexpected error")
            return Response({"error": _SERVER_ERROR}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["PUT"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def rename_session(request, session_id):
    """
    PUT /api/sessions/<session_id>/rename/
    Rename a session title. Only the owner can rename their own session.
    Body: { title: "new name" }
    Returns: { session_id, title }
    """
    try:
        cs = ChatSession.objects.get(session_id=session_id, user=request.user)
        new_title = (request.data.get("title") or "").strip()
        if not new_title:
            return Response({"error": "Title required"}, status=400)
        if len(new_title) > 200:
            return Response({"error": "Title too long. Maximum 200 characters allowed."}, status=400)
        cs.title = new_title
        cs.save(update_fields=["title", "updated_at"])
        return Response({"session_id": cs.session_id, "title": cs.title})
    except ChatSession.DoesNotExist:
        return Response({"error": "Not found"}, status=404)


@api_view(["GET", "DELETE"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def usage_stats(request):
    """
    GET /api/usage/
    Returns per-model token usage and estimated cost for the logged-in user.
    Costs are estimates based on public provider pricing.
    """
    from .models import ModelUsage
    from django.db.models import Sum
    from django.db.models.functions import Coalesce
    from django.db.models import Value

    if request.method == "DELETE":
        ModelUsage.objects.filter(user=request.user).delete()
        return Response({"detail": "Usage statistics reset."}, status=status.HTTP_200_OK)

    rows = (
        ModelUsage.objects
        .filter(user=request.user)
        .values('model_name')
        .annotate(
            total_input=Coalesce(Sum('input_tokens'), Value(0)),
            total_output=Coalesce(Sum('output_tokens'), Value(0)),
        )
        .order_by('-total_input')
    )

    by_model = []
    grand_cost = 0.0
    grand_tokens = 0

    for row in rows:
        model = row['model_name']
        inp = row['total_input']
        out = row['total_output']
        pricing = _get_model_pricing(model)
        cost = (inp * pricing['input'] + out * pricing['output']) / 1_000_000
        grand_cost += cost
        grand_tokens += inp + out
        by_model.append({
            'model': model,
            'input_tokens': inp,
            'output_tokens': out,
            'total_tokens': inp + out,
            'estimated_cost_usd': round(cost, 6),
        })

    return Response({
        'by_model': by_model,
        'total_tokens': grand_tokens,
        'total_cost_usd': round(grand_cost, 6),
    })


@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def model_info(request):
    """
    GET /api/models/
    Returns the active model identifiers so the frontend can display them.
    """
    return Response({
        "mistral": REGULAR_MODEL,
        "gemini": GEMINI_FILE_MODEL,
    })
