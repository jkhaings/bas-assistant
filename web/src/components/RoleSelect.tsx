import { ROLES, type Role } from "../api/types";

const LABELS: Record<Role, string> = { support: "Support", engineer: "Engineer", admin: "Admin" };

type Props = { role: Role; onChange: (role: Role) => void };

export function RoleSelect({ role, onChange }: Props) {
    return (
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <label htmlFor="view-as" className="text-sm font-medium text-stone-700">
                View as:
            </label>
            <select
                id="view-as"
                value={role}
                onChange={(event) => {
                    const picked = ROLES.find((option) => option === event.target.value);
                    if (picked) onChange(picked);
                }}
                className="rounded-md border border-stone-300 bg-white px-2 py-1 text-sm"
            >
                {ROLES.map((option) => (
                    <option key={option} value={option}>
                        {LABELS[option]}
                    </option>
                ))}
            </select>
            <span className="text-xs text-stone-500">roles come from SSO in production</span>
        </div>
    );
}
