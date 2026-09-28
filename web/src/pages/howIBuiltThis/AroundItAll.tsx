import { Figure } from "../../components/Figure";
import { RUN } from "./run";
import { Part, Section, Tools } from "./Section";

function CostTracking() {
    return (
        <Section id="cost-tracking" title="Cost tracking">
            <p>
                Every model call in those steps costs money, so I record each one. LiteLLM
                reports each call's price, and the app saves it as one row in a usage table.
                "Show cost" under any answer lists those rows: a simple answer comes to about{" "}
                {RUN.simpleAnswerUsd} and a complex one about {RUN.complexAnswerUsd}. A repeated
                question costs nothing, because Redis, a database that keeps data in memory,
                holds answers already given. A daily cap of {RUN.dailyCapUsd} for the whole demo
                stops new questions with a banner until midnight UTC.
            </p>
            <Figure
                src="/img/grafana-budget.png"
                alt="Grafana Budget dashboard: spend today against the cap, cost per answer, cost by model and stage"
                caption="The Budget dashboard on the Dashboards tab, after the live evaluation run."
            />
            <Tools
                names="LiteLLM, Postgres, Redis, Prometheus, Grafana"
                page={{ href: "#/dashboards", label: "Dashboards" }}
            />
        </Section>
    );
}

function Security() {
    return (
        <Section id="security" title="Security">
            <p>
                Each person has a role, and the role decides which documents they may see. That
                check is part of the database query itself, so a document the role may not see
                can't be retrieved at all. Approving a ticket needs the admin role plus a secret
                token. Every decision, refusals included, adds a row to an audit log. Keys and
                passwords live only in the server's environment, and gitleaks, a secret scanner,
                blocks any commit that contains one.
            </p>
            <Tools
                names="Postgres, pydantic-settings, gitleaks, Caddy for HTTPS"
                code="src/bas_assistant/api/roles.py"
            />
        </Section>
    );
}

function Evaluations() {
    return (
        <Section id="evaluations" title="Evaluations">
            <p>
                Before I wrote any search code, I wrote twenty questions a support desk gets, each
                with the document and page that answers it. This golden set is a fixed test I rerun
                after each change, and the live site passed every check. RAGAS, a library that
                uses a second model as a judge, rates faithfulness, the share of an answer's claims
                its sections support, at {RUN.faithfulness} overall. A red team, a set of
                deliberate attacks such as instructions hidden inside a document, ran{" "}
                {RUN.redteamCases} cases, and all {RUN.redteamCases} were stopped. Staff can rate
                each answer used as-is, with edits or not used; the demo hides those buttons,
                since its visitors aren't staff.
            </p>
            <Tools
                names="pytest, RAGAS with gpt-4o-mini as the judge"
                page={{ href: "#/evals", label: "Evals" }}
            />
        </Section>
    );
}

export function AroundItAll() {
    return (
        <Part id="step-3" title="Step 3: Around all of it">
            <CostTracking />
            <Security />
            <Evaluations />
        </Part>
    );
}
