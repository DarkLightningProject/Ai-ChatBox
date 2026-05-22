/**
 * Checkout.jsx
 *
 * Security contract (matches backend):
 *   - NEVER generates or stores an order_id locally.
 *   - order_id always comes exclusively from POST /api/payments/create-order/.
 *   - All three Razorpay values (payment_id, order_id, signature) are sent to
 *     POST /api/payments/verify-payment/ — the backend performs the real check.
 *   - checkout.js script is loaded dynamically only when the user clicks Pay.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api";
import "../styles/checkout.css";

// ---------------------------------------------------------------------------
// Dynamic loader for Razorpay checkout.js
// ---------------------------------------------------------------------------
function loadRazorpayScript() {
  return new Promise((resolve) => {
    if (window.Razorpay) {
      resolve(true);
      return;
    }
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.onload = () => resolve(true);
    script.onerror = () => resolve(false);
    document.body.appendChild(script);
  });
}

// ---------------------------------------------------------------------------
// Props:
//   amountPaise  – amount in paise (e.g. 49900 = ₹499)
//   planName     – display label (e.g. "Pro Plan")
//   features     – string[] shown as a checklist
//   period       – display period (e.g. "/month")
// ---------------------------------------------------------------------------
export default function Checkout({
  amountPaise = 49900,
  planName = "Multi-Debugger Pro",
  features = [
    "Gemini 2.5 Pro — Logic Analyst",
    "GPT-4.1 — Syntax Inspector",
    "Claude Opus 4.5 — Perf & Security",
    "Claude Sonnet 4.5 — Synthesizer",
    "One-time payment, lifetime access",
  ],
  period = "",
}) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Prevent duplicate orders if the button is somehow clicked twice
  const inFlightRef = useRef(false);

  // Read user info from localStorage (set by RequireAuth in App.js)
  const user = (() => {
    try {
      return JSON.parse(localStorage.getItem("user") || "{}");
    } catch {
      return {};
    }
  })();

  const handlePay = useCallback(async () => {
    if (inFlightRef.current) return; // guard double-click
    inFlightRef.current = true;
    setLoading(true);
    setError("");

    try {
      // ------------------------------------------------------------------
      // 1. Load checkout.js BEFORE calling the backend (parallel warm-up)
      // ------------------------------------------------------------------
      const [scriptLoaded, orderRes] = await Promise.all([
        loadRazorpayScript(),
        api.post("/api/payments/create-order/", {
          amount: amountPaise,
          currency: "INR",
        }),
      ]);

      if (!scriptLoaded) {
        throw new Error(
          "Razorpay checkout could not be loaded. Check your connection."
        );
      }

      // ------------------------------------------------------------------
      // 2. Unpack order — order_id comes ONLY from the backend
      // ------------------------------------------------------------------
      const { order_id, amount, currency, key_id } = orderRes.data;

      // ------------------------------------------------------------------
      // 3. Open Razorpay modal
      // ------------------------------------------------------------------
      const options = {
        key: key_id,               // rzp_test_... — safe to expose
        amount,                    // paise, echoed from backend
        currency,
        name: "AI ChatBox",
        description: planName,
        order_id,                  // issued by backend — not generated here

        // Prefill for smoother UX
        prefill: {
          name: user.name || user.username || "",
          email: user.email || "",
          contact: user.phone || "",
        },

        theme: { color: "#2563eb" },

        // ------------------------------------------------------------------
        // 4. On successful payment — send all 3 values to backend to verify
        // ------------------------------------------------------------------
        handler: async (response) => {
          try {
            const verifyRes = await api.post("/api/payments/verify-payment/", {
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_order_id: response.razorpay_order_id,
              razorpay_signature: response.razorpay_signature,
            });

            if (
              verifyRes.data.status === "captured" ||
              verifyRes.data.status === "already_captured"
            ) {
              navigate("/payment-success", {
                state: {
                  payment_id: response.razorpay_payment_id,
                  order_id: response.razorpay_order_id,
                  amount: amountPaise,
                },
              });
            } else {
              setError("Payment verification returned an unexpected status.");
            }
          } catch (verifyErr) {
            const msg =
              verifyErr?.response?.data?.error ||
              "Payment verification failed. Please contact support.";
            navigate("/payment-success", {
              state: {
                failed: true,
                reason: msg,
                order_id: response.razorpay_order_id,
              },
            });
          } finally {
            setLoading(false);
            inFlightRef.current = false;
          }
        },

        // ------------------------------------------------------------------
        // 5. User closed the modal — reset UI so they can try again
        // ------------------------------------------------------------------
        modal: {
          ondismiss: () => {
            setLoading(false);
            inFlightRef.current = false;
          },
        },
      };

      const rzp = new window.Razorpay(options);

      rzp.on("payment.failed", (response) => {
        const reason =
          response?.error?.description || "Payment failed. Please try again.";
        navigate("/payment-success", {
          state: {
            failed: true,
            reason,
            order_id,
          },
        });
        setLoading(false);
        inFlightRef.current = false;
      });

      rzp.open();

      // Don't reset loading/inFlight here — they're reset inside handler/ondismiss
    } catch (err) {
      const msg =
        err?.response?.data?.error ||
        err?.message ||
        "Something went wrong. Please try again.";
      setError(msg);
      setLoading(false);
      inFlightRef.current = false;
    }
  }, [amountPaise, planName, user, navigate]);

  // Clean up any Razorpay modal if component unmounts mid-flow
  useEffect(() => {
    return () => {
      inFlightRef.current = false;
    };
  }, []);

  const rupees = (amountPaise / 100).toLocaleString("en-IN");

  return (
    <div className="checkout-page">
      <div className="checkout-card">
        <h2>{planName}</h2>
        <p className="checkout-subtitle">One-time secure payment via Razorpay</p>

        <div className="checkout-amount">
          <span className="currency">₹</span>
          <span className="value">{rupees}</span>
          {period && <span className="period">{period}</span>}
        </div>

        <hr className="checkout-divider" />

        <ul className="checkout-features">
          {features.map((f) => (
            <li key={f}>
              <span className="icon">✓</span>
              {f}
            </li>
          ))}
        </ul>

        <button
          className="pay-btn"
          onClick={handlePay}
          disabled={loading}
          aria-busy={loading}
        >
          {loading ? (
            <>
              <span className="spinner" aria-hidden="true" />
              Processing…
            </>
          ) : (
            `Pay ₹${rupees}`
          )}
        </button>

        {error && <div className="checkout-error">{error}</div>}

        <p className="checkout-secure">
          <span aria-hidden="true">🔒</span>
          Payments are secured by Razorpay
        </p>
      </div>
    </div>
  );
}
