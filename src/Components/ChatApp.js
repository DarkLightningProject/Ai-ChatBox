// src/Components/ChatApp.js
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import "../styles/chat.css";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

/* ----------------------- Small helpers ----------------------- */
const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";
const absURL = (u) => (u?.startsWith("http") ? u : `${API_BASE}${u || ""}`);
const forceDownload = async (src) => {
  try {
    // If it’s already a blob: URL (previews), just click-download it
    if (src.startsWith("blob:")) {
      const a = document.createElement("a");
      a.href = src;
      a.download = "image.png";
      document.body.appendChild(a);
      a.click();
      a.remove();
      return;
    }

    // For server URLs, fetch → blob → download (works even cross-origin if CORS allows GET)
    const res = await fetch(absURL(src), { method: "GET" });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    // try to keep the original filename
    a.download = (src.split("/").pop() || "image").split("?")[0];
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    console.error("Download failed:", e);
  }
};


// Simple idempotency key: session + message + coarse timestamp bucket
const _hashStr = (s) => { let h = 0; for (let i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0; return (h >>> 0).toString(36); };
const makeIdemKey = (sid, text) => `${sid || "new"}:${_hashStr(text || "")}:${Date.now() >> 12}`;

/* ----------------------- Image Picker ------------------------ */
function ImagePicker({ images, setImages, disabled }) {
  const inputRef = useRef(null);

  // Create blob URLs once per images array change, not on every re-render.
  // Revoke old URLs when the array changes or the component unmounts.
  const blobUrls = useMemo(() => images.map((f) => URL.createObjectURL(f)), [images]);
  useEffect(() => () => blobUrls.forEach((u) => URL.revokeObjectURL(u)), [blobUrls]);

  const onPick = () => !disabled && inputRef.current?.click();

  const onChange = (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    const next = [...images, ...files].slice(0, 4); // cap at 4
    setImages(next);
    e.target.value = ""; // reset so the same file can be picked again
  };

  const removeAt = (idx) => {
    const next = [...images];
    next.splice(idx, 1);
    setImages(next);
  };

  return (
    <div className="image-picker">
      <button
        type="button"
        className="btn add-btn"
        onClick={onPick}
        disabled={disabled || images.length >= 4}
        title={images.length >= 4 ? "Max 4 images" : "Add images"}
        aria-label="Add images"
      >
        <span className="plus-icon">＋</span>
      </button>

      <input
        ref={inputRef}
        type="file"
        accept=".png,.jpg,.jpeg,.webp"
        multiple
        style={{ display: "none" }}
        onChange={onChange}
      />

      {images.length > 0 && (
        <div className="thumbs">
          {images.map((f, i) => (
            <div className="thumb" key={i} title={f.name}>
              <img src={blobUrls[i]} alt={`preview-${i}`} />
              <button
                className="remove"
                onClick={() => removeAt(i)}
                aria-label="Remove image"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* --------------- Comparison table helpers -------------------- */
const looksComparative = (q = "") =>
  /\b(vs|versus|compare|comparison|differences?|pros\s*\/??\s*cons|benefits|drawbacks|advantages|disadvantages)\b/i.test(
    q
  ) || q.toLowerCase().includes(" vs ");

const TABLE_HINT =
  " Present this comparison as a GitHub-Flavored Markdown table ONLY. " +
  "IMPORTANT: Do NOT wrap the table in a code block or markdown fences (no ```markdown or ``` wrappers). " +
  "Output the raw table directly. " +
  "Start with a header row (| Feature | Option A | Option B |), then a separator row (| --- | --- | --- |), then the data rows. " +
  "Keep each cell to 1-2 lines max. Use bullet points (•) within cells if needed.";

const enhanceWithTableHint = (q) => (looksComparative(q) ? q + TABLE_HINT : q);

const processTableResponse = (text, isComparative) => {
  if (!isComparative) return text;

  // 0) Unwrap tables the AI accidentally put inside ```markdown or ``` fences
  const fenceMatch = text.match(/```(?:markdown|md)?\s*\n([\s\S]*?)```/i);
  if (fenceMatch) {
    text = fenceMatch[1].trim();
  }

  // 1) Valid GFM tables
  const tableRegex =
    /^\s*\|.+\|\s*$\n^\s*\|(?:\s*:?-+:?\s*\|)+\s*$\n(^\s*\|.+\|\s*$\n?)+/gm;
  const tables = text.match(tableRegex) || [];
  if (tables.length > 0) return tables[0];

  // 2) Pipe-formatted -> convert
  const pipeTableRegex = /^(\s*\|[^\n]+\|\s*$\n?)+/gm;
  const pipeTables = text.match(pipeTableRegex) || [];
  if (pipeTables.length > 0) {
    const rows = pipeTables[0].trim().split("\n");
    if (rows.length > 1) {
      const header = rows[0];
      const separator = header.replace(/[^|]/g, "-").replace(/\|/g, "|");
      return `${header}\n${separator}\n${rows.slice(1).join("\n")}`;
    }
  }

  // 3) List → table
  const listRegex = /(\s*[-*]\s*\w+.*:\s*.+(\n\s+.+)*)+/g;
  const listMatches = text.match(listRegex) || [];
  if (listMatches.length > 0) {
    const listItems = listMatches[0].split("\n").filter((l) => l.trim());
    if (listItems.length > 0) {
      const table = ["| Feature | Details |", "| --- | --- |"];
      listItems.forEach((item) => {
        const match = item.match(/[-*]\s*([^:]+):\s*(.+)/);
        if (match) table.push(`| ${match[1]} | ${match[2]} |`);
      });
      return table.join("\n");
    }
  }

  return text;
};

/* ----------------------- OCR helper -------------------------- */
const DEFAULT_OCR_QUESTION =
  "Give a concise summary and extract key values (important dates, totals, names, addresses, emails, phone numbers).";

/* -------------------- Agent Panels (Multi-Debugger) ------------------ */
const AGENT_PANEL_META = [
  { key: "logic_analyst",         icon: "🔍", label: "Logic Analyst",
    free: "Mistral",           premium: "Gemini 2.5 Pro" },
  { key: "syntax_inspector",      icon: "🛠️", label: "Syntax & Runtime Inspector",
    free: "Mistral",            premium: "GPT-4.1" },
  { key: "perf_security_auditor", icon: "⚡", label: "Perf & Security Auditor",
    free: "Gemini 2.5 Flash",  premium: "Claude Opus 4.5" },
];

function AgentPanel({ agents, tier = "free" }) {
  const [openKey, setOpenKey] = useState(null);
  if (!agents) return null;
  const synthModel = tier === "premium" ? "Claude Sonnet 4.5" : "Mistral";

  return (
    <div className="agent-panels">
      <div className="synthesis-byline">
        🧠 Synthesized by <strong>{synthModel}</strong>
      </div>
      <div className="synthesis-divider"><span>Specialist analyses</span></div>
      {AGENT_PANEL_META.map(({ key, icon, label, free, premium }) => (
        <div key={key} className={`agent-panel agent-panel--${key}`}>
          <button
            className="agent-panel__header"
            onClick={() => setOpenKey(openKey === key ? null : key)}
          >
            <span className="agent-panel__icon">{icon}</span>
            <span className="agent-panel__name">{label}</span>
            <span className="agent-panel__model">
              {tier === "premium"
                ? premium
                : (agents[key] || "").startsWith("__GEMINI_UNAVAILABLE__") ? "Mistral (fallback)" : free}
            </span>
            <span className="agent-panel__chevron">{openKey === key ? "▲" : "▼"}</span>
          </button>
          {openKey === key && (
            <div className="agent-panel__body">
              {(() => {
                const raw = agents[key] || "_No analysis available._";
                const isFallback = raw.startsWith("__GEMINI_UNAVAILABLE__");
                const content = isFallback ? raw.replace(/^__GEMINI_UNAVAILABLE__\s*/, "") : raw;
                return (
                  <>
                    {isFallback && (
                      <div className="agent-gemini-unavailable">
                        ⚠️ Gemini unavailable — analysis provided by Mistral
                      </div>
                    )}
                    <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>{content}</ReactMarkdown>
                  </>
                );
              })()}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/* =========================== Component =========================== */
// Returns the active ban entry for the current mode (or full_account ban), or null
function getActiveBan(bans, mode, tier) {
  if (!bans) return null;
  if (bans["full_account"]) return bans["full_account"];
  if (mode && bans[mode]) return bans[mode];
  // multi_debugger_premium only applies when tier === "premium"
  if (mode === "multi_debugger" && tier === "premium" && bans["multi_debugger_premium"]) {
    return bans["multi_debugger_premium"];
  }
  return null;
}

export default function ChatApp({ sessionId, fallbackSessionId, mode, setSessionId, theme, isPremium = false, bans, onBanDetected, onSessionTitled, onSessionCreated, toggleSidebar }) {
  const navigate = useNavigate();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [queuedImages, setQueuedImages] = useState([]); // local queue (before send)
  const [loading, setLoading] = useState(false);
  const [debugTier, setDebugTier] = useState("free"); // "free" | "premium"
  const listRef = useRef(null);
  const textareaRef = useRef(null);
  const lastUserRef = useRef("");
  const isSendingRef = useRef(false); // sync guard against rapid double-submit
  // Tracks sessions created mid-flight so the history effect doesn't overwrite
  // in-memory messages (which carry the `agents` field) with DB history that lacks it.
  const skipHistoryForRef = useRef(null);
  const [zoomSrc, setZoomSrc] = useState(null);
  const [copiedIndex, setCopiedIndex] = useState(null);
  const [editingIdx, setEditingIdx] = useState(null);
  const [editingText, setEditingText] = useState("");

  // Active ban for this mode (full_account OR mode-specific)
  const activeBan = getActiveBan(bans, mode, debugTier);

  const [emailNotVerified, setEmailNotVerified] = useState(false);
  const [resendState, setResendState] = useState("idle"); // idle | sending | sent | failed

  const handleEmailNotVerified = (err) => {
    if (err.response?.status === 403 && err.response?.data?.error === "email_not_verified") {
      setEmailNotVerified(true);
      return true;
    }
    return false;
  };

  const handleResendVerification = async () => {
    setResendState("sending");
    try {
      await api.post("/api/auth/resend-verification/");
      setResendState("sent");
    } catch {
      setResendState("failed");
    }
  };

  // Call when a 403 with error:"banned" comes back from any chat endpoint
  const handleBan403 = (err) => {
    const data = err.response?.data;
    if (err.response?.status === 403 && data?.error === "banned") {
      onBanDetected?.({
        feature:        data.feature        || mode,
        ban_expires_at: data.ban_expires_at || null,
        ban_reason:     data.ban_reason     || "Violation of terms of service",
      });
      return true;
    }
    return false;
  };


  // Guards against React 18 StrictMode double-effect

  /* ---------------- OCR ask (text-only) ---------------- */
  const askOcr = async (question, sidOverride) => {
    const sid = sidOverride || sessionId;
    setLoading(true);
    try {
      const { data } = await api.post(
        `/api/ocr-qa/`,
        { session_id: sid || undefined, question, mode: "ocr" },
        { headers: { "Idempotency-Key": makeIdemKey(sid, question) } }
      );

      if (data.session_id && data.session_id !== sessionId) {
        onSessionCreated?.(data.session_id, data.title || "New chat", "ocr");
      }
      if (data.title) {
        onSessionTitled?.(data.session_id, data.title);
      }

      const processedText = processTableResponse(
        data.answer,
        looksComparative(lastUserRef.current)
      );

      setMessages((m) => [...m, { sender: "bot", text: processedText }]);
    } catch (err) {
      const msg = err?.response?.data?.error || "OCR-QA server error";
      setMessages((m) => [...m, { sender: "bot", text: "❌ " + msg }]);
    } finally {
      setLoading(false);
    }
  };

  /* -------------- Multi-Debugger send ------------------- */
  const sendMultiDebug = async (raw) => {
    lastUserRef.current = raw;
    setMessages((prev) => [...prev, { sender: "user", text: raw, msgId: null }]);
    setInput("");
    setLoading(true);
    try {
      const res = await api.post(
        "/api/multi-debug/",
        { message: raw, session_id: sessionId || undefined, tier: debugTier },
        { headers: { "Idempotency-Key": makeIdemKey(sessionId, raw) } },
      );
      if (res.data.session_id && res.data.session_id !== sessionId) {
        skipHistoryForRef.current = res.data.session_id;
        onSessionCreated?.(res.data.session_id, res.data.title || "New chat", "multi_debugger");
      }
      if (res.data.title) {
        onSessionTitled?.(res.data.session_id, res.data.title);
      }
      setMessages((prev) => {
        const updated = [...prev];
        const userIdx = updated.length - 1;
        if (updated[userIdx]?.sender === "user") updated[userIdx] = { ...updated[userIdx], msgId: res.data.msg_id };
        return [...updated, { sender: "bot", text: res.data.reply, agents: res.data.agents, tier: res.data.tier || debugTier }];
      });
    } catch (err) {
      console.error("[MultiDebug] error:", err.message, "status:", err.response?.status, "data:", err.response?.data);
      const httpStatus = err.response?.status;
      const errMsg = err.response?.data?.error || err.response?.data?.detail || (httpStatus ? `HTTP ${httpStatus}` : err.message) || "Multi-Debug server error";

      // 403 = banned OR not premium OR email not verified
      if (httpStatus === 403) {
        if (handleEmailNotVerified(err)) return;
        if (handleBan403(err)) return;
        setDebugTier("free");
        setMessages((prev) => [
          ...prev,
          { sender: "bot", text: `🔒 ${errMsg} [Switched back to Free tier]` },
        ]);
        return;
      }

      // 429 = rate limit exceeded
      if (httpStatus === 429) {
        const detail = err.response?.data?.detail || "";
        const wait = err.response?.data?.retry_after;
        const waitMsg = wait ? ` Try again in ${Math.ceil(wait / 60)} min.` : "";
        setMessages((prev) => [
          ...prev,
          { sender: "bot", text: `⏳ Rate limit reached.${waitMsg}` },
        ]);
        return;
      }

      // 400 = bad input (greeting, too short, etc.)
      if (httpStatus === 400) {
        setMessages((prev) => {
          const updated = [...prev];
          // Replace the user bubble with the error so we don't orphan it
          updated[updated.length - 1] = { sender: "bot", text: `⚠️ ${errMsg}` };
          return updated;
        });
        return;
      }

      setMessages((prev) => [
        ...prev,
        { sender: "bot", text: `❌ ${errMsg}` },
      ]);
    } finally {
      setLoading(false);
      isSendingRef.current = false;
    }
  };

  /* --------------------- Effects ------------------------ */
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        380
      )}px`;
    }
  }, [input]);

  useEffect(() => {
  if (mode !== "ocr" && queuedImages.length) {
    setQueuedImages([]); // prevent accidental image send in non-OCR modes
  }
}, [mode, queuedImages.length]);

useEffect(() => {
  const onKey = (e) => e.key === "Escape" && setZoomSrc(null);
  window.addEventListener("keydown", onKey);
  return () => window.removeEventListener("keydown", onKey);
}, []);


useEffect(() => {
  listRef.current?.lastElementChild?.scrollIntoView({ behavior: "smooth" });
}, [messages, loading]);

 
  const prevSessionRef = useRef();

useEffect(() => {
  const prev = prevSessionRef.current;
  prevSessionRef.current = sessionId;

  if (prev === sessionId) return; // no change

  // Always reset in-flight state so switching sessions never leaves a stuck
  // loading spinner or a disabled send button.
  setLoading(false);
  isSendingRef.current = false;
  setInput("");

  // Don't clear messages if this session was just created by the current send —
  // skipHistoryForRef being set means messages are already correct in state.
  if (skipHistoryForRef.current === sessionId) return;

  setMessages([]);
  setQueuedImages([]);
  setZoomSrc(null);
  setEditingIdx(null);
  setEditingText("");
}, [sessionId]);

useEffect(() => {
  setMessages([]);
  lastUserRef.current = "";
  setZoomSrc(null);
}, [mode]);

  // History loader with StrictMode guard + abort support
useEffect(() => {
  if (!sessionId) return;

  // Session was just created in-flight (e.g. by sendMultiDebug). The messages
  // are already in state with the full `agents` payload. Skip the DB fetch so
  // we don't overwrite them with history rows that lack that field.
  if (skipHistoryForRef.current === sessionId) {
    skipHistoryForRef.current = null;
    return;
  }

  const ctrl = new AbortController();

  api
    .get(`/api/history/`, {
      // If your backend now returns ALL messages in a session, this is enough:
      params: { session_id: sessionId, mode },
      signal: ctrl.signal,
    })
    .then((res) => {
      const rows = res.data.history || [];

      const cleaned = [];
      for (let i = 0; i < rows.length; i++) {
        const m = rows[i];
        // Skip system messages (raw OCR-extracted text) — not meant for display
        if (m.role === "system") continue;
        const isUser = m.role === "user";

        // find the last user question before this message (to decide if it's comparative)
        const prevUserText = (() => {
          for (let j = i - 1; j >= 0; j--) {
            if (rows[j].role === "user") return rows[j].content || "";
          }
          return "";
        })();

        // 1) Strip TABLE_HINT from user messages (so you don't see techy instructions you didn't type)
        let text = (m.content || "");
        if (isUser) {
          text = text.replace(TABLE_HINT, "").trim();
        }

        // 2) Re-run table post-processing on assistant messages, based on the prior user question
        if (!isUser) {
          const prevQ = prevUserText.replace(TABLE_HINT, "");
          text = processTableResponse(text, looksComparative(prevQ));
        }

        cleaned.push({
          sender: isUser ? "user" : "bot",
          text,
          msgId: m.msg_id || null,
          images: (m.attachments || []).map((a) => absURL(a.url)),
          agents: m.agents || null,
          tier: m.agents?._tier || (m.agents ? "free" : undefined),
          _versionData: m.version_data || null, // raw DB data; resolved below
        });
      }

      // Reconstruct full version history for edited messages.
      // DB stores old versions in agent_data; current version = msg content + next bot msg.
      const withVersions = cleaned.map((m, i) => {
        if (m.sender !== "user" || !m._versionData?.versions?.length) {
          const { _versionData, ...rest } = m;
          return rest;
        }
        const nextBot = cleaned[i + 1];
        const currentVersion = {
          userText:  m.text,
          botReply:  nextBot?.text  || "",
          botAgents: nextBot?.agents || null,
          botTier:   nextBot?.tier   || null,
        };
        const allVersions = [...m._versionData.versions, currentVersion];
        const { _versionData, ...rest } = m;
        return { ...rest, versions: allVersions, versionIdx: allVersions.length - 1 };
      });

      setMessages(withVersions);
    })
    .catch((err) => {
      if (err?.code === "ERR_CANCELED" || err?.name === "CanceledError") return;
      console.error("Failed to load history:", err);
      setMessages([{ sender: "bot", text: "❌ Failed to load chat history. Please refresh the page." }]);
    });

  return () => ctrl.abort();
}, [sessionId, mode]);


  /* ---- Push a user bubble immediately with local blob URLs ---- */
  const pushUserBubble = (text, images) => {
    setMessages((prev) => [
      ...prev,
      {
        sender: "user",
        text,
        images: (images || []).map((f) => URL.createObjectURL(f)),
      },
    ]);
  };

  /* -------------------- Send message -------------------- */
  const sendMessage = async () => {
    const raw = input.trim();
    if (loading || isSendingRef.current) return; // sync + state guard against rapid double-submit
    isSendingRef.current = true;

    // If images are queued → send prompt + images together (no pre-read)
    if (mode === "ocr" && queuedImages.length > 0) {
      setLoading(true);
      try {
        // 1) show bubble with blob previews
        pushUserBubble(raw || "Analyze these images", queuedImages);

        // 2) send to server
        const fd = new FormData();
        fd.append("message", raw || "Analyze these images");
        if (sessionId) fd.append("session_id", sessionId);
        fd.append("mode", "ocr");
        queuedImages.forEach((f) => fd.append("images", f));

        const { data } = await api.post(
          "/api/gemini-with-images/",
          fd,
          {
            withCredentials: true,
            headers: {
              "Content-Type": "multipart/form-data",
              "Idempotency-Key": makeIdemKey(sessionId, raw || "Analyze these images"),
            },
          }
        );

      if (data.session_id && data.session_id !== sessionId) {
  onSessionCreated?.(data.session_id, data.title || "New chat", "ocr");
}
if (data.title) {
  onSessionTitled?.(data.session_id, data.title);
}


        // 3) swap the last user bubble's blob URLs → server URLs
        const saved = (data.attachments || []).map((a) => absURL(a.url));
        setMessages((prev) => {
          const copy = [...prev];
          for (let i = copy.length - 1; i >= 0; i--) {
            if (
              copy[i].sender === "user" &&
              Array.isArray(copy[i].images) &&
              copy[i].images.length
            ) {
              // Revoke old blob URLs to free memory
              try {
                copy[i].images.forEach((u) => u.startsWith("blob:") && URL.revokeObjectURL(u));
              } catch (_) {}
              copy[i] = { ...copy[i], images: saved };
              break;
            }
          }
          return copy;
        });

        // 4) bot reply
        setMessages((prev) => [...prev, { sender: "bot", text: data.response }]);
      } catch (err) {
        if (handleEmailNotVerified(err)) return;
        // Revoke any blob URLs that are still in the last user bubble
        setMessages((prev) => {
          const copy = [...prev];
          for (let i = copy.length - 1; i >= 0; i--) {
            if (copy[i].sender === "user" && Array.isArray(copy[i].images) && copy[i].images.length) {
              copy[i].images.forEach((u) => { try { if (u.startsWith("blob:")) URL.revokeObjectURL(u); } catch (_) {} });
              break;
            }
          }
          return copy;
        });
        setMessages((prev) => [
          ...prev,
          {
            sender: "bot",
            text: "❌ " + (err.response?.data?.error || "Server error"),
          },
        ]);
      } finally {
        setInput("");
        setQueuedImages([]); // clear queue after send
        setLoading(false);
        isSendingRef.current = false;
      }
      return;
    }

    // No images queued → existing flows
    if (mode === "ocr") {
      const q = enhanceWithTableHint(raw || DEFAULT_OCR_QUESTION);
      if (raw) {
        lastUserRef.current = raw;
        setMessages((prev) => [...prev, { sender: "user", text: raw }]);
      } else {
        lastUserRef.current = DEFAULT_OCR_QUESTION;
      }
      setInput("");
      await askOcr(q);
      isSendingRef.current = false;
      return;
    }

    if (!raw) { isSendingRef.current = false; return; }

    if (mode === "multi_debugger") {
      await sendMultiDebug(raw);
      return; // isSendingRef.current = false is handled inside sendMultiDebug's finally
    }

    // Regular / Uncensored text flow
    lastUserRef.current = raw;
    const enhanced = enhanceWithTableHint(raw);
    setMessages((prev) => [...prev, { sender: "user", text: raw, msgId: null }]);
    setInput("");
    setLoading(true);

    // Use the URL session if available; fall back to the most-recent session for
    // this mode (passed from ChatWrapper) so sends from "/" never create a new
    // session when one already exists.
    const effectiveSid = sessionId || fallbackSessionId;
    const idem = makeIdemKey(effectiveSid, raw);

    try {
       const res = await api.post(
  "/api/chat/",
  {
    message: enhanced,
    mode,
    session_id: effectiveSid || undefined,
  },
  {
    withCredentials: true,
    headers: {
      "Idempotency-Key": idem,
    },
  }
);
      if (res.data.session_id && res.data.session_id !== sessionId) {
        // Skip history reload — messages are already in state from this send
        skipHistoryForRef.current = res.data.session_id;
        onSessionCreated?.(res.data.session_id, res.data.title || "New chat", mode);
      }

// ✅ if backend sent/confirmed a title, trigger typing animation in sidebar
if (res.data.title) {
  onSessionTitled?.(res.data.session_id, res.data.title);
}




const botText = res.data.reply || res.data.response;

const processedText = processTableResponse(
  botText,
  looksComparative(raw)
);

setMessages((prev) => {
  const updated = [...prev];
  const userIdx = updated.length - 1;
  if (updated[userIdx]?.sender === "user") updated[userIdx] = { ...updated[userIdx], msgId: res.data.msg_id };
  return [...updated, { sender: "bot", text: processedText }];
});

    } catch (err) {
      if (handleEmailNotVerified(err)) return;
      if (handleBan403(err)) return;
      const status = err.response?.status;
      if (status === 429) {
        const wait = (err.response?.data?.retry_after ?? 2) * 1000;
        // Backend includes session_id in 429 body so the retry can reuse it.
        // Do NOT announce the session to the sidebar yet — messages aren't in DB
        // until the retry succeeds. Announcing early causes an empty session on refresh.
        const rateLimitSid = err.response?.data?.session_id;
        const retryEffectiveSid = rateLimitSid || effectiveSid;

        setMessages((prev) => [
          ...prev,
          { sender: "bot", text: "⏳ The model is busy. Retrying once…" },
        ]);
        try {
          await new Promise((r) => setTimeout(r, wait));
          const res2 = await api.post(
            "/api/chat/",
            { message: enhanced, mode, session_id: retryEffectiveSid || undefined },
            { headers: { "Idempotency-Key": idem } }
          );
          // Retry succeeded — messages are now saved in DB.
          // Announce the session to the sidebar only now.
          if (res2.data.session_id && res2.data.session_id !== sessionId) {
            skipHistoryForRef.current = res2.data.session_id;
            onSessionCreated?.(res2.data.session_id, res2.data.title || "New chat", mode);
          }
          if (res2.data.title) {
            onSessionTitled?.(res2.data.session_id, res2.data.title);
          }
          const botText2 = res2.data.reply || res2.data.response;
          const processedText2 = processTableResponse(botText2, looksComparative(raw));
          // Replace the "retrying" placeholder with the actual bot reply
          setMessages((prev) => {
            const filtered = prev.filter((m) => m.text !== "⏳ The model is busy. Retrying once…");
            return [...filtered, { sender: "bot", text: processedText2 }];
          });
          return;
        } catch (err2) {
          // Both attempts failed — show final error and stop
          setMessages((prev) => [
            ...prev,
            { sender: "bot", text: "❌ " + (err2.response?.data?.error || "Rate limited. Please try again.") },
          ]);
          return;
        }
      }

      setMessages((prev) => [
        ...prev,
        { sender: "bot", text: "❌ " + (err.response?.data?.error || "Server error") },
      ]);
    } finally {
      setLoading(false);
      isSendingRef.current = false;
    }
  };

  /* -------------------- Edit / Version navigation -------------------- */
  const startEdit = (idx) => {
    if (loading || idx < 0 || idx >= messages.length) return;
    setEditingIdx(idx);
    setEditingText(messages[idx]?.text || "");
  };

  const cancelEdit = () => { setEditingIdx(null); setEditingText(""); };

  const submitEdit = async (idx) => {
    const newText = editingText.trim();
    if (!newText || loading || isSendingRef.current) return;
    if (idx < 0 || idx >= messages.length) return;
    isSendingRef.current = true;
    setEditingIdx(null);
    setEditingText("");
    setLoading(true);

    const userMsg = messages[idx];
    const botMsg  = messages[idx + 1];
    const prevVersions = userMsg.versions || [{
      userText: userMsg.text,
      botReply: botMsg?.text   || "",
      botAgents: botMsg?.agents || null,
      botTier:   botMsg?.tier   || null,
    }];
    const keepVersions = prevVersions.slice(0, (userMsg.versionIdx ?? prevVersions.length - 1) + 1);

    setMessages((prev) => [
      ...prev.slice(0, idx),
      { sender: "user", text: newText, versions: keepVersions, versionIdx: keepVersions.length },
    ]);

    const trimFromId = userMsg.msgId || null;

    try {
      let botReply, botAgents = null, botTier = null, newMsgId = null;
      const enhanced = enhanceWithTableHint(newText);
      if (mode === "multi_debugger") {
        const res = await api.post(
          "/api/multi-debug/",
          {
            message: enhanced, session_id: sessionId || undefined, tier: debugTier,
            trim_from_id: trimFromId,
            version_data: { versions: keepVersions, versionIdx: keepVersions.length },
          },
          { headers: { "Idempotency-Key": makeIdemKey(sessionId, newText) } },
        );
        botReply = processTableResponse(res.data.reply, looksComparative(newText));
        botAgents = res.data.agents; botTier = res.data.tier || debugTier;
        newMsgId = res.data.msg_id;
      } else {
        const res = await api.post("/api/chat/",
          {
            message: enhanced, mode, session_id: sessionId || undefined,
            trim_from_id: trimFromId,
            version_data: { versions: keepVersions, versionIdx: keepVersions.length },
          },
          { headers: { "Idempotency-Key": makeIdemKey(sessionId, newText) } }
        );
        botReply = processTableResponse(res.data.reply || res.data.response, looksComparative(newText));
        newMsgId = res.data.msg_id;
      }
      const newVersion = { userText: newText, botReply, botAgents, botTier };
      const allVersions = [...keepVersions, newVersion];
      setMessages((prev) => {
        const updated = [...prev];
        updated[idx] = { ...updated[idx], msgId: newMsgId, versions: allVersions, versionIdx: allVersions.length - 1 };
        return [...updated, { sender: "bot", text: botReply, agents: botAgents, tier: botTier }];
      });
    } catch (err) {
      if (handleEmailNotVerified(err)) return;
      if (handleBan403(err)) return;
      const httpStatus = err.response?.status;
      const errMsg = err.response?.data?.error || "Server error";
      if (httpStatus === 403 && mode === "multi_debugger") {
        setDebugTier("free");
        setMessages((prev) => [
          ...prev,
          { sender: "bot", text: `🔒 ${errMsg} [Switched back to Free tier]` },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          { sender: "bot", text: `❌ ${errMsg}` },
        ]);
      }
    } finally {
      setLoading(false);
      isSendingRef.current = false;
    }
  };

  const navigateVersion = (userMsgIdx, delta) => {
    setMessages((prev) => {
      const updated = [...prev];
      const msg = updated[userMsgIdx];
      const versions = msg.versions || [];
      const curIdx = msg.versionIdx ?? versions.length - 1;
      const newIdx = curIdx + delta;
      if (newIdx < 0 || newIdx >= versions.length) return prev;
      const v = versions[newIdx];
      updated[userMsgIdx] = { ...msg, text: v.userText, versionIdx: newIdx };
      if (updated[userMsgIdx + 1]) {
        const displayText = processTableResponse(v.botReply || "", looksComparative(v.userText));
        updated[userMsgIdx + 1] = { ...updated[userMsgIdx + 1], text: displayText, agents: v.botAgents, tier: v.botTier };
      }
      return updated;
    });
  };

  const onKeyDown = (e) => {
    if (loading) return; // ignore presses while busy
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (mode === "ocr") sendMessage();
      else if (input.trim()) sendMessage();
    }
  };

  /* ------------------------ Render ----------------------- */
  return (

    <div className={`chat-wrap ${theme}-theme`} aria-busy={loading}>
        {/* Mobile Menu Button (scrolls with content) */}
        
      <button
        className="mobile-menu-btn"
        onClick={() => toggleSidebar?.()}
      >
        ☰ Menu
      </button>

      <header className="chat-header">
        <div className="chat-pill">
          {mode === "uncensored"
            ? "🔥 Uncensored"
            : mode === "ocr"
            ? "📄 OCR + Ask"
            : mode === "multi_debugger"
            ? "🔍 Multi-Debugger"
            : "🤖 Regular"}
        </div>

        {/* Tier toggle — only visible in multi-debugger mode */}
        {mode === "multi_debugger" && (
          <div className="tier-toggle">
            <button
              className={`tier-btn ${debugTier === "free" ? "active" : ""}`}
              onClick={() => setDebugTier("free")}
              title="Free: Gemini Flash (Logic + Perf) · Mistral (Syntax + Synthesis)"
            >
              🆓 Free
            </button>
            <button
              className={`tier-btn ${debugTier === "premium" ? "active" : ""}`}
              onClick={() => {
                if (!isPremium) { navigate("/checkout"); return; }
                setDebugTier("premium");
              }}
              title={isPremium ? "Premium: Gemini 2.5 Pro · GPT-4.1 · Claude Opus · Claude Sonnet" : "Upgrade to Pro to unlock premium tier"}
            >
              {isPremium ? "⭐" : "🔒"} Premium
            </button>
          </div>
        )}

        {/* "+" add images (queues up to 4; no upload until Send) */}
       {mode === "ocr" && (
  <ImagePicker
    images={queuedImages}
    setImages={setQueuedImages}
    disabled={loading}
  />
)}
      </header>

      {/* ── Email Verification Banner ──────────────────────────────── */}
      {emailNotVerified && (
        <div className="ban-banner" role="alert" style={{ background: "#fff8e1", borderLeft: "4px solid #f59e0b" }}>
          <span className="ban-banner__icon">✉️</span>
          <div className="ban-banner__body">
            <strong className="ban-banner__title" style={{ color: "#92400e" }}>Email not verified</strong>
            <span className="ban-banner__reason" style={{ color: "#78350f" }}>
              Please verify your email to use this feature. Check your inbox for the verification link.
            </span>
            {resendState === "sent" ? (
              <span className="ban-banner__expiry" style={{ color: "#15803d" }}>Verification email sent! Check your inbox.</span>
            ) : (
              <button
                className="ban-banner__expiry"
                onClick={handleResendVerification}
                disabled={resendState === "sending"}
                style={{ background: "none", border: "none", cursor: "pointer", color: "#2c5364", textDecoration: "underline", padding: 0, font: "inherit" }}
              >
                {resendState === "sending" ? "Sending…" : resendState === "failed" ? "Failed — try again" : "Resend verification email"}
              </button>
            )}
          </div>
        </div>
      )}

      {/* ── Ban Banner ─────────────────────────────────────────────── */}
      {activeBan && (
        <div className="ban-banner" role="alert">
          <span className="ban-banner__icon">⛔</span>
          <div className="ban-banner__body">
            <strong className="ban-banner__title">
              {bans?.["full_account"] ? "Account suspended" : "This mode is suspended"}
            </strong>
            <span className="ban-banner__reason">
              {activeBan.reason || "Violation of terms of service"}
            </span>
            {activeBan.expires_at ? (
              <span className="ban-banner__expiry">
                Suspension lifts on{" "}
                {new Date(activeBan.expires_at).toLocaleString(undefined, {
                  year: "numeric", month: "long", day: "numeric",
                  hour: "2-digit", minute: "2-digit",
                })}
              </span>
            ) : (
              <span className="ban-banner__expiry">This suspension is permanent.</span>
            )}
          </div>
        </div>
      )}

      <section className="chat-history" ref={listRef} role="log" aria-live="polite">
        {messages.length === 0 && !loading && (
          <div className="welcome-message">
            <h3>Welcome to Conversa</h3>
            <p>
              {mode === "ocr"
                ? "Click ＋ to add up to 4 images, then type a prompt and press Send."
                : mode === "multi_debugger"
                ? "Paste your buggy code or describe the bug — three AI specialists will analyze it in parallel, then a Synthesizer delivers the unified fix."
                : "Start a conversation by typing a message below"}
            </p>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.sender === "user" ? "user" : "bot"}`}>
            <div className="bubble-inner">
              {m.sender === "user" && editingIdx === i ? (
                /* ---- Edit mode ---- */
                <div className="edit-area">
                  <textarea
                    className="edit-textarea"
                    value={editingText}
                    onChange={(e) => setEditingText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitEdit(i); }
                      if (e.key === "Escape") cancelEdit();
                    }}
                    autoFocus
                  />
                  <div className="edit-actions">
                    <button className="edit-save-btn" onClick={() => submitEdit(i)}>Send</button>
                    <button className="edit-cancel-btn" onClick={cancelEdit}>Cancel</button>
                  </div>
                </div>
              ) : (
                /* ---- Normal display ---- */
                <>
                  {m.images?.length > 0 && (
                    <div className="thumbs" style={{ marginBottom: 8 }}>
                      {m.images.map((src, idx) => (
                        <div className="thumb" key={idx}>
                          <img
                            src={src}
                            alt={`sent-${idx}`}
                            onClick={() => setZoomSrc(src)}
                            style={{ cursor: "zoom-in" }}
                          />
                        </div>
                      ))}
                    </div>
                  )}
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeRaw]}
                    components={{
                      code: ({ node, inline, className, children, ...props }) => {
                        const match = /language-(\w+)/.exec(className || "");
                        const language = match ? match[1] : '';
                        const codeString = String(children).replace(/\n$/, "");
                        return !inline && match ? (
                          <div className="code-block">
                            <div className="code-header">
                              <span className="code-language">{language}</span>
                              <button
                                className="code-copy-btn"
                                onClick={() => { navigator.clipboard.writeText(codeString).catch(() => {}); }}
                              >
                                📋 Copy
                              </button>
                            </div>
                            <SyntaxHighlighter
                              language={language}
                              style={vscDarkPlus}
                              customStyle={{ margin: 0, borderRadius: 0, background: '#1e1e1e' }}
                            >
                              {codeString}
                            </SyntaxHighlighter>
                          </div>
                        ) : (
                          <code className={className} {...props}>{children}</code>
                        );
                      },
                      a: ({ children, ...props }) => (
                        <a {...props} target="_blank" rel="noopener noreferrer">{children}</a>
                      ),
                      h1: ({ children, ...props }) => <h1 style={{ margin: "0.4rem 0" }} {...props}>{children}</h1>,
                      h2: ({ children, ...props }) => <h2 style={{ margin: "0.4rem 0" }} {...props}>{children}</h2>,
                      h3: ({ children, ...props }) => <h3 style={{ margin: "0.3rem 0" }} {...props}>{children}</h3>,
                      ul: ({ children, ...props }) => <ul style={{ paddingLeft: "1.25rem" }} {...props}>{children}</ul>,
                      ol: ({ children, ...props }) => <ol style={{ paddingLeft: "1.25rem" }} {...props}>{children}</ol>,
                      table: ({ children }) => (
                        <div className="table-container">
                          <table className="responsive-table">{children}</table>
                        </div>
                      ),
                      th: ({ children }) => <th className="table-header">{children}</th>,
                      td: ({ children }) => <td className="table-cell">{children}</td>,
                    }}
                  >
                    {m.text || ""}
                  </ReactMarkdown>
                  {m.agents && <AgentPanel agents={m.agents} tier={m.tier || "free"} />}
                </>
              )}
            </div>

            {/* Pencil + version nav — user bubbles only, not while editing */}
            {m.sender === "user" && editingIdx !== i && (
              <div className="user-msg-controls">
                {m.versions?.length > 1 && (
                  <div className="version-nav">
                    <button
                      className="version-btn"
                      onClick={() => navigateVersion(i, -1)}
                      disabled={(m.versionIdx ?? m.versions.length - 1) === 0}
                    >&#8249;</button>
                    <span className="version-label">
                      {(m.versionIdx ?? m.versions.length - 1) + 1} / {m.versions.length}
                    </span>
                    <button
                      className="version-btn"
                      onClick={() => navigateVersion(i, 1)}
                      disabled={(m.versionIdx ?? m.versions.length - 1) === m.versions.length - 1}
                    >&#8250;</button>
                  </div>
                )}
                {!loading && (
                  <button className="edit-pencil-btn" onClick={() => startEdit(i)} title="Edit message">
                    ✏️
                  </button>
                )}
              </div>
            )}

            {m.sender === "bot" && (
              <button
                className={`copy-btn-outside ${copiedIndex === i ? 'copied' : ''}`}
                onClick={() => {
                  navigator.clipboard.writeText(m.text || "").catch(() => {});
                  setCopiedIndex(i);
                  setTimeout(() => setCopiedIndex(null), 2000);
                }}
                title="Copy message"
              >
                {copiedIndex === i ? "✓" : "📋"}
              </button>
            )}
          </div>
        ))}
<footer className="chat-inputbar">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          className="chat-input"
          disabled={!!activeBan}
          placeholder={
            activeBan
              ? (bans?.["full_account"] ? "Your account is suspended — messaging is disabled" : "This mode is suspended — switch to another mode")
              : mode === "ocr"
              ? "Type your prompt… (Click ＋ to add images; nothing is read until Send)"
              : mode === "multi_debugger"
              ? "Paste your code or describe the bug… (Shift+Enter for newline)"
              : "Type a message (Shift+Enter for newline)…"
          }
          rows={1}
        />
        <button
          className={`btn send-btn ${theme}-theme`}
          onClick={sendMessage}
          disabled={loading || !!activeBan || (!input.trim() && queuedImages.length === 0)}
          aria-label="Send message"
          title={
            loading
              ? "Working…"
              : queuedImages.length > 0
              ? "Send images + prompt"
              : "Send"
          }
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M22 2L11 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            <path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
          </svg>
        </button>
      </footer>
        {loading && (
          <div className="typing" role="status" aria-live="assertive">
            <div className="typing-indicator">
              <span></span><span></span><span></span>
            </div>
          </div>
        )}
      </section>

      {/* Lightbox — rendered once outside the messages loop */}
      {zoomSrc && (
        <div
          className="lightbox"
          role="dialog"
          aria-modal="true"
          onClick={() => setZoomSrc(null)}
        >
          <div className="lightbox-inner" onClick={(e) => e.stopPropagation()}>
            <img src={zoomSrc} alt="zoomed" />
            <div className="lightbox-actions">
              <button className="btn" onClick={() => forceDownload(zoomSrc)}>Download</button>
              <button className="btn" onClick={() => setZoomSrc(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      
    </div>
    
  );
}
