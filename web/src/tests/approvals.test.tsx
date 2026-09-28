import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { App } from "../App";
import { json, stubApi } from "./fakeApi";
import { PROPOSED_TICKET, shellRoutes } from "./fixtures";

const TOKEN = "test-admin-token";

function ticketRoutes() {
    return [
        ...shellRoutes(),
        {
            method: "GET",
            path: "/tickets",
            respond: (request: Request) =>
                request.headers.get("x-admin-token") === TOKEN
                    ? json([PROPOSED_TICKET])
                    : json({ detail: "admin token required" }, 401),
        },
        {
            method: "POST",
            path: "/approve",
            respond: () =>
                json({
                    thread_id: PROPOSED_TICKET.thread_id,
                    ticket_id: PROPOSED_TICKET.id,
                    status: "filed",
                }),
        },
    ];
}

async function openAdminPageAsAdmin(token: string) {
    window.location.hash = "#/admin";
    render(<App />);
    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("View as:"), "admin");
    await user.type(screen.getByLabelText("Admin token"), token);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    return user;
}

test("an admin with a token approves a proposed ticket and sees it filed", async () => {
    const calls = stubApi(ticketRoutes());
    const user = await openAdminPageAsAdmin(TOKEN);

    expect(await screen.findByText(PROPOSED_TICKET.draft.title)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Approve" }));

    expect(await screen.findByText("filed")).toBeInTheDocument();
    const approve = calls.find((call) => call.path === "/approve");
    expect(approve?.headers.get("X-Admin-Token")).toBe(TOKEN);
    expect(approve?.headers.get("X-Demo-Role")).toBe("admin");
    expect(approve?.body).toEqual({ thread_id: PROPOSED_TICKET.thread_id, approve: true });
});

test("a rejected token is cleared and the admin is asked again", async () => {
    stubApi(ticketRoutes());
    await openAdminPageAsAdmin("wrong-token");

    expect(await screen.findByRole("alert")).toHaveTextContent("That token was rejected.");
    expect(screen.getByLabelText("Admin token")).toHaveValue("");
});

test("roles other than admin are told to switch", async () => {
    stubApi(shellRoutes());
    window.location.hash = "#/admin";
    render(<App />);

    expect(await screen.findByText("Switch to Admin to review tickets.")).toBeInTheDocument();
});
