import { Cost } from "./howIBuiltThis/Cost";
import { Evals } from "./howIBuiltThis/Evals";
import { InsideACompany } from "./howIBuiltThis/InsideACompany";
import { Problem } from "./howIBuiltThis/Problem";
import { RequestPath } from "./howIBuiltThis/RequestPath";
import { TwentyQuestions } from "./howIBuiltThis/TwentyQuestions";
import { Weaknesses } from "./howIBuiltThis/Weaknesses";

export function HowIBuiltThis() {
    return (
        <article className="mx-auto max-w-3xl space-y-12 pb-8 text-base leading-relaxed text-stone-800">
            <header className="space-y-3">
                <h1 className="text-3xl font-semibold tracking-tight text-stone-900">
                    How I built this
                </h1>
                <p className="text-lg text-stone-600">
                    A support assistant that answers only from public product documentation, cites
                    the page, abstains when the documents are silent, and never files a ticket
                    without a person saying yes.
                </p>
            </header>
            <Problem />
            <TwentyQuestions />
            <RequestPath />
            <Cost />
            <Evals />
            <InsideACompany />
            <Weaknesses />
            <footer className="border-t border-stone-200 pt-6">
                <p>
                    The code is on{" "}
                    <a
                        href="https://github.com/jkhaings/bas-assistant"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-accent hover:underline"
                    >
                        github.com/jkhaings/bas-assistant
                    </a>
                    .
                </p>
            </footer>
        </article>
    );
}
