import { useEffect, useMemo, useReducer, useState } from "react";
import { createApiClient } from "./api/client";
import { ApiContext } from "./api/context";
import type { Role } from "./api/types";
import { chatReducer, initialChatState } from "./chat/threads";
import { BudgetBanner } from "./components/BudgetBanner";
import { Footer } from "./components/Footer";
import { TopBar } from "./components/TopBar";
import { useBudget } from "./hooks/useBudget";
import { useDocumentCount } from "./hooks/useDocumentCount";
import { useHashRoute, type Page } from "./hooks/useHashRoute";
import { ApprovalsPage } from "./pages/ApprovalsPage";
import { ChatPage } from "./pages/ChatPage";
import { DashboardsPage } from "./pages/DashboardsPage";
import { EvalsPage } from "./pages/EvalsPage";
import { HowIBuiltThis } from "./pages/HowIBuiltThis";

type BudgetStop = { resetsAt: string | null };

export function App() {
    const page = useHashRoute();
    const [role, setRole] = useState<Role>("support");
    const [budgetStop, setBudgetStop] = useState<BudgetStop | null>(null);
    const [adminToken, setAdminToken] = useState<string | null>(null);
    const [chat, dispatch] = useReducer(chatReducer, undefined, initialChatState);

    const client = useMemo(
        () => createApiClient({ role, onBudgetReached: (resetsAt) => setBudgetStop({ resetsAt }) }),
        [role],
    );
    const { budget, refresh: refreshBudget } = useBudget(client);
    const documentCount = useDocumentCount(client);

    // A later reading with room left means the daily cap has reset.
    useEffect(() => {
        if (budget && budget.spent_usd < budget.cap_usd) setBudgetStop(null);
    }, [budget]);

    function renderPage(current: Page) {
        switch (current) {
            case "chat":
                return (
                    <ChatPage
                        role={role}
                        chat={chat}
                        dispatch={dispatch}
                        onAskFinished={refreshBudget}
                    />
                );
            case "approvals":
                return (
                    <ApprovalsPage role={role} token={adminToken} onTokenChange={setAdminToken} />
                );
            case "dashboards":
                return <DashboardsPage />;
            case "evals":
                return <EvalsPage />;
            case "how-i-built-this":
                return <HowIBuiltThis />;
        }
    }

    return (
        <ApiContext.Provider value={client}>
            <div className="flex min-h-screen flex-col">
                {budgetStop && <BudgetBanner resetsAt={budgetStop.resetsAt} />}
                <TopBar
                    page={page}
                    role={role}
                    onRoleChange={setRole}
                    budget={budget}
                    documentCount={documentCount}
                />
                <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6">
                    {renderPage(page)}
                </main>
                <Footer />
            </div>
        </ApiContext.Provider>
    );
}
