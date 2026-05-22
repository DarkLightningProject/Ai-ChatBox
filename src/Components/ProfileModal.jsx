import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";

const TABS = [
  { id: "username", label: "Username" },
  { id: "email",    label: "Email"    },
  { id: "password", label: "Password" },
  { id: "usage",    label: "Usage"    },
];

const _MODEL_DISPLAY = [
  ["gpt-4.1",           "GPT-4.1"],
  ["gpt-4o-mini",       "GPT-4o Mini"],
  ["gpt-4o",            "GPT-4o"],
  ["claude-opus-4-5",   "Claude Opus 4.5"],
  ["claude-sonnet-4-5", "Claude Sonnet 4.5"],
  ["claude-haiku",      "Claude Haiku"],
  ["gemini-2.5-pro",    "Gemini 2.5 Pro"],
  ["gemini-2.5-flash",  "Gemini 2.5 Flash"],
  ["gemini-flash",      "Gemini Flash"],
  ["gemini-pro",        "Gemini Pro"],
  ["dolphin",           "Dolphin (Uncensored)"],
  ["mistral",           "Mistral"],
];

function formatModelName(model) {
  const m = (model || "").toLowerCase();
  const hit = _MODEL_DISPLAY.find(([key]) => m.includes(key));
  return hit ? hit[1] : (model || "Unknown");
}

function fmtTokens(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + "M";
  if (n >= 1_000)     return (n / 1_000).toFixed(1) + "K";
  return String(n);
}

// [threshold, decimal places] — first match wins
const _COST_THRESHOLDS = [[1, 2], [0.01, 4], [0.0001, 6]];

function fmtCost(usd, sci) {
  if (usd === 0) return null;                       // caller shows "Free"
  if (sci) return "$" + usd.toExponential(3);       // e.g. $9.200e-5
  const hit = _COST_THRESHOLDS.find(([t]) => usd >= t);
  return "$" + usd.toFixed(hit ? hit[1] : 8);
}

function getStored() {
  try { return JSON.parse(localStorage.getItem("user") || "{}"); }
  catch { return {}; }
}
function patchStored(patch) {
  localStorage.setItem("user", JSON.stringify({ ...getStored(), ...patch }));
}

export default function ProfileModal({ isOpen, onClose, theme, isPremium }) {
  const navigate = useNavigate();
  const [tab, setTab] = useState("username");

  // User info (header card)
  const [userInfo, setUserInfo] = useState({ username: "", email: "" });

  // ── Username tab ──────────────────────────────
  const [newUsername, setNewUsername] = useState("");

  // ── Email tab ─────────────────────────────────
  const [newEmail,   setNewEmail]   = useState("");
  const [emailPass,  setEmailPass]  = useState("");

  // ── Password tab ──────────────────────────────
  const [oldPass,     setOldPass]     = useState("");
  const [newPass,     setNewPass]     = useState("");
  const [confirmPass, setConfirmPass] = useState("");
  const [showOld,     setShowOld]     = useState(false);
  const [showNew,     setShowNew]     = useState(false);

  // ── Usage tab ─────────────────────────────────
  const [usageData,      setUsageData]      = useState(null);
  const [usageLoading,   setUsageLoading]   = useState(false);
  const [usageError,     setUsageError]     = useState(null);
  const [usageResetting, setUsageResetting] = useState(false);
  const [sciMode,        setSciMode]        = useState(false);

  // ── Shared UI ─────────────────────────────────
  const [loading, setLoading] = useState(false);
  const [msg,     setMsg]     = useState({ type: "", text: "" });

  // Fetch usage data when usage tab is active
  useEffect(() => {
    if (!isOpen || tab !== "usage") return;
    setUsageLoading(true);
    setUsageError(null);
    api.get("/api/usage/")
      .then(r => setUsageData(r.data))
      .catch(() => setUsageError("Failed to load usage data. Please try again."))
      .finally(() => setUsageLoading(false));
  }, [isOpen, tab]);

  // Reset and load fresh data whenever the modal opens
  useEffect(() => {
    if (!isOpen) return;
    setTab("username");
    setUsageData(null);
    setUsageError(null);
    setSciMode(false);
    setMsg({ type: "", text: "" });
    setNewEmail(""); setEmailPass("");
    setOldPass(""); setNewPass(""); setConfirmPass("");
    setShowOld(false); setShowNew(false);

    const cached = getStored();
    setUserInfo({ username: cached.username || "", email: cached.email || "" });
    setNewUsername(cached.username || "");

    // Refresh from server in background
    api.get("/api/auth/me/").then(r => {
      setUserInfo({ username: r.data.username, email: r.data.email });
      setNewUsername(r.data.username);
      localStorage.setItem("user", JSON.stringify(r.data));
    }).catch(() => {});
  }, [isOpen]);

  const switchTab = useCallback((t) => {
    setTab(t);
    setMsg({ type: "", text: "" });
  }, []);

  if (!isOpen) return null;

  const avatarLetter = (userInfo.username || "?")[0].toUpperCase();
  const setErr = (text) => setMsg({ type: "error",   text });
  const setOk  = (text) => setMsg({ type: "success", text });

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleUsernameUpdate = async (e) => {
    e.preventDefault();
    const u = newUsername.trim();
    if (!u)          { setErr("Username is required"); return; }
    if (u.length < 3) { setErr("Username must be at least 3 characters"); return; }

    setLoading(true); setMsg({ type: "", text: "" });
    try {
      const r = await api.put("/api/auth/update-profile/", { username: u });
      setUserInfo(prev => ({ ...prev, username: r.data.username }));
      patchStored({ username: r.data.username });
      setOk("Username updated successfully");
    } catch (err) {
      setErr(err.response?.data?.error || "Failed to update username");
    } finally {
      setLoading(false);
    }
  };

  const handleEmailUpdate = async (e) => {
    e.preventDefault();
    if (!newEmail.trim() || !emailPass) {
      setErr("New email and password are required"); return;
    }
    setLoading(true); setMsg({ type: "", text: "" });
    try {
      const r = await api.post("/api/auth/update-email/", {
        password: emailPass,
        new_email: newEmail.trim(),
      });
      const updated = newEmail.trim().toLowerCase();
      setUserInfo(prev => ({ ...prev, email: updated }));
      patchStored({ email: updated });
      setOk(r.data.message);
      setNewEmail(""); setEmailPass("");
    } catch (err) {
      setErr(err.response?.data?.error || "Failed to update email");
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordChange = async (e) => {
    e.preventDefault();
    if (!oldPass || !newPass || !confirmPass) {
      setErr("All fields are required"); return;
    }
    if (newPass !== confirmPass) {
      setErr("New passwords do not match"); return;
    }
    setLoading(true); setMsg({ type: "", text: "" });
    try {
      await api.post("/api/auth/change-password/", {
        old_password: oldPass,
        new_password: newPass,
      });
      setOk("Password changed successfully");
      setOldPass(""); setNewPass(""); setConfirmPass("");
      setShowOld(false); setShowNew(false);
    } catch (err) {
      setErr(err.response?.data?.error || "Failed to change password");
    } finally {
      setLoading(false);
    }
  };

  const handleResetUsage = async () => {
    // eslint-disable-next-line no-restricted-globals
    if (!confirm("Reset all usage statistics? This cannot be undone.")) return;
    setUsageResetting(true);
    try {
      await api.delete("/api/usage/");
      setUsageData({ by_model: [], total_tokens: 0, total_cost_usd: 0 });
      setUsageError(null);
    } catch {
      setUsageError("Failed to reset statistics. Please try again.");
    } finally {
      setUsageResetting(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div
        className={`profile-modal ${theme}-theme`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Profile settings"
      >
        {/* Header */}
        <header className="profile-modal__header">
          <h3>Profile</h3>
          <button className="icon-btn" onClick={onClose} aria-label="Close">✕</button>
        </header>

        {/* User card */}
        <div className="profile-modal__card">
          <div className="profile-avatar">{avatarLetter}</div>
          <div className="profile-modal__info">
            <span className="profile-modal__name">{userInfo.username}</span>
            <span className="profile-modal__email">{userInfo.email}</span>
          </div>
          <span className={`profile-badge ${isPremium ? "premium" : "free"}`}>
            {isPremium ? "★ Premium" : "Free"}
          </span>
        </div>

        {/* Tabs */}
        <nav className="profile-tabs" role="tablist">
          {TABS.map(({ id, label }) => (
            <button
              key={id}
              role="tab"
              aria-selected={tab === id}
              className={`profile-tab-btn${tab === id ? " active" : ""}`}
              onClick={() => switchTab(id)}
            >
              {label}
            </button>
          ))}
        </nav>

        {/* Body */}
        <div className="profile-modal__body">
          {msg.text && (
            <div className={`profile-msg profile-msg--${msg.type}`} role="alert">
              {msg.text}
            </div>
          )}

          {/* ── Username tab ── */}
          {tab === "username" && (
            <form onSubmit={handleUsernameUpdate} className="profile-form">
              <label className="profile-label" htmlFor="pf-username">Username</label>
              <input
                id="pf-username"
                className="profile-input"
                type="text"
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
                maxLength={30}
                autoFocus
                autoComplete="username"
              />
              <p className="profile-hint">3–30 characters, must be unique</p>
              <button className="profile-save-btn" type="submit" disabled={loading}>
                {loading ? "Saving…" : "Save Username"}
              </button>
            </form>
          )}

          {/* ── Email tab ── */}
          {tab === "email" && (
            <form onSubmit={handleEmailUpdate} className="profile-form">
              <label className="profile-label">Current Email</label>
              <input
                className="profile-input"
                type="email"
                value={userInfo.email}
                readOnly
                disabled
                tabIndex={-1}
              />
              <label className="profile-label" htmlFor="pf-new-email">New Email</label>
              <input
                id="pf-new-email"
                className="profile-input"
                type="email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                placeholder="new@example.com"
                autoFocus
                autoComplete="email"
              />
              <label className="profile-label" htmlFor="pf-email-pass">
                Current Password (to verify)
              </label>
              <input
                id="pf-email-pass"
                className="profile-input"
                type="password"
                value={emailPass}
                onChange={(e) => setEmailPass(e.target.value)}
                placeholder="Your current password"
                autoComplete="current-password"
              />
              <button className="profile-save-btn" type="submit" disabled={loading}>
                {loading ? "Updating…" : "Update Email"}
              </button>
            </form>
          )}

          {/* ── Password tab ── */}
          {tab === "password" && (
            <form onSubmit={handlePasswordChange} className="profile-form">
              <label className="profile-label" htmlFor="pf-old-pass">Current Password</label>
              <div className="profile-input-wrap">
                <input
                  id="pf-old-pass"
                  className="profile-input"
                  type={showOld ? "text" : "password"}
                  value={oldPass}
                  onChange={(e) => setOldPass(e.target.value)}
                  placeholder="Enter current password"
                  autoFocus
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="profile-eye-btn"
                  onClick={() => setShowOld((v) => !v)}
                  aria-label={showOld ? "Hide password" : "Show password"}
                >
                  {showOld ? "🙈" : "👁"}
                </button>
              </div>

              <label className="profile-label" htmlFor="pf-new-pass">New Password</label>
              <div className="profile-input-wrap">
                <input
                  id="pf-new-pass"
                  className="profile-input"
                  type={showNew ? "text" : "password"}
                  value={newPass}
                  onChange={(e) => setNewPass(e.target.value)}
                  placeholder="Enter new password"
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  className="profile-eye-btn"
                  onClick={() => setShowNew((v) => !v)}
                  aria-label={showNew ? "Hide password" : "Show password"}
                >
                  {showNew ? "🙈" : "👁"}
                </button>
              </div>

              <label className="profile-label" htmlFor="pf-confirm-pass">
                Confirm New Password
              </label>
              <input
                id="pf-confirm-pass"
                className="profile-input"
                type="password"
                value={confirmPass}
                onChange={(e) => setConfirmPass(e.target.value)}
                placeholder="Confirm new password"
                autoComplete="new-password"
              />

              <button className="profile-save-btn" type="submit" disabled={loading}>
                {loading ? "Changing…" : "Change Password"}
              </button>

              <button
                type="button"
                className="profile-forgot-link"
                onClick={() => { onClose(); navigate("/forgot"); }}
              >
                Forgot your password?
              </button>
            </form>
          )}

          {/* ── Usage tab ── */}
          {tab === "usage" && (
            <div className="usage-panel">
              {usageLoading && (
                <p className="usage-empty">Loading usage data…</p>
              )}
              {!usageLoading && usageError && (
                <p className="profile-msg profile-msg--error">{usageError}</p>
              )}
              {!usageLoading && !usageError && (!usageData || usageData.by_model.length === 0) && (
                <p className="usage-empty">No usage recorded yet. Start chatting to see stats here.</p>
              )}
              {!usageLoading && usageData && usageData.by_model.length > 0 && (
                <>
                  <div className="usage-table-header">
                    <span className="usage-table-label">Per-model breakdown</span>
                    <button
                      className="usage-fmt-toggle"
                      onClick={() => setSciMode(v => !v)}
                      title={sciMode ? "Switch to decimal notation" : "Switch to scientific notation"}
                    >
                      {sciMode ? "1.2e-4 → 0.00012" : "0.00012 → 1.2e-4"}
                    </button>
                  </div>
                  <table className="usage-table">
                    <thead>
                      <tr>
                        <th className="usage-th usage-th--model">Model</th>
                        <th className="usage-th">Input</th>
                        <th className="usage-th">Output</th>
                        <th className="usage-th">Total</th>
                        <th className="usage-th usage-th--cost">Est. Cost</th>
                      </tr>
                    </thead>
                    <tbody>
                      {usageData.by_model.map((row) => (
                        <tr key={row.model} className="usage-row">
                          <td className="usage-td usage-td--model">{formatModelName(row.model)}</td>
                          <td className="usage-td usage-td--num">{fmtTokens(row.input_tokens)}</td>
                          <td className="usage-td usage-td--num">{fmtTokens(row.output_tokens)}</td>
                          <td className="usage-td usage-td--num">{fmtTokens(row.total_tokens)}</td>
                          <td className="usage-td usage-td--cost">
                            {fmtCost(row.estimated_cost_usd, sciMode)
                              ?? <span className="usage-free">Free</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr className="usage-total-row">
                        <td className="usage-td usage-td--model"><strong>Total</strong></td>
                        <td className="usage-td" colSpan={3} style={{ textAlign: "center" }}>
                          <strong>{fmtTokens(usageData.total_tokens)} tokens</strong>
                        </td>
                        <td className="usage-td usage-td--cost">
                          <strong>
                            {fmtCost(usageData.total_cost_usd, sciMode) ?? "$0.00"}
                          </strong>
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                  <div className="usage-footer">
                    <p className="usage-note">
                      * Costs are estimates based on public provider pricing. Actual charges may differ.
                    </p>
                    <button
                      className="usage-reset-btn"
                      onClick={handleResetUsage}
                      disabled={usageResetting}
                    >
                      {usageResetting ? "Resetting…" : "Reset Statistics"}
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
