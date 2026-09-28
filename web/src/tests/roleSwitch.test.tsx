import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { App } from "../App";
import { stubApi } from "./fakeApi";
import { shellRoutes } from "./fixtures";

test("viewing as Engineer sends the engineer role and updates the documents count", async () => {
    const calls = stubApi(shellRoutes());
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
