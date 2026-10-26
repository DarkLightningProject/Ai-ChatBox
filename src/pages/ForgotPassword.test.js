import { fireEvent, render, screen } from "@testing-library/react";
import ForgotPassword from "./ForgotPassword";
import { forgotPassword } from "../api/auth";

jest.mock(
  "react-router-dom",
  () => ({
    Link: ({ to, children, ...props }) =>
      require("react").createElement("a", { ...props, href: to }, children),
  }),
  { virtual: true }
);

jest.mock("../api/auth", () => ({
  forgotPassword: jest.fn(),
}));

test("renders the themed recovery page and its successful reset state", async () => {
  forgotPassword.mockResolvedValue({});
  render(<ForgotPassword theme="dark" />);

  expect(screen.getByRole("main")).toHaveClass("auth-page", "dark-theme");
  expect(screen.getByRole("heading", { name: /forgot your password/i })).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText(/email address/i), {
    target: { value: "person@example.com" },
  });
  fireEvent.click(screen.getByRole("button", { name: /send reset link/i }));

  expect(await screen.findByRole("heading", { name: /reset link sent/i })).toBeInTheDocument();
  expect(screen.getByText(/person@example\.com/)).toBeInTheDocument();
  expect(forgotPassword).toHaveBeenCalledWith({ email: "person@example.com" });
});
