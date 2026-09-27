import { RUN } from "./run";
import { Section } from "./Section";

export function TwentyQuestions() {
    return (
        <Section id="twenty-questions" title="The twenty questions">
            <p>
                Before writing any retrieval code, I wrote twenty questions a desk would
                plausibly get, each with the document and page that answers it. They fall into
                seven groups:
            </p>
            <ul className="list-disc space-y-1 pl-6">
                <li>Spec, ordering, wiring and power, protocol, and compatibility questions.</li>
                <li>
                    Three that no document answers and so must abstain: a refund policy, a
                    password reset on a login-gated portal, and another vendor's thermostat.
                </li>
                <li>
                    Two that only engineers may see answered. They are asked as support and as
                    engineer, which makes 22 checks.
                </li>
            </ul>
            <p>
                That is the golden set, and every evaluation run asks all of it. The corpus is{" "}
                {RUN.documents} public documents ({RUN.pdfs} catalog PDFs and {RUN.pages}{" "}
                product pages): {RUN.sections} sections and {RUN.chunks} searchable chunks.
            </p>
        </Section>
    );
}
