import { fireEvent, render, screen } from "@testing-library/react";
import VerifyEmail from "./VerifyEmail";
import { verifyEmail } from "../api/auth";
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

jest.mock("../api/auth", () => ({
  verifyEmail: jest.fn(),
}));

jest.mock("../api", () => ({
  __esModule: true,
  default: { post: jest.fn() },
}));

beforeEach(() => {
  jest.clearAllMocks();
});

test("renders the matching themed success state after verifying the email", async () => {
  verifyEmail.mockResolvedValue({});

  render(<VerifyEmail theme="dark" />);

  expect(screen.getByRole("main")).toHaveClass("auth-page", "dark-theme");
  expect(await screen.findByRole("heading", { name: /email verified/i })).toBeInTheDocument();
  expect(verifyEmail).toHaveBeenCalledWith("test-uid", "test-token");
  expect(screen.getByRole("button", { name: /go to sign in/i })).toBeInTheDocument();
});

test("shows a resend action when verification fails", async () => {
  verifyEmail.mockRejectedValue({
    response: { data: { error: "Expired link" } },
  });
  api.post.mockResolvedValue({ data: { message: "A new link was sent." } });

  render(<VerifyEmail />);

  expect(await screen.findByRole("heading", { name: /couldn’t verify your email/i })).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("Expired link");
  fireEvent.click(screen.getByRole("button", { name: /resend verification email/i }));

  expect(await screen.findByRole("status")).toHaveTextContent("A new link was sent.");
  expect(api.post).toHaveBeenCalledWith("/api/auth/resend-verification/");
});
