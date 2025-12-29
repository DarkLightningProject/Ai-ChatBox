// src/Components/ChatApp.js
import React, { useEffect, useRef, useState } from "react";
import api from "../api";
 // adjust path

import "../styles/chat.css";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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
const makeIdemKey = (sid, text) => `${sid || "new"}:${text}:${Date.now() >> 12}`;

/* ----------------------- Image Picker ------------------------ */
function ImagePicker({ images, setImages, disabled }) {
  const inputRef = useRef(null);

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
          {images.map((f, i) => {
            const url = URL.createObjectURL(f);
            return (
              <div className="thumb" key={i} title={f.name}>
                <img
                  src={url}
                  alt={`preview-${i}`}
                  onLoad={() => URL.revokeObjectURL(url)}
                />
                <button
                  className="remove"
                  onClick={() => removeAt(i)}
                  aria-label="Remove image"
                >
                  ×
                </button>
              </div>
            );
          })}
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
  " Present this comparison as a GitHub-Flavored Markdown table ONLY (no additional text). " +
  "Start with a header row (| Feature | Option A | Option B |), then a separator row (| --- | --- | --- |), then the data rows. " +
  "Keep each cell to 1-2 lines max. Use bullet points (•) within cells if needed.";

const enhanceWithTableHint = (q) => (looksComparative(q) ? q + TABLE_HINT : q);

const processTableResponse = (text, isComparative) => {
  if (!isComparative) return text;

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

/* =========================== Component =========================== */
export default function ChatApp({ sessionId, mode, setSessionId, theme,onSessionTitled,onSessionCreated,toggleSidebar  }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [queuedImages, setQueuedImages] = useState([]); // local queue (before send)
  const [loading, setLoading] = useState(false);
  const listRef = useRef(null);
  const textareaRef = useRef(null);
  const lastUserRef = useRef("");
  const [zoomSrc, setZoomSrc] = useState(null);


  // Guards against React 18 StrictMode double-effect
// Guards against React 18 StrictMode double-effect

  /* ---------------- OCR ask (text-only) ---------------- */
  const askOcr = async (question, sidOverride) => {
    const sid = sidOverride || sessionId;
    setLoading(true);
    try {
      const { data } = await api.post(`/api/ocr-qa/`, {
        session_id: sid || undefined,
        question,
        mode: "ocr",
      });

      if (data.session_id && data.session_id !== sessionId) {
            setSessionId(data.session_id);
            onSessionCreated?.(data.session_id, "New chat", "ocr");
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

  /* --------------------- Effects ------------------------ */
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        150
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


// auto-scroll chat
useEffect(() => {
  listRef.current?.lastElementChild?.scrollIntoView({ behavior: "smooth" });
}, [messages, loading]);

  useEffect(() => {
    listRef.current?.lastElementChild?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

 
  const prevSessionRef = useRef();

useEffect(() => {
  if (prevSessionRef.current && prevSessionRef.current !== sessionId) {
    setMessages([]); // clear ONLY when switching to a different session
  }
  prevSessionRef.current = sessionId;
}, [sessionId]);

useEffect(() => {
  setMessages([]);
  lastUserRef.current = "";
  setZoomSrc(null);
}, [mode]);

  // History loader with StrictMode guard + abort support
useEffect(() => {
  if (!sessionId) return;
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
          images: (m.attachments || []).map((a) => absURL(a.url)),
        });
      }

      setMessages(cleaned);
    })
    .catch((err) => {
      if (api.isCancel?.(err)) return;
      console.error("Failed to load history:", err);
    });

  return () => ctrl.abort();
}, [sessionId]);


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
  // before the try block in sendMessage()
  const wasNewSession = !sessionId;
  const sendMessage = async () => {
    const raw = input.trim();
    if (loading) return; // prevent spam while in-flight

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
    },
  }
);

      if (data.session_id && data.session_id !== sessionId) {
  const newId = data.session_id;
  setSessionId(newId);
  onSessionCreated?.(newId, data.title || "New chat", "ocr");
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
      return;
    }

    if (!raw) return;

    // Regular / Uncensored text flow
    lastUserRef.current = raw;
    const enhanced = enhanceWithTableHint(raw);
    setMessages((prev) => [...prev, { sender: "user", text: raw }]);
    setInput("");
    setLoading(true);

    // Idempotency header to dedupe double clicks
    const idem = makeIdemKey(sessionId, raw);

    try {
       const res = await api.post(
  "/api/chat/",
  {
    message: enhanced,
    mode,
    session_id: sessionId || undefined,
  },
  {
    withCredentials: true,
    headers: {
      "Idempotency-Key": idem,
    },
  }
);
      if (res.data.session_id && res.data.session_id !== sessionId) {
  setSessionId(res.data.session_id);
    onSessionCreated?.(res.data.session_id, res.data.title, mode);

  // ✅ tell parent immediately so Sidebar shows it LIVE
  if (wasNewSession) {
    onSessionCreated?.(
      res.data.session_id,
      res.data.title || "New chat",
      mode
    );
  }
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

setMessages((prev) => [...prev, { sender: "bot", text: processedText }]);

    } catch (err) {
      const status = err.response?.status;
      if (status === 429) {
        const wait = (err.response?.data?.retry_after ?? 2) * 1000;
        setMessages((prev) => [
          ...prev,
          { sender: "bot", text: "⏳ The model is busy. Retrying once…" },
        ]);
        // one auto-retry after server-suggested wait
        try {
          await new Promise((r) => setTimeout(r, wait));
          const res2 = await api.post(
  "/api/chat/",
  {
    message: enhanced,
    mode,
    session_id: sessionId || undefined,
  },
  {
    headers: { "Idempotency-Key": idem },
  }
);
         const botText2 = res2.data.reply || res2.data.response;

const processedText2 = processTableResponse(
  botText2,
  looksComparative(raw)
);

setMessages((prev) => [...prev, { sender: "bot", text: processedText2 }]);
          setLoading(false);
          return;
        } catch (err2) {
          // fallthrough to generic error below
        }
      }

      setMessages((prev) => [
        ...prev,
        { sender: "bot", text: "❌ " + (err.response?.data?.error || "Server error") },
      ]);
    } finally {
      setLoading(false);
    }
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
            : "🤖 Regular"}
        </div>

        {/* "+" add images (queues up to 4; no upload until Send) */}
       {mode === "ocr" && (
  <ImagePicker
    images={queuedImages}
    setImages={setQueuedImages}
    disabled={loading}
  />
)}
      </header>
      

      <section className="chat-history" ref={listRef} role="log" aria-live="polite">
        {messages.length === 0 && !loading && (
          <div className="welcome-message">
            <h3>Welcome to Conversa</h3>
            <p>
              {mode === "ocr"
                ? "Click ＋ to add up to 4 images, then type a prompt and press Send."
                : "Start a conversation by typing a message below"}
            </p>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.sender === "user" ? "user" : "bot"}`}>
            <div className="bubble-inner">
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
        <button className="btn" onClick={() => forceDownload(zoomSrc)}>
  Download
</button>

        <button className="btn" onClick={() => setZoomSrc(null)}>Close</button>
      </div>
    </div>
  </div>
)}

  </div>
)}

              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  a: ({ children, ...props }) => (
                    <a {...props} target="_blank" rel="noopener noreferrer">
                      {children}
                    </a>
                  ),
                  h1: ({ children, ...props }) => (
                    <h1 style={{ margin: "0.4rem 0" }} {...props}>
                      {children}
                    </h1>
                  ),
                  h2: ({ children, ...props }) => (
                    <h2 style={{ margin: "0.4rem 0" }} {...props}>
                      {children}
                    </h2>
                  ),
                  h3: ({ children, ...props }) => (
                    <h3 style={{ margin: "0.3rem 0" }} {...props}>
                      {children}
                    </h3>
                  ),
                  ul: ({ children, ...props }) => (
                    <ul style={{ paddingLeft: "1.25rem" }} {...props}>
                      {children}
                    </ul>
                  ),
                  ol: ({ children, ...props }) => (
                    <ol style={{ paddingLeft: "1.25rem" }} {...props}>
                      {children}
                    </ol>
                  ),
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
            </div>
          </div>
        ))}
<footer className="chat-inputbar">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          className="chat-input"
          placeholder={
            mode === "ocr"
              ? "Type your prompt… (Click ＋ to add images; nothing is read until Send)"
              : "Type a message (Shift+Enter for newline)…"
          }
          rows={1}
        />
        <button
          className={`btn send-btn ${theme}-theme`}
          onClick={sendMessage}
          disabled={loading || (!input.trim() && queuedImages.length === 0)}
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

      
    </div>
    
  );
}
