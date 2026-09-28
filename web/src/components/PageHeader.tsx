import type { ReactNode } from "react";

type Props = { title: string; children?: ReactNode; actions?: ReactNode };

export function PageHeader({ title, children, actions }: Props) {
    return (
        <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-3xl space-y-1">
                <h1 className="text-xl font-semibold tracking-tight text-stone-900">{title}</h1>
                {children && <div className="text-sm text-stone-600">{children}</div>}
            </div>
            {actions}
        </div>
    );
}
