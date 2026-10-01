import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import goldenJsonl from "../../../eval/golden.jsonl?raw";
import { App } from "../App";
import type { AskResponse } from "../api/types";
import { STARTERS } from "../components/chat/StarterQuestions";
import { json, noContent, sse, sseEvent, stubApi } from "./fakeApi";
import { ANSWER, RECEIPT, REQUEST_ID, shellRoutes } from "./fixtures";

const HAPPY_PATH = ["screen", "route", "retrieve", "answer", "validate", "finish"];
const FLAG_PATH = `/requests/${REQUEST_ID}/flag`;

function answerStream() {
    return sse(
        ": ping\n\n",
        ...HAPPY_PATH.map((node) => sseEvent("node", { node })),
        sseEvent("answer", ANSWER),
    );
}

async function ask(question: string) {
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Question"), question);
    await user.click(screen.getByRole("button", { name: "Ask" }));
    return user;
}

test("asking streams the graph steps, then shows the answer and its citation", async () => {
    const calls = stubApi([
        ...shellRoutes(),
        { method: "POST", path: "/ask/stream", respond: answerStream },
    ]);
    render(<App />);

    await ask("How many inputs does the eZNT-T331 have?");

    expect(await screen.findByText(ANSWER.answer)).toBeInTheDocument();
    const steps = within(screen.getByRole("list", { name: "Graph steps" }));
    expect(
        steps.getAllByRole("listitem").map((item) => item.textContent?.replace("→", "")),
    ).toEqual(HAPPY_PATH);
    const sources = within(screen.getByRole("region", { name: "Sources" }));
    const link = sources.getByRole("link", { name: /eZNT-T331 Catalog Sheet/ });
    expect(link).toHaveAttribute("href", "https://example.com/docs/eznt-t331.pdf#page=2");
    expect(link).toHaveAttribute("target", "_blank");
    expect(sources.getByText("p. 2")).toBeInTheDocument();
    expect(calls.find((call) => call.path === "/ask/stream")?.body).toEqual({
        question: "How many inputs does the eZNT-T331 have?",
        thread_id: null,
    });
});

test("a follow-up question sends the thread id from the first answer", async () => {
    const calls = stubApi([
        ...shellRoutes(),
        { method: "POST", path: "/ask/stream", respond: answerStream },
    ]);
    render(<App />);

    const user = await ask("First question");
    await screen.findByText(ANSWER.answer);
    await user.type(screen.getByLabelText("Question"), "And the outputs?{Enter}");
    await screen.findAllByText(ANSWER.answer);

    const asks = calls.filter((call) => call.path === "/ask/stream");
    expect(asks[1]?.body).toEqual({ question: "And the outputs?", thread_id: ANSWER.thread_id });
});

test("a stream that closes without an answer shows a generic error", async () => {
    stubApi([
        ...shellRoutes(),
        {
            method: "POST",
            path: "/ask/stream",
            respond: () => sse(sseEvent("node", { node: "screen" })),
        },
    ]);
    render(<App />);

    await ask("Anything");

    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
});

test("Show cost fetches the receipt and shows the cost and the model", async () => {
    const calls = stubApi([
        ...shellRoutes(),
        { method: "POST", path: "/ask/stream", respond: answerStream },
        { method: "GET", path: `/requests/${REQUEST_ID}/receipt`, respond: () => json(RECEIPT) },
    ]);
    render(<App />);
    const user = await ask("How many inputs does the eZNT-T331 have?");
    await screen.findByText(ANSWER.answer);

    await user.click(screen.getByRole("button", { name: "Show cost" }));

    const receipt = within(await screen.findByRole("region", { name: "Cost receipt" }));
    expect(await receipt.findByText("$0.000313", { selector: "dd" })).toBeInTheDocument();
    expect(receipt.getByText("gpt-4o-mini", { selector: "dd" })).toBeInTheDocument();
    expect(calls.filter((call) => call.path.endsWith("/receipt"))).toHaveLength(1);
});

test("a stream that fails while being read shows a generic error", async () => {
    const broken = new ReadableStream<Uint8Array>({
        start(controller) {
            controller.error(new TypeError("network connection was lost"));
        },
    });
    stubApi([
        ...shellRoutes(),
        { method: "POST", path: "/ask/stream", respond: () => new Response(broken) },
    ]);
    render(<App />);

    await ask("Anything");

    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
});

test("an error event on the stream shows its message", async () => {
    const limit = { reason: "model_unavailable", message: "Models are down.", resets_at: null };
    stubApi([
        ...shellRoutes(),
        { method: "POST", path: "/ask/stream", respond: () => sse(sseEvent("error", limit)) },
    ]);
    render(<App />);

    await ask("Anything");

    expect(await screen.findByRole("alert")).toHaveTextContent("Models are down.");
});

test("an answer has no used-as-is, used-with-edits or not-used buttons", async () => {
    stubApi([...shellRoutes(), { method: "POST", path: "/ask/stream", respond: answerStream }]);
    render(<App />);

    await ask("How many inputs does the eZNT-T331 have?");

    expect(await screen.findByText(ANSWER.answer)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /used/i })).not.toBeInTheDocument();
});

test("flagging an answer sends the trimmed reason and shows it flagged", async () => {
    const calls = stubApi([
        ...shellRoutes(),
        { method: "POST", path: "/ask/stream", respond: answerStream },
        { method: "POST", path: FLAG_PATH, respond: noContent },
    ]);
    render(<App />);
    const user = await ask("How many inputs does the eZNT-T331 have?");
    await screen.findByText(ANSWER.answer);

    await user.click(screen.getByRole("button", { name: "Flag as wrong" }));
    await user.type(screen.getByLabelText("What is wrong with this answer?"), "  Wrong page  ");
    await user.click(screen.getByRole("button", { name: "Submit flag" }));

    expect(await screen.findByText("Flagged")).toBeInTheDocument();
    const flag = calls.find((call) => call.path === FLAG_PATH);
    expect(flag?.method).toBe("POST");
    expect(flag?.body).toEqual({ reason: "Wrong page" });
});

const TICKET_QUESTION = "The eBM-800 will not power up, please open a ticket.";

function answerWith(response: AskResponse) {
    stubApi([
        ...shellRoutes(),
        { method: "POST", path: "/ask/stream", respond: () => sse(sseEvent("answer", response)) },
    ]);
    render(<App />);
}

const PAUSED: AskResponse = {
    ...ANSWER,
    decision: "paused",
    approval_required: true,
    ticket_id: "f70ea70e-95e5-47ac-9906-2265a87aac31",
};

test("a turn that drafts a ticket shows the answer flagged for follow-up, no ticket controls", async () => {
    answerWith(PAUSED);

    await ask(TICKET_QUESTION);

    expect(await screen.findByText("Flagged for follow-up")).toBeInTheDocument();
    expect(screen.getByText(ANSWER.answer)).toBeInTheDocument();
    expect(screen.getByText("answered")).toBeInTheDocument();
    expect(screen.queryByText("paused")).not.toBeInTheDocument();
    expect(screen.queryByText(/Ticket proposed/)).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /approvals/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
});

test("the chat's path leaves out the ticket steps", async () => {
    const path = ["screen", "route", "retrieve", "answer", "validate", "propose_ticket"];
    stubApi([
        ...shellRoutes(),
        {
            method: "POST",
            path: "/ask/stream",
            respond: () =>
                sse(...path.map((node) => sseEvent("node", { node })), sseEvent("answer", PAUSED)),
        },
    ]);
    render(<App />);

    await ask(TICKET_QUESTION);

    await screen.findByText("Flagged for follow-up");
    const steps = within(screen.getByRole("list", { name: "Graph steps" }));
    expect(
        steps.getAllByRole("listitem").map((item) => item.textContent?.replace("→", "")),
    ).toEqual(["screen", "route", "retrieve", "answer", "validate"]);
});

test("a drafted ticket with no citation shows as abstained", async () => {
    answerWith({
        ...PAUSED,
        answer: "The documentation does not cover this, so I drafted a ticket for an admin to review.",
        citations: [],
    });

    await ask(TICKET_QUESTION);

    expect(await screen.findByText("Flagged for follow-up")).toBeInTheDocument();
    expect(screen.getByText("abstained")).toBeInTheDocument();
});

test("a ticket suggested to a role that cannot file one is flagged, not explained", async () => {
    const note = "A ticket was suggested, but this role cannot create tickets.";
    answerWith({ ...ANSWER, notes: [note] });

    await ask(TICKET_QUESTION);

    expect(await screen.findByText("Flagged for follow-up")).toBeInTheDocument();
    expect(screen.queryByText(note)).not.toBeInTheDocument();
});

type GoldenCase = { question: string; expect: { support?: "answer" | "abstain" } };

test("every starter question is a golden case that support gets an answer to", () => {
    const answerable = goldenJsonl
        .split("\n")
        .filter((line) => line.trim())
        .map((line) => JSON.parse(line) as GoldenCase)
        .filter((golden) => golden.expect.support === "answer")
        .map((golden) => golden.question);

    expect(answerable).toEqual(expect.arrayContaining(STARTERS));
});
