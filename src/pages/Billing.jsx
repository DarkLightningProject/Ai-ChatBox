import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "../api";
import "../styles/checkout.css";

export default function Billing() {
  const navigate = useNavigate();
  const [status, setStatus] = useState(null); // null = loading
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/api/payments/billing-status/")
      .then((res) => setStatus(res.data))
      .catch(() => setError("Failed to load billing info."));
  }, []);

  if (!status && !error) {
    return (
      <div className="billing-page">
        <div className="billing-card">
          <div className="billing-loading">Loading billing info…</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="billing-page">
        <div className="billing-card">
          <p className="billing-error">{error}</p>
          <Link to="/" className="result-action-btn secondary">Back to App</Link>
        </div>
      </div>
    );
  }

  const { is_premium, source, premium_granted_at, order } = status;

  // Format helpers
  const fmtDate = (iso) =>
    iso ? new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "—";
  const fmtAmount = (paise) =>
    paise ? `₹${(paise / 100).toLocaleString("en-IN")}` : "—";

  // ── Paid via Razorpay ──────────────────────────────────────────────────
  if (is_premium && source === "payment") {
    return (
      <div className="billing-page">
        <div className="billing-card">
          <Link to="/" className="billing-back">← Back to App</Link>

          <div className="billing-header">
            <span className="billing-badge paid">✓ Paid</span>
            <h2>Multi-Debugger Pro</h2>
            <p className="billing-sub">One-time purchase — lifetime access</p>
          </div>

          <div className="billing-detail-block">
            <div className="billing-row">
              <span>Status</span>
              <strong className="text-green">Active</strong>
            </div>
            <div className="billing-row">
              <span>Amount paid</span>
              <strong>{fmtAmount(order?.amount)}</strong>
            </div>
            <div className="billing-row">
              <span>Date</span>
              <strong>{fmtDate(order?.created_at)}</strong>
            </div>
            {order?.order_id && (
              <div className="billing-row">
                <span>Order ID</span>
                <span className="billing-mono">{order.order_id}</span>
              </div>
            )}
            {order?.razorpay_payment_id && (
              <div className="billing-row">
                <span>Payment ID</span>
                <span className="billing-mono">{order.razorpay_payment_id}</span>
              </div>
            )}
          </div>

          <div className="billing-features">
            <h4>What you unlocked</h4>
            <ul>
              <li>⭐ Multi-Debugger Premium tier</li>
              <li>🔬 Logic Analyst — Gemini 2.5 Pro</li>
              <li>🛠️ Syntax Inspector — GPT-4.1</li>
              <li>⚡ Perf &amp; Security — Claude Opus 4.5</li>
              <li>🧠 Synthesizer — Claude Sonnet 4.5</li>
            </ul>
          </div>
        </div>
      </div>
    );
  }

  // ── Special permission (admin-granted) ────────────────────────────────
  if (is_premium && source === "admin_grant") {
    return (
      <div className="billing-page">
        <div className="billing-card">
          <Link to="/" className="billing-back">← Back to App</Link>

          <div className="billing-header">
            <span className="billing-badge special">✦ Special Access</span>
            <h2>Multi-Debugger Pro</h2>
            <p className="billing-sub">Access granted by administrator</p>
          </div>

          <div className="billing-detail-block">
            <div className="billing-row">
              <span>Status</span>
              <strong className="text-purple">Active — Complimentary</strong>
            </div>
            <div className="billing-row">
              <span>Granted on</span>
              <strong>{fmtDate(premium_granted_at)}</strong>
            </div>
          </div>

          <div className="billing-features">
            <h4>What you have access to</h4>
            <ul>
              <li>⭐ Multi-Debugger Premium tier</li>
              <li>🔬 Logic Analyst — Gemini 2.5 Pro</li>
              <li>🛠️ Syntax Inspector — GPT-4.1</li>
              <li>⚡ Perf &amp; Security — Claude Opus 4.5</li>
              <li>🧠 Synthesizer — Claude Sonnet 4.5</li>
            </ul>
          </div>
        </div>
      </div>
    );
  }

  // ── Not premium — show upgrade card ───────────────────────────────────
  return (
    <div className="billing-page">
      <div className="billing-card">
        <Link to="/" className="billing-back">← Back to App</Link>

        <div className="billing-header">
          <span className="billing-badge free">Free Plan</span>
          <h2>Upgrade to Pro</h2>
          <p className="billing-sub">Unlock premium AI models in Multi-Debugger</p>
        </div>

        <ul className="checkout-features" style={{ marginBottom: "1.5rem" }}>
          <li><span className="icon">✓</span> Gemini 2.5 Pro for Logic Analysis</li>
          <li><span className="icon">✓</span> GPT-4.1 for Syntax Inspection</li>
          <li><span className="icon">✓</span> Claude Opus 4.5 for Perf &amp; Security</li>
          <li><span className="icon">✓</span> Claude Sonnet 4.5 as Synthesizer</li>
          <li><span className="icon">✓</span> One-time payment — no subscription</li>
        </ul>

        <button
          className="pay-btn"
          onClick={() => navigate("/checkout")}
        >
          Upgrade Now
        </button>
      </div>
    </div>
  );
}
