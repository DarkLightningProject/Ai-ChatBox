import React from "react";

export const TYPING_INDICATOR_OPTIONS = [
  { value: "sparkle", label: "Sparkle" },
  { value: "pulse", label: "Pulse" },
  { value: "starburst", label: "Starburst" },
  { value: "dots", label: "Dots" },
];

export default function TypingIndicator({ variant = "sparkle" }) {
  if (variant === "dots") {
    return (
      <span className="typing-indicator typing-indicator--dots" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
    );
  }

  return (
    <span className={`typing-indicator typing-indicator--${variant}`} aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none">
        {variant === "pulse" ? (
          <>
            <circle className="typing-pulse-ring" cx="12" cy="12" r="7" />
            <circle className="typing-pulse-core" cx="12" cy="12" r="3" />
          </>
        ) : variant === "starburst" ? (
          <path
            className="typing-starburst"
            d="M12 2.5 13.5 9l5-4-2.5 6.5 6.5.5-6.5 2.5 4 5-6.5-2.5-.5 6.5-2.5-6.5-5 4 2.5-6.5-6.5-.5 6.5-2.5-4-5 6.5 2.5L12 2.5Z"
          />
        ) : (
          <>
            <path
              className="typing-sparkle-main"
              d="m12 3 1.8 6.2L20 11l-6.2 1.8L12 19l-1.8-6.2L4 11l6.2-1.8L12 3Z"
            />
            <path
              className="typing-sparkle-small"
              d="m19 16 .8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8L19 16Z"
            />
          </>
        )}
      </svg>
    </span>
  );
}
