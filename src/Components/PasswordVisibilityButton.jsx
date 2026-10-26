import React from "react";

export default function PasswordVisibilityButton({ isVisible, onToggle }) {
  return (
    <button
      type="button"
      className="eye-btn"
      aria-label={isVisible ? "Hide password" : "Show password"}
      aria-pressed={isVisible}
      onClick={onToggle}
    >
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        {isVisible ? (
          <>
            <path d="M3 3l18 18M10.6 10.6a2 2 0 0 0 2.8 2.8" />
            <path d="M9.9 5.2A10.8 10.8 0 0 1 12 5c5.2 0 8.7 4.3 9.5 7-.3 1.1-1.1 2.4-2.2 3.6M6.2 6.2C3.9 7.6 2.7 9.8 2.5 12c.8 2.7 4.3 7 9.5 7 1 0 1.9-.2 2.8-.5" />
          </>
        ) : (
          <>
            <path d="M2.5 12S6 5 12 5s9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7Z" />
            <circle cx="12" cy="12" r="2.5" />
          </>
        )}
      </svg>
    </button>
  );
}
