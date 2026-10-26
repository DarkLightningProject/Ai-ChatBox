import React, { useState } from "react";
import { login } from "../api/auth";
import { Link, useNavigate } from "react-router-dom";
import ThemeToggle from "../Components/ThemeToggle";
import PasswordVisibilityButton from "../Components/PasswordVisibilityButton";
import "../styles/auth.css";

export default function Login({ theme = "light", onToggleTheme }) {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    setError("");

    try {
      const res = await login({ identifier, password });
      localStorage.setItem("user", JSON.stringify(res.data));
      navigate("/app");
    } catch (err) {
      setError(err.response?.data?.error || "Invalid credentials");
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
        <section className="auth-showcase" aria-label="Welcome to conversa Ai">
          <span className="auth-showcase-eyebrow"><span /> A SPACE FOR YOUR NEXT THOUGHT</span>
          <h1>Good ideas<br />start with a<br /><span>conversation.</span></h1>
          <p>Bring your questions, your half-formed ideas, and the tricky problems. We’ll work through them together.</p>
          <div className="auth-showcase-note">
            <span className="auth-showcase-note-icon" aria-hidden="true">✦</span>
            <span><strong>Pick up where curiosity takes you.</strong><small>Chat, create, explore, repeat.</small></span>
          </div>
          <div className="auth-showcase-orb auth-showcase-orb-one" />
          <div className="auth-showcase-orb auth-showcase-orb-two" />
        </section>

        <section className="auth-card" aria-labelledby="login-heading">
          <div className="auth-card-heading">
            <span className="auth-card-kicker">WELCOME BACK</span>
            <h2 id="login-heading">Good to see you.</h2>
            <p className="subtitle">Sign in and pick up where you left off.</p>
          </div>

          {error && <div className="error-box" role="alert">{error}</div>}

          <form className="auth-form" onSubmit={submit}>
            <div className="input-group">
              <label htmlFor="login-identifier">Username or email</label>
              <input
                id="login-identifier"
                type="text"
                autoComplete="username"
                placeholder="you@example.com"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                required
              />
            </div>

            <div className="input-group password-group">
              <div className="auth-label-row">
                <label htmlFor="login-password">Password</label>
                <Link to="/forgot">Forgot password?</Link>
              </div>
              <input
                id="login-password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <PasswordVisibilityButton
                isVisible={showPassword}
                onToggle={() => setShowPassword((p) => !p)}
              />
            </div>

            <button type="submit" className="auth-btn" disabled={isSubmitting}>
              <span className="auth-submit-label">
                {isSubmitting && <span className="ui-spinner" aria-hidden="true" />}
                {isSubmitting ? "Signing in…" : "Sign in"}
              </span>
              {!isSubmitting && <span aria-hidden="true">↗</span>}
            </button>
          </form>

          <p className="auth-switch">
            New around here? <Link to="/signup">Create an account</Link>
          </p>
          <div className="auth-card-footer"><span>✳</span> Your space to think out loud.</div>
        </section>
      </div>
    </main>
  );
}
