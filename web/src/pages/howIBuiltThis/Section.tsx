import type { ReactNode } from "react";

type SectionProps = { id: string; title: string; children: ReactNode };

export function Section({ id, title, children }: SectionProps) {
    return (
        <section aria-labelledby={id} className="space-y-4">
            <h2 id={id} className="text-2xl font-semibold tracking-tight text-stone-900">
                {title}
            </h2>
            {children}
        </section>
    );
}

export function Steps({ items }: { items: [string, string][] }) {
    return (
        <ol className="list-decimal space-y-2 pl-6">
            {items.map(([name, what]) => (
                <li key={name}>
                    <span className="font-medium text-stone-900">{name}</span>: {what}
                </li>
            ))}
        </ol>
    );
}
