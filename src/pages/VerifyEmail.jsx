import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { verifyEmail } from "../api/auth";
import api from "../api";
import "../styles/auth.css";

export default function VerifyEmail() {
  const { uid, token } = useParams();
  const navigate = useNavigate();

  const [status, setStatus] = useState("loading"); // loading | success | error
  const [errorMsg, setErrorMsg] = useState("");
  const [countdown, setCountdown] = useState(4);
  const [resendState, setResendState] = useState("idle"); // idle | sending | sent | failed
  const [resendMsg, setResendMsg] = useState("");

  // Auto-verify on mount
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

  // Countdown redirect after success
  useEffect(() => {
    if (status !== "success") return;
    if (countdown <= 0) { navigate("/login"); return; }
    const t = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [status, countdown, navigate]);

  const handleResend = async () => {
    setResendState("sending");
    setResendMsg("");
    try {
      const res = await api.post("/api/auth/resend-verification/");
      setResendState("sent");
      setResendMsg(res.data?.message || "Verification email sent! Check your inbox.");
    } catch (err) {
      setResendState("failed");
      if (err.response?.status === 401 || err.response?.status === 403) {
        setResendMsg("Please log in first, then resend from within the app.");
      } else {
        setResendMsg(err.response?.data?.message || err.response?.data?.error || "Failed to send. Please try again.");
      }
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card" style={{ textAlign: "center" }}>

        {status === "loading" && (
          <>
            <div className="verify-spinner" />
            <h2>Verifying your email…</h2>
            <p className="subtitle">Please wait a moment.</p>
          </>
        )}

        {status === "success" && (
          <>
            <div className="verify-icon verify-icon--success">✓</div>
            <h2>Email Verified!</h2>
            <p className="subtitle">Your account is now active.</p>
            <p className="subtitle" style={{ marginTop: "0.5rem" }}>
              Redirecting to login in <strong>{countdown}s</strong>…
            </p>
            <button
              className="auth-btn"
              style={{ marginTop: "1rem" }}
              onClick={() => navigate("/login")}
            >
              Go to Login now
            </button>
          </>
        )}

        {status === "error" && (
          <>
            <div className="verify-icon verify-icon--error">✕</div>
            <h2>Verification Failed</h2>
            <div className="error-box">{errorMsg}</div>

            {resendState === "sent" ? (
              <div className="success-box">{resendMsg}</div>
            ) : (
              <>
                <button
                  className="auth-btn"
                  onClick={handleResend}
                  disabled={resendState === "sending"}
                  style={{ marginBottom: "0.5rem" }}
                >
                  {resendState === "sending" ? "Sending…" : "Resend Verification Email"}
                </button>
                {resendState === "failed" && (
                  <div className="error-box" style={{ marginTop: "0.25rem", marginBottom: "0.5rem" }}>
                    {resendMsg}
                  </div>
                )}
              </>
            )}

            <button
              className="auth-btn auth-btn--outline"
              style={{ marginTop: "0.5rem" }}
              onClick={() => navigate("/login")}
            >
              Go to Login
            </button>
          </>
        )}

      </div>
    </div>
  );
}
