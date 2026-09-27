import { RUN } from "./run";
import { Section } from "./Section";

export function Weaknesses() {
    return (
        <Section id="weaknesses" title="What it does badly">
            <ul className="list-disc space-y-2 pl-6">
                <li>
                    Protocol questions, as above: near-identical sections from sibling products
                    blur which passage supports the answer.
                </li>
                <li>
                    Latency. The reranker runs on the CPU of a two-core server, so the p95 for
                    an answer is about {RUN.p95Seconds} seconds.
                </li>
                <li>
                    With no login, everyone who picks a role shares that role's daily allowance
                    of 50 questions. The per-visitor control is the rate limit.
                </li>
                <li>
                    The name detector is a small model: it misses some names and most bare city
                    names.
                </li>
                <li>
                    The corpus is catalog sheets and product pages only. There are no manuals
                    or help-center articles.
                </li>
                <li>
                    Prompt caching is configured but inactive, because the system prompt is
                    shorter than the provider's minimum.
                </li>
            </ul>
        </Section>
    );
}
