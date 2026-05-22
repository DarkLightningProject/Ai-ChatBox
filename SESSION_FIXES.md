# Bug Fixes & Optimizations — Session Documentation

---

## Fix 1 — Multi-Debugger: Illegal HTTP Header Value (DOMException)

### Where the problem arose
**File:** `chatgpt-frontend/src/Components/ChatApp.js` — `makeIdemKey()` function (line 47–48)

The `Idempotency-Key` HTTP header was built by embedding the raw message text directly into the header value:

```js
// BEFORE (broken)
const makeIdemKey = (sid, text) => `${sid || "new"}:${text || ""}:${Date.now() >> 12}`;
```

When the user pasted multi-line code into the Multi-Debugger (e.g., a function with `\n`, `{`, `}`), the header value contained those characters. HTTP header values may **only** contain printable single-line ASCII — newlines are strictly forbidden.

The browser's `XMLHttpRequest` enforced this and threw:
```
DOMException: Failed to execute 'setRequestHeader' on 'XMLHttpRequest':
'debugger-c69040a7:function foo() {\n  ...\n}:283936' is not a valid HTTP header field value.
```

Because the exception was thrown **before the request was sent**, the Django server received nothing and logged nothing. The frontend's `catch` block had no `err.response` (it was `undefined`), so it fell back to the generic "Multi-Debug server error" message — making the bug look like a server problem rather than a client-side crash.

### How it was fixed
Replaced the raw text with a **djb2-style hash** that produces a safe alphanumeric string:

```js
// AFTER (fixed)
const _hashStr = (s) => {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  return (h >>> 0).toString(36);
};
const makeIdemKey = (sid, text) => `${sid || "new"}:${_hashStr(text || "")}:${Date.now() >> 12}`;
```

The header value is now always a short alphanumeric string regardless of what the user typed.  
Better error diagnostics were also added to the `catch` block so future errors surface the real message instead of a generic fallback.

---

## Fix 2 — Multi-Debugger: Session Mode Mismatch → 404

### Where the problem arose
**File:** `chat/views.py` — `MultiDebugView.post()` (around line 1612)

The `/api/multi-debug/` endpoint looked up the incoming `session_id` and filtered by **both** user and `mode="multi_debugger"`:

```python
# BEFORE (broken)
session = ChatSession.objects.filter(
    session_id=incoming_session_id,
    user=request.user,
    mode="multi_debugger",
).first()
if not session:
    return Response({"error": "Session not found"}, status=404)
```

When the user was browsing a regular chat (`/chat/reg-001`) and switched to Multi-Debugger mode, the frontend sent `session_id="reg-001"` to the multi-debug endpoint. The DB lookup found no session with that ID **and** `mode="multi_debugger"` → it returned HTTP 404 → frontend showed "Multi-Debug server error".

### How it was fixed
Instead of returning 404 on a mode mismatch, silently create a brand-new `multi_debugger` session and continue:

```python
# AFTER (fixed)
session = ChatSession.objects.filter(
    session_id=incoming_session_id,
    user=request.user,
    mode="multi_debugger",
).first()
if not session:
    # Session belongs to a different mode — create a proper multi_debugger one
    session_id = _ensure_session(None, "multi_debugger", user=request.user)
    session = ChatSession.objects.get(session_id=session_id)
```

The frontend receives the new `session_id` in the response, `onSessionCreated` fires, the new session appears in the sidebar, and the URL updates automatically.

---

## Fix 3 — Uncensored Chat: Duplicate Session Created on Every Send

### Where the problem arose
**Files:**
- `chatgpt-frontend/src/App.js` — route definitions (lines 366–399)
- `chatgpt-frontend/src/App.js` — `ChatWrapper` component

This was the deepest architectural bug. In React Router v6, the app had **two separate `<Route>` elements** for the same logical page:

```jsx
// BEFORE (broken)
<Route path="/"          element={<RequireAuth>...<ChatWrapper /></RequireAuth>} />
<Route path="/chat/:sessionId" element={<RequireAuth>...<ChatWrapper /></RequireAuth>} />
```

Because they were separate Route elements, React treated them as **two completely different component trees**. Every time the user navigated from `"/"` to `"/chat/unc-1"` (which happens when the first message is sent and a new session is created), React fully **unmounted** the old `ChatWrapper` and **mounted a brand-new one**.

The sequence that caused duplicates:

```
1. User is on "/" (no session) — ChatWrapper-A is mounted
2. User sends first uncensored message
3. Backend creates session "unc-1", returns it
4. onSessionCreated("unc-1") fires on ChatWrapper-A:
     → setSessions([unc-1])  ← IGNORED (ChatWrapper-A is unmounting)
     → navigate("/chat/unc-1")
5. React unmounts ChatWrapper-A, mounts ChatWrapper-B for "/chat/:sessionId"
6. ChatWrapper-B starts fresh: sessions = []
7. ChatWrapper-B's fetchSessions() runs → fetches from DB → gets ["unc-1"] ✓

   ... but because ChatWrapper-A's setSessions was lost, the sidebar
   briefly flashed empty. If the user sent another message during
   that window, another session was created → TRUE DUPLICATE.

8. Also: RequireAuth re-ran its /api/auth/me/ check on every navigation
   (unnecessary auth call each time "/" ↔ "/chat/:sessionId").
```

### How it was fixed
Merged both routes into a single **layout route** (React Router v6 pattern). A layout route keeps its parent element mounted when navigating between its children:

```jsx
// AFTER (fixed) — in App.js
<Route
  element={
    <RequireAuth>
      {(userData) => <ChatWrapper mode={mode} ... />}
    </RequireAuth>
  }
>
  <Route index path="/" />
  <Route path="/chat/:sessionId" />
</Route>
```

Added `<Outlet />` to `ChatWrapper`'s render (required so React Router knows this is a layout route):

```jsx
// ChatWrapper return — App.js
return (
  <>
    <div className={`app-shell ${theme}-theme`}>
      ...
    </div>
    <Outlet />   {/* child routes have no elements, so this renders nothing */}
  </>
);
```

**Result:**
- `ChatWrapper` **stays mounted** when navigating from `"/"` to `"/chat/unc-1"` and back
- `sessions` state is never lost
- `onSessionCreated`'s `setSessions` call updates the **live** instance — the new session appears in the sidebar immediately
- `RequireAuth` calls `/api/auth/me/` only **once** on first load, not on every navigation
- No more duplicate sessions

---

## Fix 4 — Redundant Double Navigation on Session Creation

### Where the problem arose
**File:** `chatgpt-frontend/src/Components/ChatApp.js` — `sendMessage`, `askOcr`, OCR-image send, `sendMultiDebug`

Every place that created a new session called **both**:

```js
// BEFORE (broken) — 4 different places in ChatApp.js
setSessionId(res.data.session_id);           // 1. navigate("/chat/new-id")
onSessionCreated?.(res.data.session_id, ...); // 2. setSessions + navigate("/chat/new-id")
```

`setSessionId` is just an alias for `navigate("/chat/id")`.  
`onSessionCreated` (which is `handleSessionCreated` in App.js) also calls `navigate("/chat/id")`.

This pushed **two identical entries** onto the browser history stack for each new session:
- `history: [..., "/", "/chat/unc-1", "/chat/unc-1"]`  
- Pressing the Back button went to `/chat/unc-1` again instead of `"/"`.

It also caused two React Router state transitions in the same tick, which could confuse React's batching.

### How it was fixed
Removed the redundant `setSessionId` call from all 4 locations. `onSessionCreated` already handles both the `setSessions` update and the `navigate`:

```js
// AFTER (fixed) — all 4 places
if (res.data.session_id && res.data.session_id !== sessionId) {
  // setSessionId(res.data.session_id);  ← removed: onSessionCreated handles navigate
  onSessionCreated?.(res.data.session_id, res.data.title || "New chat", mode);
}
```

Affected call sites: `sendMessage` (regular/uncensored), `askOcr`, OCR image send, `sendMultiDebug`.

---

## Fix 5 — ChatView: Wrong-Mode Session Reused for Uncensored Messages

### Where the problem arose
**File:** `chat/views.py` — `ChatView.post()` session lookup (lines 791–816)

The `/api/chat/` endpoint (used by regular AND uncensored mode) looked up the session without checking its mode:

```python
# BEFORE (broken)
session = ChatSession.objects.filter(
    session_id=incoming_session_id,
    user=request.user
    # ← no mode check!
).first()
if not session:
    return Response({"error": "Session not found"}, status=404)
session_id = session.session_id
```

**Scenario:** User has a regular chat session open (`session_id = "reg-001"`, `mode = "regular"` in DB). They switch to uncensored mode in the sidebar. If the URL still contained `"reg-001"` (before navigation fully settled), the frontend sent `session_id="reg-001"` with `mode="uncensored"` to the backend. The backend found the session (it exists, owned by the user) and used it — storing uncensored messages inside a `mode="regular"` session.

This caused:
- Messages appearing in the wrong session
- The history API (`/api/history/`) filtering by `mode="uncensored"` missing those messages
- The session not appearing in the uncensored sidebar (sidebar filters by `session.mode`)

### How it was fixed
Added a mode check after finding the session. If the session exists but has a different mode, a new session in the correct mode is created silently:

```python
# AFTER (fixed)
session = ChatSession.objects.filter(
    session_id=incoming_session_id,
    user=request.user
).first()

if not session:
    return Response({"error": _SESSION_NOT_FOUND}, status=404)

if session.mode != mode:
    # Mode mismatch — create a fresh session in the correct mode
    session_id = _ensure_session(None, mode, user=request.user)
    session = ChatSession.objects.get(session_id=session_id)
else:
    session_id = session.session_id
```

---

## Fix 6 — Optimization: OpenRouter Client Rebuilt on Every Request

### Where the problem arose
**File:** `chat/views.py` — `get_uncensored_client()` function

```python
# BEFORE (inefficient)
def get_uncensored_client() -> OpenAIClient:
    """Called per-request so the API key is always read fresh..."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    ...
    return OpenAIClient(api_key=api_key, ...)  # new object every time
```

Every single uncensored chat request rebuilt the `OpenAIClient` object from scratch — reading env vars, allocating the HTTP client, setting up headers, etc. On a busy server this is wasteful.

### How it was fixed
Converted to a **lazy singleton** — the client is built once on the first call and reused for all subsequent requests:

```python
# AFTER (optimized)
_uncensored_client: "OpenAIClient | None" = None

def get_uncensored_client() -> OpenAIClient:
    global _uncensored_client
    if _uncensored_client is not None:
        return _uncensored_client

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY missing at runtime")

    _uncensored_client = OpenAIClient(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        max_retries=0,
        default_headers={"Referer": frontend_url, "X-Title": "AI Chatbox"},
    )
    return _uncensored_client
```

The Mistral client (regular mode) was already built once at module load — this brings the uncensored client to the same standard.

---

## Summary Table

| # | Bug / Issue | File(s) Changed | Root Cause | Fix |
|---|---|---|---|---|
| 1 | Multi-Debugger "server error" — no Django logs | `ChatApp.js` | Raw code pasted into HTTP header value — DOMException before request sent | Hash the message text with djb2; only safe alphanumeric chars in header |
| 2 | Multi-Debugger 404 on mode switch | `chat/views.py` | Mode-filtered session lookup returned 404 when URL had wrong-mode session | Silently create new `multi_debugger` session on mismatch |
| 3 | Duplicate session created in uncensored chat | `App.js` | `"/"` and `"/chat/:sessionId"` were separate Route elements — `ChatWrapper` remounted on every new-session navigation | Merge into single layout route so `ChatWrapper` stays mounted |
| 4 | Double browser history entry per new session | `ChatApp.js` | Both `setSessionId` (navigate) and `onSessionCreated` (also navigate) called on same new-session event | Remove redundant `setSessionId` — let `onSessionCreated` handle navigation |
| 5 | Uncensored messages stored in wrong-mode session | `chat/views.py` | `ChatView` looked up session without checking `mode` field | Add `session.mode != mode` check; create new session on mismatch |
| 6 | OpenRouter HTTP client rebuilt on every request | `chat/views.py` | `get_uncensored_client()` returned a new object each call | Lazy singleton — build once, cache, reuse |
