import { useSyncExternalStore } from "react";

export const PAGES = ["chat", "approvals", "dashboards", "evals", "how-i-built-this"] as const;
export type Page = (typeof PAGES)[number];

function currentPage(): Page {
    const name = window.location.hash.replace(/^#\/?/, "");
    return PAGES.find((page) => page === name) ?? "chat";
}

function subscribe(onChange: () => void): () => void {
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
}

export function useHashRoute(): Page {
    return useSyncExternalStore(subscribe, currentPage);
}
