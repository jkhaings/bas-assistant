import { describe, expect, test } from "vitest";
import { GENERIC_ERROR, NETWORK_ERROR, describeError } from "./errors";

describe("describeError", () => {
    test("shows a string detail as a sentence", () => {
        expect(describeError({ detail: "request not found" })).toBe("Request not found");
    });

    test("joins validation messages with the field they refer to", () => {
        const detail = [
            {
                loc: ["body", "question"],
                msg: "String should have at least 1 character",
                type: "x",
            },
            { loc: ["body"], msg: "Field required", type: "missing" },
        ];
        expect(describeError({ detail })).toBe(
            "Question: String should have at least 1 character; Field required",
        );
    });

    test("shows the message of a wrapped limit object", () => {
        const detail = { reason: "rate_limited", message: "Too many questions.", resets_at: null };
        expect(describeError({ detail })).toBe("Too many questions.");
    });

    test("shows the message of a bare limit object from the stream", () => {
        const error = { reason: "model_unavailable", message: "Models are down.", resets_at: null };
        expect(describeError(error)).toBe("Models are down.");
    });

    test("explains a request that never reached the server", () => {
        expect(describeError(new TypeError("Failed to fetch"))).toBe(NETWORK_ERROR);
    });

    test("falls back to a generic message for anything else", () => {
        expect(describeError("<html>Bad gateway</html>")).toBe(GENERIC_ERROR);
        expect(describeError({ detail: { unexpected: true } })).toBe(GENERIC_ERROR);
    });
});
