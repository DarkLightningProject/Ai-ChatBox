// OcrUpload.js (drop-in upgrade)
import React, { useRef, useState } from "react";
import axios from "axios";

export default function OcrUpload({ sessionId, mode = "ocr", onOcrText }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";

  const pick = () => inputRef.current?.click();

  const handleFile = async (file) => {
    if (!file) return;
    if (file.size > 20 * 1024 * 1024) {  // 20MB
      onOcrText?.("⚠️ File too large (max 20MB).", sessionId);
      return;
    }
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (sessionId) fd.append("session_id", sessionId);
      fd.append("mode", mode);

      const { data } = await axios.post(
  `${API_BASE}/api/ocr/`,
  fd,
  { headers: { "Content-Type": "multipart/form-data" } }
);

      // show in chat
      onOcrText?.(data.text, data.session_id);

      // optional: also download as .txt
      const blob = new Blob([data.text || ""], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = (file.name.replace(/\.[^.]+$/, "") || "ocr") + ".txt";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      const msg = err?.response?.data?.error || "OCR server error";
      onOcrText?.(`⚠️ ${msg}`, sessionId);
      console.error("OCR failed:", err);
    } finally {
      setBusy(false);
    }
  };

  const onChange = (e) => handleFile(e.target.files?.[0]);

  return (
    <div
      onClick={pick}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault(); setDragOver(false);
        const file = e.dataTransfer.files?.[0];
        handleFile(file);
      }}
      className="btn"
      style={{ outline: dragOver ? "2px dashed var(--primary)" : "none" }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".txt,.png,.jpg,.jpeg,.webp,.pdf"
        style={{ display: "none" }}
        onChange={onChange}
      />
      {busy ? "Reading…" : "Upload / Drop for OCR"}
    </div>
  );
}
