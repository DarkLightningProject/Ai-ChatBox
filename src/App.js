// src/App.js
import React, { useEffect, useState, useCallback } from "react";
// import axios from "axios";
import ChatApp from "./Components/ChatApp";
import Sidebar from "./Components/Sidebar";
import "./styles/variables.css";
import "./styles/layout.css";
import { Routes, Route, Outlet, useParams, useNavigate, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import ResetPassword from "./pages/ResetPassword";
import ForgotPassword from "./pages/ForgotPassword";
import Checkout from "./pages/Checkout";
import PaymentSuccess from "./pages/PaymentSuccess";
import Billing from "./pages/Billing";
import VerifyEmail from "./pages/VerifyEmail";
import api from "./api";

// import ChatWrapper from "./ChatWrapper";


function upsertSessions(list, item) {
  const i = list.findIndex(s => s.session_id === item.session_id);
  if (i === -1) return [item, ...list];
  const next = [...list];
  next[i] = { ...next[i], ...item };
  return next;
}
const clamp = (s, n = 60) => (s.length > n ? s.slice(0, n - 1) + "…" : s);
/* -------------------------------
   ChatWrapper
   - Manages sidebar, sessions, and chat
-------------------------------- */
function ChatWrapper({ mode, setMode, theme, setTheme, initialData }) {
  const { isPremium, bans: serverBans, emailVerified } = useUserStatus(initialData);
  // localBans merges in any 403-banned responses received mid-session
  const [localBans, setLocalBans] = useState({});
  const bans = { ...serverBans, ...localBans };
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

  // sessions state
  const [sessions, setSessions] = useState([]);

  /* ---------- Handlers ---------- */
const lastCreatedRef = React.useRef(null);
const skipFetchRef = React.useRef(false);
const creatingRef = React.useRef(false);
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
  skipFetchRef.current = true; // suppress the useEffect fetch triggered by mode change
  try {
    const res = await api.get("/api/sessions/", { params: { mode: newMode } });
    const list = res.data || [];
    setSessions(list);
    if (list.length > 0) {
      navigate(`/chat/${list[0].session_id}`);
    } else {
      navigate("/");
    }
  } catch (err) {
    skipFetchRef.current = false;
    console.error("Failed to fetch sessions on mode change:", err);
    navigate("/");
  }
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
  if (creatingRef.current) return;
  creatingRef.current = true;

  try {
    const r = await api.post("/api/sessions/new/", {
      mode,
    });

    setSessions((prev) =>
      upsertSessions(prev, {
        session_id: r.data.session_id,
        title: "New chat",
        mode,
      })
    );

    navigate(`/chat/${r.data.session_id}`);
  } catch (e) {
    console.error("Failed to create new session:", e);
  } finally {
    creatingRef.current = false;
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
  if (skipFetchRef.current) {
    skipFetchRef.current = false;
    return;
  }
  try {
    const res = await api.get("/api/sessions/", {
      params: { mode },
    });
    const serverList = res.data || [];
    setSessions(prev => {
      // Merge instead of replace: if a session was created mid-flight
      // (onSessionCreated fired before this response arrived), a plain
      // setSessions(serverList) would wipe it out and flash "No chats yet".
      // Keep any local-only entries that the stale server snapshot missed.
      const serverIds = new Set(serverList.map(s => s.session_id));
      const localOnly = prev.filter(s => !serverIds.has(s.session_id));
      return [...localOnly, ...serverList];
    });
  } catch (err) {
    console.error("Failed to fetch sessions:", err);
  }
}, [mode]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  // When the user is on "/" with no active session but existing sessions exist,
  // silently redirect to the most recent one. This prevents every send from "/"
  // creating a brand-new session and duplicating the sidebar.
  useEffect(() => {
    if (!sessionId && sessions.length > 0) {
      navigate(`/chat/${sessions[0].session_id}`, { replace: true });
    }
  }, [sessions, sessionId, navigate]);

  /* ---------- Render ---------- */
  return (
    <>
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
            isPremium={isPremium}
            bans={bans}
            toggleTheme={() => {
              const next = theme === "light" ? "dark" : "light";
              setTheme(next);
              localStorage.setItem("theme", next);
            }}
          />
        )}

        <main className={`chat-pane ${theme}-theme`}>
          <ChatApp
            key={mode}
            sessionId={sessionId}
            fallbackSessionId={!sessionId && sessions.length > 0 ? sessions[0].session_id : undefined}
            mode={mode}
            theme={theme}
            isPremium={isPremium}
            bans={bans}
            onBanDetected={(banInfo) => setLocalBans(prev => ({
              ...prev,
              [banInfo.feature]: { expires_at: banInfo.ban_expires_at, reason: banInfo.ban_reason }
            }))}
            setSessionId={(id) => navigate(`/chat/${id}`)}
            onSessionTitled={handleSessionTitled}
            onSessionCreated={handleSessionCreated}
            toggleSidebar={() => setSidebarOpen((o) => !o)}
            emailVerified={emailVerified}
          />
        </main>
      </div>
      <Outlet />
    </>
  );
}

/* -------------------------------
   App
-------------------------------- */
/* ---------- Auth Guard ---------- */
// Calls /api/auth/me/ ONCE, stores the result, and passes it to children via
// a render-prop so child components never need to fetch it again.
const RequireAuth = ({ children }) => {
  const [state, setState] = useState("loading"); // "loading" | "ok" | "fail"
  const [userData, setUserData] = useState(null);

  useEffect(() => {
    api.get("/api/auth/me/")
      .then(res => {
        localStorage.setItem("user", JSON.stringify(res.data));
        setUserData(res.data);
        setState("ok");
      })
      .catch(() => {
        localStorage.removeItem("user");
        setState("fail");
      });
  }, []);

  if (state === "loading") return null;
  if (state === "fail") return <Navigate to="/login" replace />;
  // Pass userData to children if children is a function (render prop),
  // otherwise render as-is (e.g. Checkout, Billing don't need user data).
  return typeof children === "function" ? children(userData) : children;
};

function useUserStatus(initialData) {
  // Seed state from the data already fetched by RequireAuth — no extra request.
  const [isPremium, setIsPremium] = useState(initialData?.is_premium === true);
  const [bans, setBans] = useState(initialData?.bans || {});
  const [emailVerified, setEmailVerified] = useState(initialData?.email_verified === true);

  // Keep in sync if the user upgrades/gets banned/verified mid-session (periodic refresh).
  useEffect(() => {
    const refresh = () => {
      api.get("/api/auth/me/").then(res => {
        localStorage.setItem("user", JSON.stringify(res.data));
        setIsPremium(res.data.is_premium === true);
        setBans(res.data.bans || {});
        setEmailVerified(res.data.email_verified === true);
      }).catch(() => {});
    };
    // Re-fetch every 5 minutes in the background to pick up admin changes.
    const id = setInterval(refresh, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  return { isPremium, bans, emailVerified };
}

export default function App() {
  const [mode, setMode] = useState(localStorage.getItem("mode") || "regular");
  const [theme, setTheme] = useState(localStorage.getItem("theme") || "light");

  return (
    <Routes>
      {/* ---------- Auth Routes ---------- */}
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/forgot" element={<ForgotPassword />} />
      <Route path="/reset-password/:uid/:token" element={<ResetPassword />} />
      <Route path="/verify-email/:uid/:token" element={<VerifyEmail />} />

      {/* ---------- Payment Routes (protected) ---------- */}
      <Route
        path="/checkout"
        element={
          <RequireAuth>
            <Checkout />
          </RequireAuth>
        }
      />
      <Route
        path="/payment-success"
        element={
          <RequireAuth>
            <PaymentSuccess />
          </RequireAuth>
        }
      />
      <Route
        path="/billing"
        element={
          <RequireAuth>
            <Billing />
          </RequireAuth>
        }
      />


      {/* ---------- Protected Chat Routes ---------- */}
      {/* Single layout route keeps ChatWrapper mounted across "/" and "/chat/:sessionId"
          so sessions state survives navigation and never causes duplicate sessions. */}
      <Route
        element={
          <RequireAuth>
            {(userData) => (
              <ChatWrapper
                mode={mode}
                setMode={setMode}
                theme={theme}
                setTheme={setTheme}
                initialData={userData}
              />
            )}
          </RequireAuth>
        }
      >
        <Route index />
        <Route path="/chat/:sessionId" />
      </Route>
    </Routes>
  );
}