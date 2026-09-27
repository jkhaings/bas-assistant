import type { Exchange } from "../../chat/threads";
import { AnswerView } from "./AnswerView";
import { NodeSteps } from "./NodeSteps";

export function ExchangeView({ exchange }: { exchange: Exchange }) {
    const running = !exchange.response && !exchange.error;
    return (
        <article className="space-y-3">
            <div className="rounded-lg bg-stone-200/60 px-4 py-3">
                <p className="text-xs font-medium text-stone-500">Question</p>
                <p className="whitespace-pre-wrap text-stone-900">{exchange.question}</p>
            </div>
            <NodeSteps steps={exchange.steps} running={running} />
            {exchange.error && (
                <p
                    role="alert"
                    className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"
                >
                    {exchange.error}
                </p>
            )}
            {exchange.response && <AnswerView response={exchange.response} />}
        </article>
    );
}
