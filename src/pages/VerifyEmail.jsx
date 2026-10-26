import React, { useEffect, useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { verifyEmail } from "../api/auth";
import api from "../api";
import ThemeToggle from "../Components/ThemeToggle";
import "../styles/auth.css";

export default function VerifyEmail({ theme = "light", onToggleTheme }) {
  const { uid, token } = useParams();
  const navigate = useNavigate();

  const [status, setStatus] = useState("loading"); // loading | success | error
  const [errorMsg, setErrorMsg] = useState("");
  const [countdown, setCountdown] = useState(4);
  const [resendState, setResendState] = useState("idle"); // idle | sending | sent | failed
  const [resendMsg, setResendMsg] = useState("");

  useEffect(() => {
    verifyEmail(uid, token)
      .then(() => setStatus("success"))
      .catch((err) => {
        setErrorMsg(
          err.response?.data?.error ||
          "Verification failed. The link may be expired or invalid."
        );
        setStatus("error");
      });
  }, [uid, token]);

  useEffect(() => {
    if (status !== "success") return;
    if (countdown <= 0) { navigate("/login"); return; }
    const timeout = setTimeout(() => setCountdown((current) => current - 1), 1000);
    return () => clearTimeout(timeout);
  }, [status, countdown, navigate]);

  const handleResend = async () => {
    setResendState("sending");
    setResendMsg("");
    try {
      const response = await api.post("/api/auth/resend-verification/");
      setResendState("sent");
      setResendMsg(response.data?.message || "Verification email sent! Check your inbox.");
    } catch (err) {
      setResendState("failed");
      if (err.response?.status === 401 || err.response?.status === 403) {
        setResendMsg("Please log in first, then resend from within the app.");
      } else {
        setResendMsg(
          err.response?.data?.message ||
          err.response?.data?.error ||
          "Failed to send. Please try again."
        );
      }
    }
  };

  return (
    <main className={`auth-container auth-page ${theme}-theme`}>
      <Link className="auth-home-link" to="/" aria-label="AI ChatBox home">
        <span className="auth-brand-mark" aria-hidden="true">✳</span>
        <span>AI ChatBox</span>
      </Link>
      <ThemeToggle theme={theme} onToggle={onToggleTheme} />

      <div className="auth-layout">
        <section className="auth-showcase" aria-label="AI ChatBox email verification">
          <span className="auth-showcase-eyebrow"><span /> A SPACE FOR YOUR NEXT THOUGHT</span>
          <h1>One small step<br />to a whole world<br /><span>of ideas.</span></h1>
          <p>Verify your email to activate your account and make room for good questions, fresh ideas, and conversations that go somewhere.</p>
          <div className="auth-showcase-note">
            <span className="auth-showcase-note-icon" aria-hidden="true">✦</span>
            <span><strong>Your next conversation is close.</strong><small>Verify once, then jump right in.</small></span>
          </div>
          <div className="auth-showcase-orb auth-showcase-orb-one" />
          <div className="auth-showcase-orb auth-showcase-orb-two" />
        </section>

        <section
          className="auth-card auth-success-card verify-card"
          aria-labelledby="verify-heading"
          aria-live="polite"
        >
          {status === "loading" && (
            <>
              <div className="verify-spinner" role="status" aria-label="Verifying email" />
              <span className="auth-card-kicker">JUST A MOMENT</span>
              <h2 id="verify-heading">Verifying your email…</h2>
              <p className="subtitle">We’re checking your link. This should only take a moment.</p>
            </>
          )}

          {status === "success" && (
            <>
              <div className="verify-icon verify-icon--success" aria-hidden="true">✓</div>
              <span className="auth-card-kicker">YOU’RE ALL SET</span>
              <h2 id="verify-heading">Email verified!</h2>
              <p className="subtitle">Your account is active. Welcome to AI ChatBox.</p>
              <p className="subtitle verify-countdown">
                Taking you to sign in in <strong>{countdown}s</strong>…
              </p>
              <button className="auth-btn" onClick={() => navigate("/login")}>
                <span>Go to sign in</span><span aria-hidden="true">↗</span>
              </button>
            </>
          )}

          {status === "error" && (
            <>
              <div className="verify-icon verify-icon--error" aria-hidden="true">✕</div>
              <span className="auth-card-kicker">LINK NOT WORKING</span>
              <h2 id="verify-heading">Couldn’t verify your email.</h2>
              <p className="subtitle">This verification link may have expired or already been used.</p>
              <div className="error-box" role="alert">{errorMsg}</div>

              {resendState === "sent" ? (
                <div className="success-box" role="status">{resendMsg}</div>
              ) : (
                <>
                  <button
                    className="auth-btn"
                    onClick={handleResend}
                    disabled={resendState === "sending"}
                  >
                    <span className="auth-submit-label">
                      {resendState === "sending" && <span className="ui-spinner" aria-hidden="true" />}
                      {resendState === "sending" ? "Sending…" : "Resend verification email"}
                    </span>
                    {resendState !== "sending" && <span aria-hidden="true">↗</span>}
                  </button>
                  {resendState === "failed" && (
                    <div className="error-box" role="alert">{resendMsg}</div>
                  )}
                </>
              )}

              <p className="auth-switch">
                Already verified? <Link to="/login">Sign in</Link>
              </p>
            </>
          )}

          {status !== "error" && (
            <div className="auth-card-footer"><span>✳</span> Your space to think out loud.</div>
          )}
        </section>
      </div>
    </main>
  );
}
