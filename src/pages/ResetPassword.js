import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api from "../api";
import "../styles/auth.css";

export default function ResetPassword() {
  const { uid, token } = useParams();
  const navigate = useNavigate();

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");

    if (password !== confirm) {
      setError("Passwords do not match");
      return;
    }

    try {
      await api.post("/api/auth/reset-password/", {
        uid,
        token,
        password,
      });
      setSuccess(true);
      setTimeout(() => navigate("/login"), 2000);
    } catch (err) {
      setError(err.response?.data?.error || "Reset failed");
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h2>Reset Password</h2>
        <p className="subtitle">Create a new secure password</p>

        {error && <div className="error-box">{error}</div>}

        {success ? (
          <div className="success-box">
            Password reset successful. Redirecting to login…
          </div>
        ) : (
          <form onSubmit={submit}>
            <div className="input-group">
              <input
                type="password"
                placeholder="New password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            <div className="input-group">
              <input
                type="password"
                placeholder="Confirm password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
              />
            </div>

            <button type="submit" className="auth-btn">
              Reset Password
            </button>
          </form>
        )}

        {!success && (
          <div className="auth-links" style={{ justifyContent: "center" }}>
            <span onClick={() => navigate("/login")}>Back to Login</span>
          </div>
        )}
      </div>
    </div>
  );
}
