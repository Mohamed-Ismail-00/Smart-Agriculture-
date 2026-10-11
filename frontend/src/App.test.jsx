import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

describe("App", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("renders the login page for visitors", async () => {
    render(<App />);

    expect(await screen.findByRole("heading", { name: /welcome back/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("redirects protected pages back to login when there is no token", async () => {
    window.history.pushState({}, "", "/dashboard");

    render(<App />);

    expect(await screen.findByRole("heading", { name: /welcome back/i })).toBeInTheDocument();
  });

  it("loads the protected app shell when a saved token is valid", async () => {
    localStorage.setItem("agri_token", "test-token");
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        status: "success",
        data: {
          user_id: 1,
          email: "omar@example.com",
          role: "viewer",
          is_active: true,
        },
      }),
    });

    window.history.pushState({}, "", "/dashboard");
    render(<App />);

    expect(await screen.findByText("AgriData Egypt")).toBeInTheDocument();
    expect(screen.getAllByText("Dashboard").length).toBeGreaterThan(0);
    expect(screen.getByText("omar@example.com")).toBeInTheDocument();
  });
});
