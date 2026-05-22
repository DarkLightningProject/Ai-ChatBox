/**
 * PaymentSuccess.jsx
 *
 * Shows success or failure result based on navigate() state set by Checkout.jsx.
 * Never trusts any URL param for payment status — result comes from verify-payment API.
 */

import { Link, useLocation, useNavigate } from "react-router-dom";
import "../styles/checkout.css";

export default function PaymentSuccess() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state || {};

  const failed = Boolean(state.failed);
  const paymentId = state.payment_id || "";
  const orderId = state.order_id || "";
  const amountPaise = state.amount || 0;
  const reason = state.reason || "An unexpected error occurred.";

  // If someone navigates here directly with no state, redirect to checkout
  if (!orderId && !paymentId && !failed) {
    navigate("/checkout", { replace: true });
    return null;
  }

  const rupees =
    amountPaise > 0 ? `₹${(amountPaise / 100).toLocaleString("en-IN")}` : "";

  if (failed) {
    return (
      <div className="payment-result-page">
        <div className="payment-result-card">
          <div className="result-icon" aria-label="Payment failed">
            ❌
          </div>
          <h2>Payment Failed</h2>
          <p>{reason}</p>

          {orderId && (
            <div className="result-detail">
              <strong>Order ID:</strong> {orderId}
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <button
              className="result-action-btn"
              onClick={() => navigate("/checkout")}
            >
              Try Again
            </button>
            <Link to="/" className="result-action-btn secondary">
              Back to Home
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="payment-result-page">
      <div className="payment-result-card">
        <div className="result-icon" aria-label="Payment successful">
          ✅
        </div>
        <h2>Payment Successful</h2>
        <p>
          {rupees
            ? `Your payment of ${rupees} was received successfully.`
            : "Your payment was received successfully."}
        </p>

        <div className="result-detail">
          {paymentId && (
            <div>
              <strong>Payment ID:</strong> {paymentId}
            </div>
          )}
          {orderId && (
            <div style={{ marginTop: "0.35rem" }}>
              <strong>Order ID:</strong> {orderId}
            </div>
          )}
        </div>

        <Link to="/" className="result-action-btn">
          Continue to App
        </Link>
      </div>
    </div>
  );
}
