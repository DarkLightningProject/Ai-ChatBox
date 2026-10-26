import { render } from "@testing-library/react";
import TypingIndicator, { TYPING_INDICATOR_OPTIONS } from "./TypingIndicator";

test("provides four animated response indicators", () => {
  expect(TYPING_INDICATOR_OPTIONS.map(({ value }) => value)).toEqual([
    "sparkle",
    "pulse",
    "starburst",
    "dots",
  ]);

  TYPING_INDICATOR_OPTIONS.forEach(({ value }) => {
    const { container, unmount } = render(<TypingIndicator variant={value} />);
    expect(container.querySelector(`.typing-indicator--${value}`)).toBeInTheDocument();
    unmount();
  });
});
