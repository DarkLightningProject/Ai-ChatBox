import { fireEvent, render, screen } from "@testing-library/react";
import ResetPassword from "./ResetPassword";
import api from "../api";

const mockNavigate = jest.fn();

jest.mock(
  "react-router-dom",
  () => ({
    Link: ({ to, children, ...props }) =>
      require("react").createElement("a", { ...props, href: to }, children),
    useParams: () => ({ uid: "test-uid", token: "test-token" }),
    useNavigate: () => mockNavigate,
  }),
  { virtual: true }
);

jest.mock("../api", () => ({
  __esModule: true,
  default: { post: jest.fn() },
}));

beforeEach(() => {
  jest.clearAllMocks();
});

test("renders themed password reset fields with independent eye toggles", () => {
  render(<ResetPassword theme="dark" />);

  expect(screen.getByRole("main")).toHaveClass("auth-page", "dark-theme");
  expect(screen.getByLabelText("New password")).toHaveAttribute("type", "password");
  expect(screen.getByLabelText("Confirm new password")).toHaveAttribute("type", "password");

  fireEvent.click(screen.getAllByRole("button", { name: "Show password" })[0]);

  expect(screen.getByLabelText("New password")).toHaveAttribute("type", "text");
  expect(screen.getByLabelText("Confirm new password")).toHaveAttribute("type", "password");
});

test("submits matching strong passwords and displays success", async () => {
  api.post.mockResolvedValue({});
  render(<ResetPassword />);

  fireEvent.change(screen.getByLabelText("New password"), {
    target: { value: "StrongPass1!" },
  });
  fireEvent.change(screen.getByLabelText("Confirm new password"), {
    target: { value: "StrongPass1!" },
  });
  fireEvent.click(screen.getByRole("button", { name: /reset password/i }));

  expect(await screen.findByRole("heading", { name: /password updated/i })).toBeInTheDocument();
  expect(api.post).toHaveBeenCalledWith("/api/auth/reset-password/", {
    uid: "test-uid",
    token: "test-token",
    password: "StrongPass1!",
  });
});

test("rejects mismatched passwords without calling the API", () => {
  render(<ResetPassword />);

  fireEvent.change(screen.getByLabelText("New password"), {
    target: { value: "StrongPass1!" },
  });
  fireEvent.change(screen.getByLabelText("Confirm new password"), {
    target: { value: "DifferentPass1!" },
  });
  fireEvent.click(screen.getByRole("button", { name: /reset password/i }));

  expect(screen.getByRole("alert")).toHaveTextContent("Passwords do not match.");
  expect(api.post).not.toHaveBeenCalled();
});
