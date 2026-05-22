import React, { useState } from "react";
import { signup } from "../api/auth";
import { useNavigate } from "react-router-dom";
import "../styles/auth.css";

export default function Signup() {
  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
  });

  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [success, setSuccess] = useState(false);
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
    setError("");

    if (!isStrongPassword) {
      setError("Password does not meet security requirements.");
      return;
    }

    try {
      await signup(form);
      setSuccess(true);
    } catch (err) {
      setError(err.response?.data?.error || "Signup failed");
    }
  };

  if (success) {
    return (
      <div className="auth-container">
        <div className="auth-card" style={{ textAlign: "center" }}>
          <div className="verify-icon verify-icon--success">✓</div>
          <h2>Account Created!</h2>
          <p className="subtitle">
            A verification link has been sent to <strong>{form.email}</strong>.
            <br />Please check your inbox and click the link to activate your account.
          </p>
          <button
            className="auth-btn"
            style={{ marginTop: "1.25rem" }}
            onClick={() => navigate("/login")}
          >
            Go to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h2>Create Account</h2>
        <p className="subtitle">Join us to get started</p>

        {error && <div className="error-box">{error}</div>}

        <form onSubmit={submit}>
          {/* Username */}
          <div className="input-group">
            <input
              type="text"
              placeholder="Username"
              value={form.username}
              onChange={(e) =>
                setForm({ ...form, username: e.target.value })
              }
              required
            />
          </div>

          {/* Email */}
          <div className="input-group">
            <input
              type="email"
              placeholder="Email"
              value={form.email}
              onChange={(e) =>
                setForm({ ...form, email: e.target.value })
              }
              required
            />
          </div>

          {/* Password */}
          <div className="input-group password-group">
            <input
              type={showPassword ? "text" : "password"}
              placeholder="Password"
              value={form.password}
              onChange={(e) =>
                setForm({ ...form, password: e.target.value })
              }
              required
            />
            <button type="button" className="eye-btn" onClick={() => setShowPassword(p => !p)}>
              {showPassword ? "Hide" : "Show"}
            </button>
          </div>

          {/* Password rules */}
          <ul className="password-rules">
            {passwordRules.map((rule, i) => {
              const ok = rule.test.test(form.password);
              return (
                <li key={i} className={ok ? "ok" : "bad"}>
                  {ok ? "✔" : "✖"} {rule.label}
                </li>
              );
            })}
          </ul>

          <button
            type="submit"
            className="auth-btn"
            disabled={!isStrongPassword}
          >
            Create Account
          </button>
        </form>

        <div className="auth-links" style={{ justifyContent: "center" }}>
          <span onClick={() => navigate("/login")}>
            Already have an account? Login
          </span>
        </div>
      </div>
    </div>
  );
}
