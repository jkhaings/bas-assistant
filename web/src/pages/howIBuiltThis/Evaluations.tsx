import { GoldenTable } from "./GoldenTable";
import { RUN } from "./run";
import { Section, Tools } from "./Section";

const METRICS: [string, string][] = [
    [
        "Faithfulness",
        "does the answer only say things the pieces say? This catches answers that sound right but aren't.",
    ],
    ["Answer relevancy", "does it answer the question that was asked, not a nearby one?"],
    ["Context precision", "were the pieces it found the right ones, or padding?"],
    ["Context recall", "was the piece that held the answer actually found?"],
];

function Subheading({ children }: { children: string }) {
    return <h4 className="pt-2 text-lg font-semibold text-stone-900">{children}</h4>;
}

function GoldenSet() {
    return (
        <>
            <Subheading>The golden set</Subheading>
            <p>
                A golden set is an answer key. It's 20 questions where I wrote down the right
                answer ahead of time, and which document it comes from. Some of the questions are
                on purpose not in the documents, and the right behaviour there is to say "I don't
                know". Every time I change something, I ask them all again and check them against
                the key. That's how I know if a change helped or broke something.
            </p>
            <GoldenTable />
        </>
    );
}

function Judge() {
    return (
        <>
            <Subheading>LLM as a judge</Subheading>
            <p>
                Checking 22 answers by hand after every change is slow, so I use a second model as
                a judge. The judge doesn't get the internet. It only sees four things: the
                question, the answer the assistant gave, the document pieces the assistant used,
                and the right answer from my key. Then it scores four things from 0 to 1:
            </p>
            <ul className="list-disc space-y-1 pl-6">
                {METRICS.map(([name, meaning]) => (
                    <li key={name}>
                        <span className="font-medium text-stone-900">{name}</span> — {meaning}
                    </li>
                ))}
            </ul>
            <p>
                The judge is gpt-4o-mini, run with a tool called RAGAS. One run costs about{" "}
                {RUN.evalAnswersUsd} for the answers and {RUN.evalJudgeUsd} for the judge.
            </p>
            <p>
                A judge can only judge what it sees. The protocol score is{" "}
                {RUN.protocolFaithfulness} because sibling products have near-identical sections,
                and the judge reads pieces without their document title, so it can't tell which
                product a piece belongs to. Part of that number is a measuring problem, and I say
                so instead of hiding it.
            </p>
        </>
    );
}

export function Evaluations() {
    return (
        <Section id="evaluations" title="Evaluations">
            <GoldenSet />
            <Judge />
            <p>
                A red team, a set of deliberate attacks such as instructions hidden inside a
                document, ran {RUN.redteamCases} cases, and all {RUN.redteamCases} were stopped.
                Staff can rate each answer used as-is, with edits or not used; the demo hides those
                buttons, since its visitors aren't staff.
            </p>
            <Tools
                names="pytest, RAGAS with gpt-4o-mini as the judge"
                page={{ href: "#/evals", label: "Evals" }}
            />
        </Section>
    );
}
