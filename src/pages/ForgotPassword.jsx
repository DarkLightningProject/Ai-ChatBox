import React, { useState } from "react";
import { forgotPassword } from "../api/auth";
import { useNavigate } from "react-router-dom";
import "../styles/auth.css";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState("");
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setMsg("");

    try {
      await forgotPassword({ email });
      setMsg("Reset link sent. Check your email inbox.");
    } catch {
      setMsg("Email not found.");
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h2>Forgot Password</h2>
        <p className="subtitle">
          Enter your registered email to reset your password
        </p>

        {msg && <div className="error-box">{msg}</div>}

        <form onSubmit={submit}>
          <div className="input-group">
            <input
              type="email"
              placeholder="Email address"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <button type="submit" className="auth-btn">
            Send Reset Link
          </button>
        </form>

        <div className="auth-links" style={{ justifyContent: "center" }}>
          <span onClick={() => navigate("/login")}>
            Back to Login
          </span>
        </div>
      </div>
    </div>
  );
}
