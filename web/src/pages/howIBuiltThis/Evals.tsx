import { RUN } from "./run";
import { Section } from "./Section";

function EarlierFailures() {
    return (
        <>
            <p>Earlier failures that changed the build:</p>
            <ul className="list-disc space-y-1 pl-6">
                <li>
                    The first reranker took 13 to 20 seconds per question on CPU. It was
                    replaced with a smaller cross-encoder that is loaded at startup.
                </li>
                <li>
                    One evaluation ran against an empty database and abstained on everything,
                    and those abstains stayed cached. The cache key now carries the corpus
                    version.
                </li>
                <li>
                    The router called the refund question off-topic in 3 of 10 runs. An
                    "unclear" scope, which retrieves and abstains instead, made it 0 of 10.
                </li>
            </ul>
        </>
    );
}

export function Evals() {
    return (
        <Section id="evals" title="What the evals and the red team showed">
            <p>
                On the live URL, the golden set passed {RUN.golden}: every answerable question
                cited its expected document, every out-of-scope one abstained, and support never
                got the engineer-only answers. RAGAS, with gpt-4o-mini as the judge, puts
                faithfulness at {RUN.faithfulness} overall. That is the share of an answer's
                claims its passages support.
            </p>
            <p>
                The weak spot is protocol questions, with faithfulness{" "}
                {RUN.protocolFaithfulness}. Sibling products share catalog-sheet sections word
                for word. Asked which BACnet profile the Red5-PLUS-1146 carries, retrieval fills
                the top five with the same one-line section from the Red5 EDGE 1146 and the
                Red5-PLUS-1180 as well.
            </p>
            <p>
                The answer names the right product, because the answer model sees each
                passage's document title. The judge reads only the section text, and that text
                never names the product, so it counts the claim as unsupported. Part of the
                score is the measurement, and part is real crowding.
            </p>
            <p>
                I tried capping each document at two of the five places. It changed nothing,
                because no single document held more than two; the crowding comes from sibling
                documents. The next thing to try is merging identical sections across
                documents, or filtering by the product named in the question.
            </p>
            <EarlierFailures />
            <p>
                The red team passed {RUN.redteam}: a direct injection, instructions planted
                inside a document, a request to embed a tracking image, personal data in a
                question, support asking for a ticket, and an off-topic request. Each case also
                checks that it left an audit row.
            </p>
        </Section>
    );
}
