import { render, screen, waitFor } from "@testing-library/react";
import AboutPage from "./AboutPage";
import api from "../api";

jest.mock("../api", () => ({
  __esModule: true,
  default: { get: jest.fn() },
}));

jest.mock(
  "react-router-dom",
  () => ({
    Link: ({ to, children, ...props }) =>
      require("react").createElement("a", { ...props, href: to }, children),
  }),
  { virtual: true }
);

beforeEach(() => {
  api.get.mockReset().mockRejectedValue(new Error("Not authenticated"));
});

test("explains the prototype technology stack and navigation", async () => {
  api.get.mockRejectedValue(new Error("Not authenticated"));
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
  await waitFor(() => {
    expect(screen.getByRole("link", { name: /log in/i })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("link", { name: /get started/i })).toHaveAttribute("href", "/signup");
  });
});

test("hides login and signup links when the user is authenticated", async () => {
  api.get.mockResolvedValue({ data: { user_id: 1 } });

  render(<AboutPage theme="light" />);

  await waitFor(() => {
    expect(api.get).toHaveBeenCalledWith("/api/auth/me/");
    expect(screen.queryByRole("link", { name: /log in/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /get started/i })).not.toBeInTheDocument();
  });
});

test("enables page scrolling only while About is mounted", () => {
  api.get.mockReturnValue(new Promise(() => {}));
  const { unmount } = render(<AboutPage />);

  expect(document.documentElement).toHaveClass("landing-page-scroll");
  expect(document.body).toHaveClass("landing-page-scroll");

  unmount();

  expect(document.documentElement).not.toHaveClass("landing-page-scroll");
  expect(document.body).not.toHaveClass("landing-page-scroll");
});
