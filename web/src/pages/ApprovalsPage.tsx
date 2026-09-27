import { useCallback, useState } from "react";
import type { Role } from "../api/types";
import { TicketBoard } from "../components/approvals/TicketBoard";
import { TokenForm } from "../components/approvals/TokenForm";
import { PageHeader } from "../components/PageHeader";

type Props = {
    role: Role;
    token: string | null;
    onTokenChange: (token: string | null) => void;
};

export function ApprovalsPage({ role, token, onTokenChange }: Props) {
    const [notice, setNotice] = useState<string | null>(null);

    const rejectToken = useCallback(() => {
        onTokenChange(null);
        setNotice("That token was rejected.");
    }, [onTokenChange]);

    function body() {
        if (role !== "admin") {
            return <p className="text-sm text-stone-700">Switch to Admin to review tickets.</p>;
        }
        if (!token) {
            return (
                <TokenForm
                    notice={notice}
                    onSubmit={(value) => {
                        setNotice(null);
                        onTokenChange(value);
                    }}
                />
            );
        }
        return <TicketBoard token={token} onTokenRejected={rejectToken} />;
    }

    return (
        <div className="space-y-6">
            <PageHeader title="Approvals">
                When an engineer's question needs follow-up, the assistant drafts a ticket and
                pauses. Nothing is filed until an admin approves it here.
            </PageHeader>
            {body()}
        </div>
    );
}
