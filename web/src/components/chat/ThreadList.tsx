import type { ChatThread } from "../../chat/threads";

type Props = {
    threads: ChatThread[];
    activeKey: string;
    onSelect: (key: string) => void;
    onNew: () => void;
};

function threadTitle(thread: ChatThread): string {
    return thread.exchanges[0]?.question ?? "Empty thread";
}

export function ThreadList({ threads, activeKey, onSelect, onNew }: Props) {
    return (
        <nav aria-label="Threads" className="space-y-3">
            <div className="flex items-center justify-between gap-2">
                <h2 className="text-sm font-semibold text-stone-700">Threads</h2>
                <button
                    type="button"
                    onClick={onNew}
                    className="rounded-md border border-stone-300 bg-white px-2.5 py-1 text-sm font-medium hover:bg-stone-100"
                >
                    New thread
                </button>
            </div>
            <ul className="space-y-1">
                {threads.map((thread) => {
                    const active = thread.key === activeKey;
                    const tone = active
                        ? "bg-accent-soft text-accent-strong font-medium"
                        : "text-stone-700 hover:bg-stone-100";
                    return (
                        <li key={thread.key}>
                            <button
                                type="button"
                                aria-current={active ? "true" : undefined}
                                onClick={() => onSelect(thread.key)}
                                className={`block w-full truncate rounded-md px-3 py-2 text-left text-sm ${tone}`}
                            >
                                {threadTitle(thread)}
                            </button>
                        </li>
                    );
                })}
            </ul>
            <p className="text-xs text-stone-500">
                Threads live in this tab only, one list per role.
            </p>
        </nav>
    );
}
