import { useEffect, useMemo, useState } from "react";
import { createApiClient, type ApiClient } from "../api/client";
import type { Budget, Role } from "../api/types";
import { useBudget } from "./useBudget";

type BudgetStop = { resetsAt: string | null };

type BudgetedClient = {
    client: ApiClient;
    budget: Budget | null;
    refreshBudget: () => void;
    budgetStop: BudgetStop | null;
};

// The client reports a daily budget stop; the budget poll is what lifts it.
export function useBudgetedClient(role: Role): BudgetedClient {
    const [budgetStop, setBudgetStop] = useState<BudgetStop | null>(null);
    const client = useMemo(
        () => createApiClient({ role, onBudgetReached: (resetsAt) => setBudgetStop({ resetsAt }) }),
        [role],
    );
    const { budget, refresh } = useBudget(client);

    // A later reading with room left means the daily cap has reset.
    useEffect(() => {
        if (budget && budget.spent_usd < budget.cap_usd) setBudgetStop(null);
    }, [budget]);

    return { client, budget, refreshBudget: refresh, budgetStop };
}
