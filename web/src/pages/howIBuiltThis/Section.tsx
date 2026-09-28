import type { ReactNode } from "react";

// GitHub redirects a blob URL for a directory to its tree view, so one base serves both.
const REPO_BLOB = "https://github.com/jkhaings/bas-assistant/blob/main/";

type HeadingProps = { id: string; title: string; children: ReactNode };

export function Part({ id, title, children }: HeadingProps) {
    return (
        <section aria-labelledby={id} className="space-y-10">
            <h2 id={id} className="text-2xl font-semibold tracking-tight text-stone-900">
                {title}
            </h2>
            {children}
        </section>
    );
}

export function Section({ id, title, children }: HeadingProps) {
    return (
        <section aria-labelledby={id} className="space-y-3">
            <h3 id={id} className="text-xl font-semibold tracking-tight text-stone-900">
                {title}
            </h3>
            {children}
        </section>
    );
}

type ToolsProps = { names: string; code?: string; page?: { href: string; label: string } };

export function Tools({ names, code, page }: ToolsProps) {
    return (
        <p className="text-sm text-stone-600">
            <span className="font-medium text-stone-900">Tools:</span> {names}.
            {code && (
                <>
                    {" "}
                    Code:{" "}
                    <a
                        href={`${REPO_BLOB}${code}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-mono text-accent hover:underline"
                    >
                        {code}
                    </a>
                </>
            )}
            {page && (
                <>
                    {" "}
                    See it:{" "}
                    <a href={page.href} className="font-medium text-accent hover:underline">
                        {page.label}
                    </a>
                </>
            )}
        </p>
    );
}
