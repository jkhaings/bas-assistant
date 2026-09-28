import { useState, type KeyboardEvent } from "react";

type FieldProps = { value: string; onChange: (text: string) => void; onEnter: () => void };

function QuestionField({ value, onChange, onEnter }: FieldProps) {
    function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
        if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
        event.preventDefault();
        onEnter();
    }

    return (
        <>
            <label htmlFor="question" className="sr-only">
                Question
            </label>
            <textarea
                id="question"
                value={value}
                onChange={(event) => onChange(event.target.value)}
                onKeyDown={onKeyDown}
                maxLength={2000}
                rows={3}
                placeholder="Ask a product question: specs, wiring, protocols, compatibility"
                className="block w-full resize-y border-0 bg-transparent px-2 py-1 text-sm focus:outline-none"
            />
        </>
    );
}

type Props = { busy: boolean; onAsk: (question: string) => void };

export function Composer({ busy, onAsk }: Props) {
    const [text, setText] = useState("");
    const question = text.trim();

    function submit() {
        if (!question || busy) return;
        onAsk(question);
        setText("");
    }

    return (
        <form
            onSubmit={(event) => {
                event.preventDefault();
                submit();
            }}
            className="rounded-lg border border-stone-300 bg-white p-2 shadow-sm focus-within:border-accent"
        >
            <QuestionField value={text} onChange={setText} onEnter={submit} />
            <div className="flex items-center justify-between gap-2 px-2 pt-1">
                <span className="text-xs text-stone-500">
                    Enter to ask, Shift+Enter for a new line
                </span>
                <button
                    type="submit"
                    disabled={busy || !question}
                    className="rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {busy ? "Working" : "Ask"}
                </button>
            </div>
        </form>
    );
}
