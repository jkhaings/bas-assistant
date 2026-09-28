import type { components } from "./schema";

type Schemas = components["schemas"];

export type AskResponse = Schemas["bas_assistant__agent__turn__AskResponse"];
export type Citation = Schemas["bas_assistant__agent__turn__Citation"];
export type Decision = AskResponse["decision"];
export type Receipt = Schemas["Receipt"];
export type Ticket = Schemas["TicketOut"];
export type Budget = Schemas["BudgetOut"];
export type EvalRun = Schemas["EvalRunOut"];
export type FeedbackValue = Schemas["FeedbackBody"]["value"];

export const ROLES = ["support", "engineer", "admin"] as const;
export type Role = (typeof ROLES)[number];

export const LIMIT_REASONS = [
    "rate_limited",
    "daily_allowance_used",
    "daily_budget_reached",
    "key_budget_reached",
    "model_unavailable",
] as const;
export type LimitReason = (typeof LIMIT_REASONS)[number];

export type LimitDetail = {
    reason: LimitReason;
    message: string;
    resets_at: string | null;
};
