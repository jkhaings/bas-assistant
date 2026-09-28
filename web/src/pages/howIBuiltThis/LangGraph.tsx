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
                checkpointed to Postgres. The response says a ticket is waiting.
            </p>
            <p>
                An admin with the token approves or denies it on the Approvals tab. The graph
                resumes and files it: here into an internal table, in a company into Jira. A
                support user cannot create a ticket, and only an admin can approve one.
            </p>
        </Section>
    );
}
