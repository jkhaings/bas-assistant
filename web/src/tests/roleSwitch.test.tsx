import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { App } from "../App";
import { stubApi } from "./fakeApi";
import { shellRoutes } from "./fixtures";

test("the main screen asks as support with no role switcher, admin token or Approvals tab", async () => {
    const calls = stubApi(shellRoutes());
    render(<App />);

    expect(await screen.findByText("3 documents visible")).toBeInTheDocument();
    expect(calls.find((call) => call.path === "/documents")?.headers.get("X-Demo-Role")).toBe(
        "support",
    );
    expect(screen.queryByLabelText("View as:")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Admin token")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /approvals|admin/i })).not.toBeInTheDocument();
});

test("viewing as Engineer on #/admin sends the engineer role and updates the documents count", async () => {
    const calls = stubApi(shellRoutes());
    window.location.hash = "#/admin";
    render(<App />);
    expect(await screen.findByText("3 documents visible")).toBeInTheDocument();
    const before = calls.length;

    await userEvent.setup().selectOptions(screen.getByLabelText("View as:"), "engineer");

    expect(await screen.findByText("5 documents visible")).toBeInTheDocument();
    const next = calls[before];
    expect(next?.headers.get("X-Demo-Role")).toBe("engineer");
    const documents = calls.slice(before).find((call) => call.path === "/documents");
    expect(documents?.headers.get("X-Demo-Role")).toBe("engineer");
});
