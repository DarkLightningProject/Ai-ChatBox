import { fireEvent, render, screen } from "@testing-library/react";
import Signup from "./Signup";
import { signup } from "../api/auth";

const mockNavigate = jest.fn();

jest.mock(
  "react-router-dom",
  () => ({
    Link: ({ to, children, ...props }) =>
      require("react").createElement("a", { ...props, href: to }, children),
    useNavigate: () => mockNavigate,
  }),
  { virtual: true }
);

jest.mock("../api/auth", () => ({
  signup: jest.fn(),
}));

beforeEach(() => {
  jest.clearAllMocks();
});

test("shows a prototype alert when signup verification email delivery fails", async () => {
  signup.mockResolvedValue({
    data: {
      verification_email_sent: false,
    },
  });
  render(<Signup theme="light" />);

  fireEvent.change(screen.getByLabelText("Username"), {
    target: { value: "DemoUser" },
  });
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "demo@example.com" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "StrongPass1!" },
  });
  fireEvent.click(screen.getByRole("button", { name: /create account/i }));

  expect(await screen.findByRole("alertdialog")).toHaveTextContent(/prototype’s email service may be unavailable/i);
  expect(screen.getByRole("alertdialog")).toHaveTextContent(/please try again later/i);
  expect(screen.getByRole("alertdialog")).not.toHaveTextContent(/24 hours/i);
  expect(screen.getByRole("heading", { name: /account created/i })).toBeInTheDocument();
});
