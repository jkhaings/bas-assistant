import type { Page } from "../hooks/useHashRoute";

const TABS: { page: Page; label: string }[] = [
    { page: "chat", label: "Chat" },
    { page: "dashboards", label: "Dashboards" },
    { page: "evals", label: "Evals" },
    { page: "how-i-built-this", label: "How I built this" },
];

export function NavTabs({ current }: { current: Page }) {
    return (
        <nav aria-label="Main">
            <ul className="-mb-px flex gap-1 overflow-x-auto">
                {TABS.map(({ page, label }) => {
                    const active = page === current;
                    const tone = active
                        ? "border-accent text-accent-strong"
                        : "border-transparent text-stone-600 hover:border-stone-300 hover:text-stone-900";
                    return (
                        <li key={page}>
                            <a
                                href={`#/${page}`}
                                aria-current={active ? "page" : undefined}
                                className={`block border-b-2 px-3 py-2 text-sm font-medium whitespace-nowrap ${tone}`}
                            >
                                {label}
                            </a>
                        </li>
                    );
                })}
            </ul>
        </nav>
    );
}
