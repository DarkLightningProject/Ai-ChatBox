import React, { useState } from "react";
import { signup } from "../api/auth";
import { Link, useNavigate } from "react-router-dom";
import ThemeToggle from "../Components/ThemeToggle";
import PasswordVisibilityButton from "../Components/PasswordVisibilityButton";
import "../styles/auth.css";

export default function Signup({ theme = "light", onToggleTheme }) {
  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
  });

  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [success, setSuccess] = useState(false);
  const [verificationEmailSent, setVerificationEmailSent] = useState(true);
  const [showEmailWarning, setShowEmailWarning] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();

  /* ---------- Password rules ---------- */
  const passwordRules = [
    { test: /.{8,}/, label: "At least 8 characters" },
    { test: /[A-Z]/, label: "One uppercase letter" },
    { test: /[a-z]/, label: "One lowercase letter" },
    { test: /[0-9]/, label: "One number" },
    { test: /[!@#$%^&*(),.?":{}|<>]/, label: "One special character" },
  ];

  const isStrongPassword = passwordRules.every((r) =>
    r.test.test(form.password)
  );

  /* ---------- Submit ---------- */
  const submit = async (e) => {
    e.preventDefault();
    if (isSubmitting) return;
    setError("");

    if (!isStrongPassword) {
      setError("Password does not meet security requirements.");
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await signup(form);
      const emailSent = response.data?.verification_email_sent !== false;
      setVerificationEmailSent(emailSent);
      if (!emailSent) {
        setShowEmailWarning(true);
      }
      setSuccess(true);
    } catch (err) {
      setError(err.response?.data?.error || "Signup failed");
      setIsSubmitting(false);
    }
  };

  if (success) {
    return (
      <main className={`auth-container auth-page ${theme}-theme`}>
        <Link className="auth-home-link" to="/" aria-label="conversa Ai home">
          <span className="auth-brand-mark" aria-hidden="true">✳</span>
          <span>conversa Ai</span>
        </Link>
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        <div className="auth-layout">
          <section className="auth-showcase" aria-label="Welcome to conversa Ai">
            <span className="auth-showcase-eyebrow"><span /> A SPACE FOR YOUR NEXT THOUGHT</span>
            <h1>Your next<br />chapter starts<br /><span>with a hello.</span></h1>
            <p>Make room for good questions, fresh ideas, and the occasional “wait, that actually worked.”</p>
            <div className="auth-showcase-note">
              <span className="auth-showcase-note-icon" aria-hidden="true">✦</span>
              <span><strong>One account. Lots of possibilities.</strong><small>Chat, create, explore, repeat.</small></span>
            </div>
            <div className="auth-showcase-orb auth-showcase-orb-one" />
            <div className="auth-showcase-orb auth-showcase-orb-two" />
          </section>
          <section className="auth-card auth-success-card" aria-labelledby="signup-success-heading">
            <div className="verify-icon verify-icon--success">✓</div>
            <span className="auth-card-kicker">YOU’RE ALMOST THERE</span>
            <h2 id="signup-success-heading">Account created!</h2>
            <p className="subtitle">
              {verificationEmailSent ? (
                <>
                  We sent a verification link to <strong>{form.email}</strong>.
                  Open it to activate your account and get started.
                </>
              ) : (
                <>
                  Your account was created, but we couldn’t send a verification link to <strong>{form.email}</strong>.
                  Sign in to request a resend.
                </>
              )}
            </p>
            <button className="auth-btn" onClick={() => navigate("/login")}>
              <span>Go to sign in</span><span aria-hidden="true">↗</span>
            </button>
            {showEmailWarning && (
              <div className="signup-email-warning-backdrop">
                <section
                  className="signup-email-warning"
                  role="alertdialog"
                  aria-modal="true"
                  aria-labelledby="signup-email-warning-title"
                  aria-describedby="signup-email-warning-description"
                >
                  <div className="signup-email-warning-icon" aria-hidden="true">!</div>
                  <span className="auth-card-kicker">PROTOTYPE NOTICE</span>
                  <h3 id="signup-email-warning-title">Verification email not sent</h3>
                  <p id="signup-email-warning-description">
                    This prototype’s email service may be unavailable. Please try again later.
                    {" "}Use dummy details only; never enter real or sensitive information.
                  </p>
                  <button
                    type="button"
                    className="auth-btn"
                    onClick={() => setShowEmailWarning(false)}
                  >
                    Got it
                  </button>
                </section>
              </div>
            )}
          </section>
        </div>
      </main>
    );
  }

  return (
    <main className={`auth-container auth-page ${theme}-theme`}>
      <Link className="auth-home-link" to="/" aria-label="conversa Ai home">
        <span className="auth-brand-mark" aria-hidden="true">✳</span>
        <span>conversa Ai</span>
      </Link>
      <ThemeToggle theme={theme} onToggle={onToggleTheme} />
      <div className="auth-layout">
        <section className="auth-showcase" aria-label="Welcome to conversa Ai">
          <span className="auth-showcase-eyebrow"><span /> A SPACE FOR YOUR NEXT THOUGHT</span>
          <h1>Your next<br />chapter starts<br /><span>with a hello.</span></h1>
          <p>Make room for good questions, fresh ideas, and the occasional “wait, that actually worked.”</p>
          <div className="auth-showcase-note">
            <span className="auth-showcase-note-icon" aria-hidden="true">✦</span>
            <span><strong>One account. Lots of possibilities.</strong><small>Chat, create, explore, repeat.</small></span>
          </div>
          <div className="auth-showcase-orb auth-showcase-orb-one" />
          <div className="auth-showcase-orb auth-showcase-orb-two" />
        </section>

        <section className="auth-card" aria-labelledby="signup-heading">
          <div className="auth-card-heading">
            <span className="auth-card-kicker">COME ON IN</span>
            <h2 id="signup-heading">Create your account.</h2>
            <p className="subtitle">A little curiosity goes a long way.</p>
          </div>

          {error && <div className="error-box" role="alert">{error}</div>}

          <form className="auth-form" onSubmit={submit}>
            <div className="input-group">
              <label htmlFor="signup-username">Username</label>
              <input
                id="signup-username"
                type="text"
                autoComplete="username"
                placeholder="What should we call you?"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                required
              />
            </div>

            <div className="input-group">
              <label htmlFor="signup-email">Email</label>
              <input
                id="signup-email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                required
              />
            </div>

            <div className="input-group password-group">
              <label htmlFor="signup-password">Password</label>
              <input
                id="signup-password"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                placeholder="Create a strong password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                required
              />
              <PasswordVisibilityButton
                isVisible={showPassword}
                onToggle={() => setShowPassword((p) => !p)}
              />
            </div>

            <ul className="password-rules" aria-label="Password requirements" aria-live="polite">
              {passwordRules.map((rule, i) => {
                const ok = rule.test.test(form.password);
                return (
                  <li key={i} className={ok ? "ok" : "bad"}>
                    <span aria-hidden="true">{ok ? "✓" : "○"}</span> {rule.label}
                  </li>
                );
              })}
            </ul>

            <button type="submit" className="auth-btn" disabled={!isStrongPassword || isSubmitting} aria-busy={isSubmitting}>
              <span className="auth-submit-label">
                {isSubmitting && <span className="ui-spinner" aria-hidden="true" />}
                {isSubmitting ? "Creating account…" : "Create account"}
              </span>
              {!isSubmitting && <span aria-hidden="true">↗</span>}
            </button>
          </form>

          <p className="auth-switch">
            Already have an account? <Link to="/login">Sign in</Link>
          </p>
          <div className="auth-card-footer"><span>✳</span> Your space to think out loud.</div>
        </section>
      </div>
    </main>
  );
}
