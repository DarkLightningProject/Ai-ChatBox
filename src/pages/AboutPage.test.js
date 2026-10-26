import { render, screen } from "@testing-library/react";
import AboutPage from "./AboutPage";

jest.mock(
  "react-router-dom",
  () => ({
    Link: ({ to, children, ...props }) =>
      require("react").createElement("a", { ...props, href: to }, children),
  }),
  { virtual: true }
);

test("explains the prototype technology stack and navigation", () => {
  render(<AboutPage theme="light" />);

  expect(screen.getByRole("heading", { name: /curiosity deserves a good conversation/i })).toBeInTheDocument();
  expect(screen.getByRole("note")).toHaveTextContent(
    "This is a prototype. Use dummy details only to try logging in or signing up. Do not enter real or sensitive information. The site owner is not responsible if information you submit is exposed or leaked."
  );
  expect(screen.queryByText(/prototype notice/i)).not.toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /what this website is built with/i })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Frontend" })).toBeInTheDocument();
  expect(screen.getByText(/react, javascript, and css/i)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Backend" })).toBeInTheDocument();
  expect(screen.getByText(/python, django, and django rest framework/i)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Data storage" })).toBeInTheDocument();
  expect(screen.getByText(/sqlite is used locally, with supabase-hosted postgresql for production/i)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "AI integrations" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Media & hosting" })).toBeInTheDocument();
  expect(screen.getByText(/cloudinary stores uploaded media in production, and render hosts the backend service/i)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "eclipsexautomationsolution@gmail.com" })).toHaveAttribute(
    "href",
    "mailto:eclipsexautomationsolution@gmail.com"
  );
  expect(screen.getByRole("link", { name: /get started/i })).toHaveAttribute("href", "/signup");
  expect(screen.getByRole("link", { name: /back to home/i })).toHaveAttribute("href", "/");
});

test("enables page scrolling only while About is mounted", () => {
  const { unmount } = render(<AboutPage />);

  expect(document.documentElement).toHaveClass("landing-page-scroll");
  expect(document.body).toHaveClass("landing-page-scroll");

  unmount();

  expect(document.documentElement).not.toHaveClass("landing-page-scroll");
  expect(document.body).not.toHaveClass("landing-page-scroll");
});
