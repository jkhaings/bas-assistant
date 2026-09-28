import { useReducer, useState, type Dispatch } from "react";
import { ApiContext } from "./api/context";
import type { Role } from "./api/types";
import { chatReducer, initialChatState, type ChatAction, type ChatState } from "./chat/threads";
import { BudgetBanner } from "./components/BudgetBanner";
import { Footer } from "./components/Footer";
import { TopBar } from "./components/TopBar";
import { useBudgetedClient } from "./hooks/useBudgetedClient";
import { useDocumentCount } from "./hooks/useDocumentCount";
import { useHashRoute, type Page } from "./hooks/useHashRoute";
import { AdminPage } from "./pages/AdminPage";
import { ChatPage } from "./pages/ChatPage";
import { DashboardsPage } from "./pages/DashboardsPage";
import { EvalsPage } from "./pages/EvalsPage";
import { HowIBuiltThis } from "./pages/HowIBuiltThis";

// The role, chat threads and admin token live above the pages so switching pages keeps them,
// and the role picked on #/admin applies to Chat.
type CurrentPageProps = {
    page: Page;
    role: Role;
    onRoleChange: (role: Role) => void;
    chat: ChatState;
    dispatch: Dispatch<ChatAction>;
    onAskFinished: () => void;
    adminToken: string | null;
    onAdminTokenChange: (token: string | null) => void;
};

function CurrentPage({
    page,
    role,
    onRoleChange,
    chat,
    dispatch,
    onAskFinished,
    adminToken,
    onAdminTokenChange,
}: CurrentPageProps) {
    switch (page) {
        case "chat":
            return (
                <ChatPage
                    role={role}
                    chat={chat}
                    dispatch={dispatch}
                    onAskFinished={onAskFinished}
                />
            );
        case "admin":
            return (
                <AdminPage
                    role={role}
                    onRoleChange={onRoleChange}
                    token={adminToken}
                    onTokenChange={onAdminTokenChange}
                />
            );
        case "dashboards":
            return <DashboardsPage />;
        case "evals":
            return <EvalsPage />;
        case "how-i-built-this":
            return <HowIBuiltThis />;
    }
}

export function App() {
    const page = useHashRoute();
    const [role, setRole] = useState<Role>("support");
    const [adminToken, setAdminToken] = useState<string | null>(null);
    const [chat, dispatch] = useReducer(chatReducer, undefined, initialChatState);
    const { client, budget, refreshBudget, budgetStop } = useBudgetedClient(role);
    const documentCount = useDocumentCount(client);

    return (
        <ApiContext.Provider value={client}>
            <div className="flex min-h-screen flex-col">
                {budgetStop && <BudgetBanner resetsAt={budgetStop.resetsAt} />}
                <TopBar page={page} budget={budget} documentCount={documentCount} />
                <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6">
                    <CurrentPage
                        page={page}
                        role={role}
                        onRoleChange={setRole}
                        chat={chat}
                        dispatch={dispatch}
                        onAskFinished={refreshBudget}
                        adminToken={adminToken}
                        onAdminTokenChange={setAdminToken}
                    />
                </main>
                <Footer />
            </div>
        </ApiContext.Provider>
    );
}
