import { fireEvent, render, screen, within } from "@testing-library/react";
import LandingPage from "./pages/LandingPage";

jest.mock(
  "react-router-dom",
  () => ({
    Link: ({ to, children, ...props }) =>
      require("react").createElement("a", { ...props, href: to }, children),
  }),
  { virtual: true }
);

test("shows the public landing page and account entry points", () => {
  render(<LandingPage />);

  expect(
    screen.getByRole("heading", { name: /a little more human in your corner/i })
  ).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /start chatting/i })).toHaveAttribute(
    "href",
    "/signup"
  );
  expect(screen.getAllByRole("link", { name: /log in/i })[0]).toHaveAttribute(
    "href",
    "/login"
  );
  const navigation = within(screen.getByRole("navigation", { name: /main navigation/i }));
  expect(navigation.queryByRole("link", { name: "Explore" })).not.toBeInTheDocument();
  expect(navigation.getByRole("link", { name: "Log in" })).toHaveAttribute(
    "href",
    "/login"
  );
  expect(navigation.getByRole("link", { name: /get started/i })).toHaveAttribute(
    "href",
    "/signup"
  );
  expect(navigation.getByRole("link", { name: "About" })).toHaveAttribute(
    "href",
    "/about"
  );
  expect(screen.getByRole("heading", { name: /more than a blank chat/i })).toBeInTheDocument();
});

test("Take a look scrolls to features without navigating", () => {
  render(<LandingPage />);
  const features = document.getElementById("features");
  features.scrollIntoView = jest.fn();
  const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;

  fireEvent.click(screen.getByRole("link", { name: /take a look/i }));

  expect(features.scrollIntoView).toHaveBeenCalledWith({
    behavior: "smooth",
    block: "start",
  });
  expect(`${window.location.pathname}${window.location.search}${window.location.hash}`).toBe(currentUrl);
});

test("the hero preview tilts toward the pointer and resets when the pointer leaves", () => {
  render(<LandingPage />);
  const visual = document.querySelector(".landing-visual");
  visual.getBoundingClientRect = () => ({
    left: 0,
    top: 0,
    right: 100,
    bottom: 100,
    width: 100,
    height: 100,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  });

  const pointerMoveEvent = new Event("pointermove", { bubbles: true });
  Object.defineProperties(pointerMoveEvent, {
    clientX: { value: 75 },
    clientY: { value: 25 },
    pointerType: { value: "mouse" },
  });
  fireEvent(visual, pointerMoveEvent);
  expect(visual.style.getPropertyValue("--landing-tilt-x")).toBe("2.50deg");
  expect(visual.style.getPropertyValue("--landing-tilt-y")).toBe("2.00deg");

  fireEvent.pointerLeave(visual);
  expect(visual.style.getPropertyValue("--landing-tilt-x")).toBe("0deg");
  expect(visual.style.getPropertyValue("--landing-tilt-y")).toBe("0deg");
});

test("enables document scrolling only while the landing page is mounted", () => {
  const { unmount } = render(<LandingPage />);

  expect(document.documentElement).toHaveClass("landing-page-scroll");
  expect(document.body).toHaveClass("landing-page-scroll");

  unmount();
  expect(document.documentElement).not.toHaveClass("landing-page-scroll");
  expect(document.body).not.toHaveClass("landing-page-scroll");
});
