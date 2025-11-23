// src/App.js
import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import ChatApp from "./Components/ChatApp";
import Sidebar from "./Components/Sidebar";
import "./styles/variables.css";
import "./styles/layout.css";
import { Routes, Route, useParams, useNavigate } from "react-router-dom";

console.log("API_BASE =", process.env.REACT_APP_API_BASE);

function upsertSessions(list, item) {
  const i = list.findIndex(s => s.session_id === item.session_id);
  if (i === -1) return [item, ...list];
  const next = [...list];
  next[i] = { ...next[i], ...item };
  return next;
}
const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";
const clamp = (s, n = 60) => (s.length > n ? s.slice(0, n - 1) + "…" : s);
/* -------------------------------
   ChatWrapper
   - Manages sidebar, sessions, and chat
-------------------------------- */
function ChatWrapper({ mode, setMode, theme, setTheme }) {
  const { sessionId } = useParams(); // always from URL
  const navigate = useNavigate();
  const clearTimersRef = React.useRef({});

  // Responsive
  const initialIsMobile =
    typeof window !== "undefined" ? window.innerWidth <= 768 : false;
  const [isMobile, setIsMobile] = useState(initialIsMobile);
  const [sidebarOpen, setSidebarOpen] = useState(
    typeof window !== "undefined" ? window.innerWidth > 768 : true
  );
  const [creating, setCreating] = useState(false);

  // sessions state
  const [sessions, setSessions] = useState([]);

  /* ---------- Handlers ---------- */
const lastCreatedRef = React.useRef(null);  
const handleSessionCreated = (id, title, createdMode = mode) => {
  if (lastCreatedRef.current === id) return; // guard same tick
  lastCreatedRef.current = id;
  setTimeout(() => { lastCreatedRef.current = null; }, 0); // release guard next tick

  setSessions(prev =>
    upsertSessions(prev, {
      session_id: id,
      title: title || "New chat",
      mode: createdMode
    })
  );

  navigate(`/chat/${id}`);
};
const openSession = (id, sessionMode) => {
  // set the mode silently for this session (no extra navigation)
  if (sessionMode && sessionMode !== mode) setMode(sessionMode);
  navigate(`/chat/${id}`);
  if (isMobile) setSidebarOpen(false);
};

const handleModeChange = async (newMode) => {
  setMode(newMode);

  // We already filter the sidebar list by mode via fetchSessions(params: { mode })
  // Wait a tick so sessions state updates after fetch
  setTimeout(() => {
    setSessions((prev) => {
      // prev already contains sessions of *current* mode if fetchSessions ran,
      // but to be safe, filter by target mode here:
      const list = prev.filter((s) => s.mode === newMode);
      if (list.length > 0) {
        // open the most recently updated one (your fetch already sorts)
        navigate(`/chat/${list[0].session_id}`);
      } else {
        // no session in this mode yet → show blank; first send or +New Chat will create
        navigate(`/`);
      }
      return prev;
    });
  }, 0);
};

const handleSessionTitled = React.useCallback((id, newTitleRaw) => {
  const title = clamp(newTitleRaw || "New chat");

  // 1) Only set justRenamed when the title actually changes
  let didChange = false;
  setSessions(prev => {
    const next = prev.map(s => {
      if (s.session_id !== id) return s;
      if (s.title === title) return s;        // ⬅️ no-op if unchanged
      didChange = true;
      return { ...s, title, justRenamed: true };
    });
    return didChange ? next : prev;           // ⬅️ avoid re-render if nothing changed
  });

  if (!didChange) return;

  // 2) Clear the flag once; cancel any previous timer for this id
  if (clearTimersRef.current[id]) clearTimeout(clearTimersRef.current[id]);
  clearTimersRef.current[id] = setTimeout(() => {
    setSessions(prev => {
      let touched = false;
      const next = prev.map(s => {
        if (s.session_id !== id || !s.justRenamed) return s;
        touched = true;
        return { ...s, justRenamed: false };
      });
      return touched ? next : prev;
    });
  }, 900);
}, [setSessions]);



  const handleDeleted = (deletedId) => {
    setSessions((prev) => prev.filter((s) => s.session_id !== deletedId));
    if (deletedId === sessionId) {
      navigate("/"); // go home if current session deleted
    }
  };

  const handleRenamed = (id, newTitle) => {
    setSessions((prev) =>
      prev.map((s) =>
        s.session_id === id
          ? { ...s, title: newTitle, justRenamed: true }
          : s
      )
    );
    setTimeout(() => {
      setSessions((prev) =>
        prev.map((s) =>
          s.session_id === id ? { ...s, justRenamed: false } : s
        )
      );
    }, 2000);
  };



const handleNewSession = async () => {
  if (creating) return;
  try {
    setCreating(true);
    const r = await axios.post(`${API_BASE}/api/sessions/new/`, { mode });
    setSessions(prev =>
      upsertSessions(prev, { session_id: r.data.session_id, title: "New chat", mode })
    );
    navigate(`/chat/${r.data.session_id}`);
  } catch (e) {
    console.error(e);
  } finally {
    setCreating(false);
  }
};
  /* ---------- Effects ---------- */
  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth <= 768);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => setSidebarOpen(!isMobile), [isMobile]);

  useEffect(() => {
    document.body.classList.remove("dark-theme", "light-theme");
    document.body.classList.add(`${theme}-theme`);
  }, [theme]);

  // persist last session + mode
  useEffect(() => {
    if (sessionId) localStorage.setItem("sessionId", sessionId);
  }, [sessionId]);
  useEffect(() => {
    if (mode) localStorage.setItem("mode", mode);
  }, [mode]);

  // fetch sessions
  const fetchSessions = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/sessions/`, {
        params: { mode },
      });
      setSessions(res.data);
    } catch (err) {
      console.error("Failed to fetch sessions:", err);
    }
  }, [mode]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  /* ---------- Render ---------- */
  return (
    <div className={`app-shell ${theme}-theme`}>
      {sidebarOpen && (
        <Sidebar
          sessions={sessions}
          onSessionSelect={(id, m) => openSession(id, m)} 
          currentSession={sessionId}
          onModeChange={handleModeChange}
          currentMode={mode}
          onNewSession={handleNewSession}
          onDeleted={handleDeleted}
          onRenamed={handleRenamed}
          theme={theme}
          toggleTheme={() => {
            const next = theme === "light" ? "dark" : "light";
            setTheme(next);
            localStorage.setItem("theme", next);
          }}
        />
      )}

      <main className={`chat-pane ${theme}-theme`}>
        <button
          className="mobile-menu-btn"
          onClick={() => setSidebarOpen((o) => !o)}
        >
          ☰ Menu
        </button>

        <ChatApp
        key={`${sessionId || 'blank'}:${mode}`}
          sessionId={sessionId}
          mode={mode}
          theme={theme}
          setSessionId={(id) => navigate(`/chat/${id}`)}
          onSessionTitled={handleSessionTitled}
          onSessionCreated={handleSessionCreated}
        />
      </main>
    </div>
  );
}

/* -------------------------------
   App
-------------------------------- */
export default function App() {
  const [mode, setMode] = useState(localStorage.getItem("mode") || "regular");
  const [theme, setTheme] = useState(localStorage.getItem("theme") || "light");

  return (
    <Routes>
      <Route
        path="/"
        element={
          <ChatWrapper
            mode={mode}
            setMode={setMode}
            theme={theme}
            setTheme={setTheme}
          />
        }
      />
      <Route
        path="/chat/:sessionId"
        element={
          <ChatWrapper
            mode={mode}
            setMode={setMode}
            theme={theme}
            setTheme={setTheme}
          />
        }
      />
    </Routes>
  );
}
