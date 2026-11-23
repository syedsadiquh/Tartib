import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import TodayPage from "./page";

describe("Today placeholder", () => {
  it("renders the screen heading", () => {
    render(<TodayPage />);

    expect(screen.getByRole("heading", { name: "Today" })).toBeInTheDocument();
  });
});
