import { Figure } from "../../components/Figure";
import { Part, Section, Tools } from "./Section";

function Guardrails() {
    return (
        <Section id="guardrails" title="Guardrails">
            <p>
                When someone presses Ask, the question first meets the guardrails: checks written
                as code, so they don't depend on a model behaving. Presidio, a tool that spots
                personal data, swaps names, places, emails, phone numbers and street addresses
                for placeholders before anything is stored or sent. A pattern check then looks
                for prompt injection, which is text trying to override the assistant's
                instructions. Each IP address, roughly each visitor, can ask at most 20 questions
                a minute, so one person can't run up the bill. A question that gets through goes
                to the router.
            </p>
            <Tools
                names="Presidio with spaCy's en_core_web_sm model, Redis for the rate limit"
                code="src/bas_assistant/guardrails/"
            />
        </Section>
    );
}

function Routing() {
    return (
        <Section id="routing" title="Routing">
            <p>
                The router is one cheap model call that sorts the question before any real work
                starts. It marks the question simple or complex, so only complex ones reach the
                stronger, pricier model. It checks that the question is about building automation
                at all, and an off-topic request is refused. It also flags prompt injection the
                pattern check missed, at no extra cost, since it rides on the same call. Every
                model call goes through LiteLLM, a middle layer that gives models short names and
                swaps in a backup if one is down.
            </p>
            <Tools
                names="LiteLLM, gpt-4o-mini as fast with Gemini 3.8 Flash as its backup, Claude Sonnet 4.6 as strong with GPT-4o as its backup"
                code="src/bas_assistant/llm/router.py"
            />
        </Section>
    );
}

function Search() {
    return (
        <Section id="search" title="Search">
            <p>
                An on-topic question is turned into an embedding too, and search runs two ways in
                one database query. Vector search finds chunks close in meaning, and keyword search
                finds chunks with the same words, such as a model number. Both only see documents
                the asker's role is allowed to read, because that rule is part of the query. A
                reranker, a small model that reads the question and a chunk side by side, rescores
                the top 20 and keeps the best five sections. If even the best score is too
                low, the assistant says it couldn't find the answer, and no answer model is called.
            </p>
            <Tools
                names="Postgres full-text search and pgvector through SQLAlchemy, sentence-transformers running the cross-encoder/ms-marco-MiniLM-L-6-v2 reranker on the server's CPU"
                code="src/bas_assistant/retrieval/"
            />
        </Section>
    );
}

function Orchestration() {
    return (
        <Section id="orchestration" title="Orchestration">
            <p>
                Orchestration is the part that runs these steps in order and decides what happens
                next. I use LangGraph, which treats each step as a node in a graph, so each one
                can be traced and tested on its own. After search, the answer model writes a reply
                from the five sections only and names the ones it used. A validator, code rather
                than a model, checks that every citation is one of those five, and blocks the
                reply after one failed retry. If an engineer's question calls for a ticket,
                the graph pauses and saves its state in Postgres until an admin approves or denies
                it.
            </p>
            <Figure
                src="/img/chat-answer.png"
                alt="A live answer: the node path, the answer, two Red5-PLUS-1180 citation cards (pages 1 and 2) and the cost receipt"
                caption="A live answer, its two sources, and its receipt: three model calls, $0.00035."
            />
            <Tools
                names="LangGraph with its Postgres checkpointer, FastAPI streaming each finished step to the page"
                code="src/bas_assistant/agent/graph.py"
            />
        </Section>
    );
}

export function AQuestionArrives() {
    return (
        <Part id="step-2" title="Step 2: A question arrives">
            <Guardrails />
            <Routing />
            <Search />
            <Orchestration />
        </Part>
    );
}
