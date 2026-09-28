import type { Budget, Role } from "../api/types";
import type { Page } from "../hooks/useHashRoute";
import { NavTabs } from "./NavTabs";
import { RoleSelect } from "./RoleSelect";
import { BudgetChip, DocumentsChip } from "./StatusChips";

type Props = {
    page: Page;
    role: Role;
    onRoleChange: (role: Role) => void;
    budget: Budget | null;
    documentCount: number | null;
};

export function TopBar({ page, role, onRoleChange, budget, documentCount }: Props) {
    return (
        <header className="border-b border-stone-200 bg-white">
            <div className="mx-auto max-w-6xl px-4 sm:px-6">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-3 pb-2">
                    <a
                        href="#/chat"
                        className="text-lg font-semibold tracking-tight text-stone-900"
                    >
                        bas-assistant
                    </a>
                    <div className="flex flex-wrap items-center gap-2">
                        <BudgetChip budget={budget} />
                        <DocumentsChip count={documentCount} />
                    </div>
                    <div className="sm:ml-auto">
                        <RoleSelect role={role} onChange={onRoleChange} />
                    </div>
                </div>
                <NavTabs current={page} />
            </div>
        </header>
    );
}
