import { useState, useEffect, useRef, memo } from "react";
import { useNavigate } from "react-router-dom";
import { createPortal } from "react-dom";
import "../styles/layout.css";
import api from "../api";
import { logout,deleteAccount } from "../api/auth";
import ProfileModal from "./ProfileModal";
import TypingIndicator, { TYPING_INDICATOR_OPTIONS } from "./TypingIndicator";




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



const PREMIUM_MODES = new Set([]); // no mode is fully locked — only premium tier inside Multi-Debugger

function SidebarIcon({ name }) {
  const paths = {
    regular: <path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H5l1.8-3.2A7.5 7.5 0 1 1 20 11.5Z" />,
    uncensored: <path d="M12.1 22c4.2 0 7-2.8 7-6.6 0-2.6-1.4-4.5-3.7-6.6-.1 2-1.1 3.1-2.1 3.6.2-3.7-1.7-7-5.2-9.4.4 4-1 5.8-2.4 7.7C4.5 12.3 4 13.8 4 15.6 4 19.4 7.2 22 12.1 22Z" />,
    multi_debugger: (
      <>
        <path d="M8 8V6.5a2.5 2.5 0 1 0-2.5 2.5H8Zm0 0h8m0 0V7a2.5 2.5 0 1 1 2.5 2.5H16Zm0 0v8m0 0h1.5a2.5 2.5 0 1 1-2.5 2.5V16Zm0 0H8m0 0v1.5a2.5 2.5 0 1 1-2.5-2.5H8Zm0 0V8Z" />
      </>
    ),
    logout: (
      <>
        <path d="M12 3v9" />
        <path d="M7.1 5.8a8 8 0 1 0 9.8 0" />
      </>
    ),
    settings: (
      <>
        <path d="M4 7h9m4 0h3M4 17h3m4 0h9" />
        <circle cx="15" cy="7" r="2" />
        <circle cx="9" cy="17" r="2" />
      </>
    ),
  };

  return (
    <svg
      className={`sidebar-icon sidebar-icon-${name}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {paths[name]}
    </svg>
  );
}

// Returns true if bans dict indicates this mode (or full_account) is banned
function isModeInBans(bans, modeKey) {
  if (!bans) return false;
  return !!(bans["full_account"] || bans[modeKey]);
}

function Sidebar({
  sessions,
  onSessionSelect,
  pendingAction,
  currentSession,
  onModeChange,
  currentMode,
  onNewSession,
  onDeleted,
  onRenamed,
  theme,
  toggleTheme,
  typingAnimation,
  setTypingAnimation,
  isPremium = false,
  bans = {},
}) {
  const [menuOpen, setMenuOpen] = useState(null);
  const [modeMenuOpen, setModeMenuOpen] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const navigate = useNavigate();
  const menuRef = useRef();
  const modeMenuRef = useRef();
  const modeTriggerRef = useRef();

  // Close menu when clicking outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(null);
      }
      if (modeMenuRef.current && !modeMenuRef.current.contains(e.target)) {
        setModeMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await logout();
    } catch (err) {
      console.error("Logout failed:", err);
    } finally {
      localStorage.removeItem("user");
      navigate("/login");
    }
  };

  const selectMode = (val) => {
    if (pendingAction?.type === "mode") return;
    setModeMenuOpen(false);
    if (PREMIUM_MODES.has(val) && !isPremium) {
      navigate("/checkout");
      return;
    }
    if (val === "regular") {
      if (currentMode !== "regular" && currentMode !== "ocr") onModeChange("regular");
      return;
    }
    if (isModeInBans(bans, val)) return;
    onModeChange(val);
  };

  const deleteSession = async (session_id) => {
    try {
      await api.delete(`/api/sessions/${session_id}/delete/`
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
      await api.put(
  `/api/sessions/${session_id}/rename/`,
  { title: editTitle }
);
      onRenamed?.(session_id, editTitle);
      setMenuOpen(null);
    } catch (err) {
      console.error("Failed to rename session:", err);
    }
  };
const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
const [deleting, setDeleting] = useState(false);
const [logoutConfirmOpen, setLogoutConfirmOpen] = useState(false);
const [loggingOut, setLoggingOut] = useState(false);
const [settingsOpen, setSettingsOpen] = useState(false);
const [profileOpen, setProfileOpen] = useState(false);
const [modelNames, setModelNames] = useState({ mistral: "Mistral", gemini: "Gemini" });

useEffect(() => {
  api.get("/api/models/")
    .then(res => setModelNames(res.data))
    .catch(() => {}); // non-critical — fallback labels stay
}, []);




  return (
    <aside className={`sidebar ${theme}-theme`}>
      <div className="sidebar-top">
        <button
          className={`btn new-btn ${theme}-theme`}
          onClick={onNewSession}
          disabled={pendingAction?.type === "new"}
          aria-busy={pendingAction?.type === "new"}
        >
          {pendingAction?.type === "new"
            ? <span className="ui-spinner" aria-hidden="true" />
            : <span className="plus">+</span>}
          {pendingAction?.type === "new" ? "Creating…" : "New Chat"}
        </button>

        

        <div className="controls-row">
          

       <div className="control-group">
  <label className="mode-label" htmlFor="mode">
    Mode:
  </label>

  {/* A custom menu gives each mode a consistently sized vector icon. */}
  <div className={`mode-picker ${theme}-theme`} ref={modeMenuRef}>
    <button
      id="mode"
      ref={modeTriggerRef}
      type="button"
      className="mode-picker-trigger"
      aria-haspopup="menu"
      aria-expanded={modeMenuOpen}
      aria-label="Select chat mode"
      onClick={() => setModeMenuOpen((open) => !open)}
      onKeyDown={(event) => {
        if (event.key === "Escape") setModeMenuOpen(false);
      }}
    >
      <span className="mode-picker-current">
        {pendingAction?.type === "mode"
          ? <span className="ui-spinner" aria-hidden="true" />
          : <SidebarIcon name={(currentMode === "regular" || currentMode === "ocr") ? "regular" : currentMode} />}
        <span>{pendingAction?.type === "mode" ? "Switching…" : currentMode === "uncensored" ? "Uncensored" : currentMode === "multi_debugger" ? "Multi-Debugger" : "Regular"}</span>
      </span>
      <svg className="mode-picker-chevron" viewBox="0 0 16 16" aria-hidden="true">
        <path d="m4 6 4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
    {modeMenuOpen && (
      <div
        className="mode-picker-menu"
        role="menu"
        aria-labelledby="mode"
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            setModeMenuOpen(false);
            modeTriggerRef.current?.focus();
          }
        }}
      >
        {[
          { value: "regular", label: "Regular", disabled: isModeInBans(bans, "regular") && isModeInBans(bans, "ocr") },
          { value: "uncensored", label: "Uncensored", disabled: isModeInBans(bans, "uncensored") },
          { value: "multi_debugger", label: "Multi-Debugger", disabled: isModeInBans(bans, "multi_debugger") },
        ].map((option) => {
          const selected = option.value === "regular"
            ? currentMode === "regular" || currentMode === "ocr"
            : currentMode === option.value;
          return (
            <button
              key={option.value}
              type="button"
              role="menuitemradio"
              aria-checked={selected}
              disabled={option.disabled || pendingAction?.type === "mode"}
              className={`mode-picker-option ${selected ? "selected" : ""}`}
              onClick={() => selectMode(option.value)}
            >
              {option.disabled ? <span className="mode-picker-blocked" aria-hidden="true">⛔</span> : <SidebarIcon name={option.value} />}
              <span>{option.label}</span>
              {selected && <span className="mode-picker-check" aria-hidden="true">✓</span>}
            </button>
          );
        })}
      </div>
    )}
  </div>

  {/* Model sub-picker — only visible inside the Regular category */}
  {(currentMode === "regular" || currentMode === "ocr") && (
    <select
      id="model"
      value={currentMode}
      onChange={(e) => {
        const val = e.target.value;
        if (isModeInBans(bans, val)) return;
        onModeChange(val);
      }}
      disabled={pendingAction?.type === "mode"}
      className={`model-select ${theme}-theme`}
      aria-label="Model"
    >
      <option value="regular" disabled={isModeInBans(bans, "regular")}>
        {isModeInBans(bans, "regular") ? "⛔" : "⚡"} {modelNames.mistral}
      </option>
      <option value="ocr" disabled={isModeInBans(bans, "ocr")}>
        {isModeInBans(bans, "ocr") ? "⛔" : "✨"} {modelNames.gemini} (OCR)
      </option>
    </select>
  )}

  {/* ACTION BUTTONS ROW */}
  <div className="icon-row">
    <button
      className={`icon-btn logout-icon ${theme}-theme`}
      onClick={() => setLogoutConfirmOpen(true)}
      title="Logout"
      aria-label="Logout"
    >
      <SidebarIcon name="logout" />
    </button>

    <button
      className={`icon-btn ${theme}-theme`}
      onClick={() => setSettingsOpen(true)}
      title="Settings"
      aria-label="Settings"
    >
      <SidebarIcon name="settings" />
    </button>
  </div>
</div>

 
  
</div>

          </div>
          
          <button
            className={`theme-toggle ${theme}-theme`}
            onClick={toggleTheme}
            aria-label="Toggle theme"
          >
            {theme === "dark" ? "🌙" : "☀️"}
          </button>
          
          
        <div>
      </div>

      <ul className="session-list">
        {sessions.map((s) => {
          const displayedTitle = s.title || "New chat";
          return (
            <li
              key={s.session_id}
              className={`session-item ${
                currentSession === s.session_id ? "active" : ""
              } ${theme}-theme ${pendingAction?.sessionId === s.session_id ? "is-loading" : ""}`}
              aria-busy={pendingAction?.sessionId === s.session_id}
               onClick={() => onSessionSelect?.(s.session_id, s.mode)}
              title={displayedTitle}
            >
               {pendingAction?.sessionId === s.session_id
                 ? <span className="ui-spinner session-loading-spinner" aria-label="Opening chat" />
                 : <span className="session-icon">{/* emoji */}</span>}

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
      {settingsOpen && createPortal(
  <div className={`settings-overlay ${theme}-theme`} onClick={() => setSettingsOpen(false)}>
    <div
      className={`settings-panel ${theme}-theme`}
      onClick={(e) => e.stopPropagation()}
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-title"
    >
      <header className="settings-header">
        <h3 id="settings-title">Settings</h3>
        <button
          className="icon-btn"
          onClick={() => setSettingsOpen(false)}
          aria-label="Close"
        >
          ✕
        </button>
      </header>

      <section className="settings-section typing-settings">
        <h4>Response animation</h4>
        <div className="typing-style-options" role="radiogroup" aria-label="Response animation">
          {TYPING_INDICATOR_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={typingAnimation === option.value}
              className={`typing-style-option${typingAnimation === option.value ? " is-selected" : ""}`}
              onClick={() => setTypingAnimation(option.value)}
            >
              <TypingIndicator variant={option.value} />
              <span>{option.label}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="settings-section">
        <h4>Explore</h4>
        <button
          className="settings-item"
          onClick={() => { setSettingsOpen(false); navigate("/about"); }}
        >
          ✦ About AI ChatBox
        </button>
      </section>

      <section className="settings-section">
        <h4>Account</h4>
        <button
          className="settings-item"
          onClick={() => { setSettingsOpen(false); setProfileOpen(true); }}
        >
          👤 Profile &amp; Security
        </button>
        <button
          className="settings-item"
          onClick={() => { setSettingsOpen(false); navigate("/billing"); }}
        >
          {isPremium ? "⭐ Billing — Premium" : "💳 Billing & Upgrade"}
        </button>
      </section>

      <section className="settings-section danger">
        <h4>Danger zone</h4>
        <button
          className="settings-item danger"
          onClick={() => {
    setSettingsOpen(false);
    setConfirmDeleteOpen(true);
  }}
          
          
        >
          🗑️ Delete account
        </button>
      </section>
    </div>
  </div>,
  document.body
)}
{confirmDeleteOpen && (
  <div
    className="confirm-overlay"
    onClick={() => !deleting && setConfirmDeleteOpen(false)}
  >
    <div
      className="confirm-modal"
      onClick={(e) => e.stopPropagation()}
    >
      <h3>Delete account?</h3>

      <p>
        This will permanently delete your account and all associated data.
        <br />
        <strong>This action cannot be undone.</strong>
      </p>

      <div className="confirm-actions">
        <button
          className="btn"
          type="button"
          disabled={deleting}
          onClick={() => setConfirmDeleteOpen(false)}
        >
          Cancel
        </button>

        <button
          className="btn danger"
          type="button"
          disabled={deleting}
          onClick={async () => {
            setDeleting(true);
            try {
              await deleteAccount();
              localStorage.removeItem("user");
              navigate("/login");
            } catch (err) {
              console.error(err);
              alert("Failed to delete account");
              setDeleting(false);
            }
          }}
        >
          {deleting ? "Deleting…" : "Delete"}
        </button>
      </div>
    </div>
  </div>
)}

{logoutConfirmOpen && createPortal(
  <div
    className={`confirm-overlay ${theme}-theme`}
    onClick={() => !loggingOut && setLogoutConfirmOpen(false)}
  >
    <div
      className={`confirm-modal ${theme}-theme`}
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="logout-confirm-title"
      aria-describedby="logout-confirm-description"
      onClick={(e) => e.stopPropagation()}
    >
      <h3 id="logout-confirm-title">Log out?</h3>
      <p id="logout-confirm-description">Are you sure you want to log out of your account?</p>
      <div className="confirm-actions">
        <button
          className="btn"
          type="button"
          disabled={loggingOut}
          onClick={() => setLogoutConfirmOpen(false)}
        >
          Cancel
        </button>
        <button
          className="btn danger"
          type="button"
          disabled={loggingOut}
          onClick={handleLogout}
        >
          {loggingOut ? "Logging out…" : "Log out"}
        </button>
      </div>
    </div>
  </div>,
  document.body
)}

<ProfileModal
  isOpen={profileOpen}
  onClose={() => setProfileOpen(false)}
  theme={theme}
  isPremium={isPremium}
/>

    </aside>
  );
}

export default Sidebar;
