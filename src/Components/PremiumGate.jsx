/**
 * PremiumGate.jsx
 *
 * Wraps any premium-only UI. If the user is not premium, renders a
 * locked overlay with an upgrade CTA instead of the children.
 *
 * Usage:
 *   <PremiumGate isPremium={isPremium} theme={theme} featureName="Uncensored Mode">
 *     <YourPremiumComponent />
 *   </PremiumGate>
 */

import { useNavigate } from "react-router-dom";
import "./PremiumGate.css";

export default function PremiumGate({ isPremium, children, featureName = "this feature", theme = "light" }) {
  const navigate = useNavigate();

  if (isPremium) return children;

  return (
    <div className={`premium-gate ${theme}-theme`}>
      <div className="premium-gate-overlay">
        <div className="premium-gate-card">
          <div className="premium-gate-icon">🔒</div>
          <h3>Premium Feature</h3>
          <p>
            <strong>{featureName}</strong> is available on the Pro plan.
            Upgrade to unlock all AI modes.
          </p>
          <button
            className="premium-gate-btn"
            onClick={() => navigate("/checkout")}
          >
            Upgrade to Pro
          </button>
        </div>
      </div>
    </div>
  );
}
