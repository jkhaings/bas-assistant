import { Section, Steps } from "./Section";

const REQUEST_STEPS: [string, string][] = [
    [
        "Screen",
        "code checks for instruction-override phrasing before any model sees the question",
    ],
    [
        "Route",
        "a small model says whether the question is simple or complex, and whether it is about building automation at all",
    ],
    [
        "Retrieve",
        "vector and keyword search run in one SQL query, filtered to the role's documents, then fused and reranked by a local cross-encoder. The five best sections go forward, and if even the best is weak, the assistant abstains without calling the answer model.",
    ],
    [
        "Answer",
        "the model reads the five passages as data, never as instructions, and returns JSON with the ids of the passages it used",
    ],
    [
        "Validate",
        "code checks that every citation is a passage it was given, and that there are no links outside the documents, no images, and no personal data the passages don't contain. It allows one retry, then fails closed.",
    ],
];

export function RequestPath() {
    return (
        <Section id="request-path" title="The request path and the four fences">
            <p>What happens between pressing Ask and seeing a cited answer:</p>
            <Steps items={REQUEST_STEPS} />
            <p>
                The four fences are input, retrieval, output and action:
            </p>
            <ul className="list-disc space-y-1 pl-6">
                <li>
                    <span className="font-medium text-stone-900">Input</span>: names, emails
                    and phone numbers are redacted before anything is stored or sent, and
                    requests are rate-limited per visitor.
                </li>
                <li>
                    <span className="font-medium text-stone-900">Retrieval</span>: the role's
                    access groups are part of the SQL.
                </li>
                <li>
                    <span className="font-medium text-stone-900">Output</span>: the validator.
                </li>
                <li>
                    <span className="font-medium text-stone-900">Action</span>: the human gate.
                </li>
            </ul>
            <p>Every decision writes an audit row, refusals included.</p>
        </Section>
    );
}
