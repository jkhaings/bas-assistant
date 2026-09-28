// TODO(post-weekend): these tests stub fetch; there is no browser end-to-end test in CI
// (HANDOFF_E.md, Known gaps).
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    window.location.hash = "";
});
