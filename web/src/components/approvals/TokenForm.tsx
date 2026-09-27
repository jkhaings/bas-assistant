import { useState } from "react";

type Props = { notice: string | null; onSubmit: (token: string) => void };

export function TokenForm({ notice, onSubmit }: Props) {
    const [token, setToken] = useState("");

    return (
        <form
            onSubmit={(event) => {
                event.preventDefault();
                if (token) onSubmit(token);
            }}
            className="max-w-sm space-y-3 rounded-lg border border-stone-200 bg-white p-4 shadow-sm"
        >
            <label htmlFor="admin-token" className="block text-sm font-medium text-stone-700">
                Admin token
            </label>
            <input
                id="admin-token"
                type="password"
                autoComplete="off"
                value={token}
                onChange={(event) => setToken(event.target.value)}
                className="block w-full rounded-md border border-stone-300 px-3 py-1.5 text-sm"
            />
            <p className="text-xs text-stone-500">Kept in memory only, never stored.</p>
            {notice && (
                <p role="alert" className="text-sm text-red-700">
                    {notice}
                </p>
            )}
            <button
                type="submit"
                disabled={!token}
                className="rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white hover:bg-accent-strong disabled:opacity-50"
            >
                Continue
            </button>
        </form>
    );
}
