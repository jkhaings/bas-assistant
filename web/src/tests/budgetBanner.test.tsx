import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { App } from "../App";
import { json, stubApi } from "./fakeApi";
import { shellRoutes } from "./fixtures";

const RESETS_AT = "2026-09-28T00:00:00+00:00";
const BUDGET_REACHED = {
    detail: {
        reason: "daily_budget_reached",
        message: "The demo has reached today's spending cap and is paused.",
        resets_at: RESETS_AT,
    },
};

test("a daily budget stop on ask shows the budget banner", async () => {
    stubApi([
        {
            method: "GET",
            path: "/budget",
            respond: () => json({ spent_usd: 3.01, cap_usd: 3, resets_at: RESETS_AT }),
        },
        ...shellRoutes(),
        { method: "POST", path: "/ask/stream", respond: () => json(BUDGET_REACHED, 503) },
    ]);
    render(<App />);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("Question"), "What is the power draw?");
    await user.click(screen.getByRole("button", { name: "Ask" }));

    const resetTime = new Date(RESETS_AT).toLocaleTimeString(undefined, {
        hour: "numeric",
        minute: "2-digit",
        timeZoneName: "short",
    });
    expect(
        await screen.findByText(`The demo's daily budget is used up. It resets at ${resetTime}.`),
    ).toBeInTheDocument();
    expect(screen.getByText(BUDGET_REACHED.detail.message)).toBeInTheDocument();
});
