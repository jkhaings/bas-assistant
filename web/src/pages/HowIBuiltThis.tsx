import { AQuestionArrives } from "./howIBuiltThis/AQuestionArrives";
import { AroundItAll } from "./howIBuiltThis/AroundItAll";
import { BeforeAQuestion } from "./howIBuiltThis/BeforeAQuestion";
import { KnownProblems } from "./howIBuiltThis/KnownProblems";

export function HowIBuiltThis() {
    return (
        <article className="mx-auto max-w-3xl space-y-12 pb-8 text-base leading-relaxed text-stone-800">
            <header className="space-y-3">
                <h1 className="text-3xl font-semibold tracking-tight text-stone-900">
                    How I built this
                </h1>
                <p className="text-lg text-stone-600">
                    I built a support assistant for a building-automation company's help desk. It
                    answers product questions only from the company's public documents, shows the
                    page it used, and says so when the documents don't cover a question. This page
                    follows the system in the order things happen.
                </p>
            </header>
            <BeforeAQuestion />
            <AQuestionArrives />
            <AroundItAll />
            <KnownProblems />
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
