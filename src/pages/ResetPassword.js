import React, { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api from "../api";
import ThemeToggle from "../Components/ThemeToggle";
import PasswordVisibilityButton from "../Components/PasswordVisibilityButton";
import "../styles/auth.css";

const PASSWORD_RULES = [
  { test: /.{8,}/, label: "At least 8 characters" },
  { test: /[A-Z]/, label: "One uppercase letter" },
  { test: /[a-z]/, label: "One lowercase letter" },
  { test: /[0-9]/, label: "One number" },
  { test: /[!@#$%^&*(),.?":{}|<>]/, label: "One special character" },
];

export default function ResetPassword({ theme = "light", onToggleTheme }) {
  const { uid, token } = useParams();
  const navigate = useNavigate();

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isStrongPassword = PASSWORD_RULES.every((rule) => rule.test.test(password));

  const submit = async (e) => {
    e.preventDefault();
    if (isSubmitting) return;
    setError("");

    if (!isStrongPassword) {
      setError("Password does not meet security requirements.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }

    setIsSubmitting(true);
    try {
      await api.post("/api/auth/reset-password/", { uid, token, password });
      setSuccess(true);
      setTimeout(() => navigate("/login"), 2000);
    } catch (err) {
      setError(err.response?.data?.error || "Reset failed. Please try again.");
      setIsSubmitting(false);
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
        <section className="auth-showcase" aria-label="AI ChatBox password reset">
          <span className="auth-showcase-eyebrow"><span /> A SPACE FOR YOUR NEXT THOUGHT</span>
          <h1>A new key<br />to unlock<br /><span>what’s next.</span></h1>
          <p>Choose a strong new password and get right back to your conversations, ideas, and work.</p>
          <div className="auth-showcase-note">
            <span className="auth-showcase-note-icon" aria-hidden="true">✦</span>
            <span><strong>Keep your account secure.</strong><small>A strong password is a great start.</small></span>
          </div>
          <div className="auth-showcase-orb auth-showcase-orb-one" />
          <div className="auth-showcase-orb auth-showcase-orb-two" />
        </section>

        <section
          className={`auth-card${success ? " auth-success-card" : ""}`}
          aria-labelledby="reset-heading"
          aria-live="polite"
        >
          {success ? (
            <>
              <div className="verify-icon verify-icon--success" aria-hidden="true">✓</div>
              <span className="auth-card-kicker">ALL SET</span>
              <h2 id="reset-heading">Password updated.</h2>
              <p className="subtitle">Your password has been reset successfully. You can now sign in with your new password.</p>
              <Link className="auth-btn auth-button-link" to="/login">
                <span>Go to sign in</span><span aria-hidden="true">↗</span>
              </Link>
              <div className="auth-card-footer"><span>✳</span> Your space to think out loud.</div>
            </>
          ) : (
            <>
              <div className="auth-card-heading">
                <span className="auth-card-kicker">ACCOUNT RECOVERY</span>
                <h2 id="reset-heading">Set a new password.</h2>
                <p className="subtitle">Create a secure password you haven’t used before.</p>
              </div>

              {error && <div className="error-box" role="alert">{error}</div>}

              <form className="auth-form" onSubmit={submit}>
                <div className="input-group password-group">
                  <label htmlFor="reset-password">New password</label>
                  <input
                    id="reset-password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    placeholder="Create a strong password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                  <PasswordVisibilityButton
                    isVisible={showPassword}
                    onToggle={() => setShowPassword((visible) => !visible)}
                  />
                </div>

                <div className="input-group password-group">
                  <label htmlFor="reset-confirm-password">Confirm new password</label>
                  <input
                    id="reset-confirm-password"
                    type={showConfirm ? "text" : "password"}
                    autoComplete="new-password"
                    placeholder="Enter your new password again"
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    required
                  />
                  <PasswordVisibilityButton
                    isVisible={showConfirm}
                    onToggle={() => setShowConfirm((visible) => !visible)}
                  />
                </div>

                <ul className="password-rules" aria-label="Password requirements" aria-live="polite">
                  {PASSWORD_RULES.map((rule) => {
                    const isValid = rule.test.test(password);
                    return (
                      <li key={rule.label} className={isValid ? "ok" : "bad"}>
                        <span aria-hidden="true">{isValid ? "✓" : "○"}</span> {rule.label}
                      </li>
                    );
                  })}
                </ul>

                <button
                  type="submit"
                  className="auth-btn"
                  disabled={!isStrongPassword || isSubmitting}
                  aria-busy={isSubmitting}
                >
                  <span className="auth-submit-label">
                    {isSubmitting && <span className="ui-spinner" aria-hidden="true" />}
                    {isSubmitting ? "Updating password…" : "Reset password"}
                  </span>
                  {!isSubmitting && <span aria-hidden="true">↗</span>}
                </button>
              </form>

              <p className="auth-switch">
                Remembered your password? <Link to="/login">Sign in</Link>
              </p>
              <div className="auth-card-footer"><span>✳</span> Your space to think out loud.</div>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
