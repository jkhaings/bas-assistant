import { Section } from "./Section";

export function LangGraph() {
    return (
        <Section id="langgraph" title="Why LangGraph, and what the human gate does">
            <p>
                Each step is a node with typed state. That lets it be traced, tested on its
                own, paused, and resumed after a restart. The model makes two decisions, the
                route and the answer, and everything else is code.
            </p>
            <p>
                When an engineer's question calls for a ticket, the answer includes a draft,
                stored as "proposed". The graph then stops at an interrupt, and its state is
                checkpointed to Postgres. The API response marks the turn as waiting for approval.
            </p>
            <p>
                An admin with the token approves or denies it. The graph resumes and files it:
                here into an internal table, in a company into Jira. A support user cannot
                create a ticket, and only an admin can approve one.
            </p>
            <p>
                The public chat keeps this out of the way. Visitors ask as support by default, and
                when a turn does draft a ticket, the chat shows the answer with a quiet
                "Flagged for follow-up". The roles and the gate are unchanged. They are
                demonstrated on <code className="font-mono text-sm">#/admin</code>, a page
                reached only by its URL, which has the role switcher, the admin token and the
                approve and deny buttons. To see the gate, switch to Engineer there, ask for a
                ticket in Chat, then switch to Admin and approve it.
            </p>
        </Section>
    );
}
