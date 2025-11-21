import React, { useState, useEffect, useRef, memo } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import "../styles/layout.css";

const SessionTitle = memo(function SessionTitle({ title, justRenamed, onDoubleClick }) {
  const [displayedText, setDisplayedText] = useState(title || "");
  const [typing, setTyping] = useState(false);

  const timeoutRef = useRef(null);
  const runTokenRef = useRef(0);
  const prevTitleRef = useRef(title);

  useEffect(() => () => timeoutRef.current && clearTimeout(timeoutRef.current), []);

  useEffect(() => {
    if (!justRenamed) {
      if (prevTitleRef.current !== title) {
        setDisplayedText(title || "");
        prevTitleRef.current = title;
      }
      setTyping(false);
      return;
    }

    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    const myRun = ++runTokenRef.current;

    const text = title || "";
    const len = text.length;
    setTyping(true);
    setDisplayedText("");
    let i = 0;

    const step = () => {
      if (runTokenRef.current !== myRun) return;
      i += 1;
      if (i <= len) {
        setDisplayedText(text.slice(0, i));
        timeoutRef.current = setTimeout(step, 55);
      } else {
        prevTitleRef.current = text;
        timeoutRef.current = setTimeout(() => {
          if (runTokenRef.current === myRun) setTyping(false);
        }, 400);
      }
    };

    step();
    return () => timeoutRef.current && clearTimeout(timeoutRef.current);
  }, [justRenamed, title]);

  return (
    <span className="typing-wrapper" onDoubleClick={onDoubleClick}>
      <span className="text">{displayedText}</span>
      {typing && <span className="cursor" />}
    </span>
  );
}, (prev, next) => prev.title === next.title && prev.justRenamed === next.justRenamed);

function Sidebar({
  sessions,
  onSessionSelect,
  currentSession,
  onModeChange,
  currentMode,
  onNewSession,
  onDeleted,
  onRenamed,
  theme,
  toggleTheme,
}) {
  const [menuOpen, setMenuOpen] = useState(null);
  const [editTitle, setEditTitle] = useState("");
  const navigate = useNavigate();
  const menuRef = useRef();

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(null);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const deleteSession = async (session_id) => {
    try {
      await axios.delete(
        `http://localhost:8000/api/sessions/${session_id}/delete/`
      );
      onDeleted?.(session_id);
      setMenuOpen(null);
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  };

  const renameSession = async (session_id) => {
    if (!editTitle.trim()) return;
    try {
      await axios.put(
        `http://localhost:8000/api/sessions/${session_id}/rename/`,
        { title: editTitle }
      );
      onRenamed?.(session_id, editTitle);
      setMenuOpen(null);
    } catch (err) {
      console.error("Failed to rename session:", err);
    }
  };

  return (
    <aside className={`sidebar ${theme}-theme`}>
      <div className="sidebar-top">
        <button
          className={`btn new-btn ${theme}-theme`}
          onClick={onNewSession}
        >
          <span className="plus">+</span> New Chat
        </button>

        <div className="controls-row">
          <div className="control-group">
            <label className="mode-label" htmlFor="mode">
              Mode:
            </label>
            <select
              id="mode"
              value={currentMode}
              onChange={(e) => onModeChange(e.target.value)}
              className={`mode-select ${theme}-theme`}
            >
              <option value="regular">🤖 Regular (API)</option>
              <option value="uncensored">🔥 Uncensored (Local)</option>
              <option value="ocr">📄 OCR (Gemini)</option>
            </select>
          </div>
          <button
            className={`theme-toggle ${theme}-theme`}
            onClick={toggleTheme}
            aria-label="Toggle theme"
          >
            {theme === "dark" ? "🌙" : "☀️"}
          </button>
        </div>
      </div>

      <ul className="session-list">
        {sessions.map((s) => {
          const displayedTitle = s.title || "New chat";
          return (
            <li
              key={s.session_id}
              className={`session-item ${
                currentSession === s.session_id ? "active" : ""
              } ${theme}-theme`}
               onClick={() => onSessionSelect?.(s.session_id, s.mode)}
              title={displayedTitle}
            >
               <span className="session-icon">{/* emoji */}</span>

  {/* 👇 this wrapper applies ellipsis */}
  <div className="session-title">
    <SessionTitle
      title={displayedTitle}
      justRenamed={s.justRenamed}
      onDoubleClick={(e) => {
        e.stopPropagation();
        setMenuOpen(s.session_id);
        setEditTitle(displayedTitle);
      }}
    />
  </div>

              {/* 3-dot menu */}
              <div
                className="session-menu-trigger"
                onClick={(e) => {
                  e.stopPropagation();
                  setMenuOpen(menuOpen === s.session_id ? null : s.session_id);
                  setEditTitle(displayedTitle);
                }}
              >
                ⋯
                {menuOpen === s.session_id && (
                  <div
                    ref={menuRef}
                    className="session-menu"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") renameSession(s.session_id);
                        if (e.key === "Escape") setMenuOpen(null);
                      }}
                      autoFocus
                      className="session-edit-input"
                    />
                    <button onClick={() => renameSession(s.session_id)}>
                      Rename
                    </button>
                    <button onClick={() => deleteSession(s.session_id)}>
                      Delete
                    </button>
                  </div>
                )}
              </div>
            </li>
          );
        })}

        {sessions.length === 0 && (
          <li className={`empty-hint ${theme}-theme`}>
            <p>No chats yet</p>
            <p>Start a new conversation</p>
          </li>
        )}
      </ul>
    </aside>
  );
}

export default Sidebar;

