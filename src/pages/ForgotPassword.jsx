import React, { useState } from "react";
import { Link } from "react-router-dom";
import { forgotPassword } from "../api/auth";
import ThemeToggle from "../Components/ThemeToggle";
import "../styles/auth.css";

export default function ForgotPassword({ theme = "light", onToggleTheme }) {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (isSubmitting) return;
    setError("");
    setIsSubmitting(true);

    try {
      await forgotPassword({ email });
      setSent(true);
    } catch {
      setError("Email not found.");
      setIsSubmitting(false);
    }
  };

  return (
    <main className={`auth-container auth-page ${theme}-theme`}>
      <Link className="auth-home-link" to="/" aria-label="conversa Ai home">
        <span className="auth-brand-mark" aria-hidden="true">✳</span>
        <span>conversa Ai</span>
      </Link>
      <ThemeToggle theme={theme} onToggle={onToggleTheme} />

      <div className="auth-layout">
        <section className="auth-showcase" aria-label="conversa Ai account recovery">
          <span className="auth-showcase-eyebrow"><span /> A SPACE FOR YOUR NEXT THOUGHT</span>
          <h1>A fresh start<br />is just around<br /><span>the corner.</span></h1>
          <p>We’ll help you get back to your conversations. Enter your account email and we’ll send you a secure reset link.</p>
          <div className="auth-showcase-note">
            <span className="auth-showcase-note-icon" aria-hidden="true">✦</span>
            <span><strong>Your conversations are waiting.</strong><small>Pick up right where you left off.</small></span>
          </div>
          <div className="auth-showcase-orb auth-showcase-orb-one" />
          <div className="auth-showcase-orb auth-showcase-orb-two" />
        </section>

        <section className={`auth-card${sent ? " auth-success-card" : ""}`} aria-labelledby="forgot-heading">
          {sent ? (
            <>
              <div className="verify-icon verify-icon--success" aria-hidden="true">✓</div>
              <span className="auth-card-kicker">CHECK YOUR INBOX</span>
              <h2 id="forgot-heading">Reset link sent.</h2>
              <p className="subtitle">
                If an account exists for <strong>{email}</strong>, you’ll receive a password reset link shortly.
              </p>
              <Link className="auth-btn auth-button-link" to="/login">
                <span>Back to sign in</span><span aria-hidden="true">↗</span>
              </Link>
            </>
          ) : (
            <>
              <div className="auth-card-heading">
                <span className="auth-card-kicker">ACCOUNT RECOVERY</span>
                <h2 id="forgot-heading">Forgot your password?</h2>
                <p className="subtitle">Enter your account email and we’ll send a reset link.</p>
              </div>

              {error && <div className="error-box" role="alert">{error}</div>}

              <form className="auth-form" onSubmit={submit}>
                <div className="input-group">
                  <label htmlFor="forgot-email">Email address</label>
                  <input
                    id="forgot-email"
                    type="email"
                    autoComplete="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>

                <button type="submit" className="auth-btn" disabled={isSubmitting}>
                  <span className="auth-submit-label">
                    {isSubmitting && <span className="ui-spinner" aria-hidden="true" />}
                    {isSubmitting ? "Sending link…" : "Send reset link"}
                  </span>
                  {!isSubmitting && <span aria-hidden="true">↗</span>}
                </button>
              </form>

              <p className="auth-switch">
                Remember your password? <Link to="/login">Sign in</Link>
              </p>
              <div className="auth-card-footer"><span>✳</span> Your space to think out loud.</div>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
