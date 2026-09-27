import { useState } from "react";
import { useApi } from "../../api/context";
import { settle } from "../../api/settle";
import type { Receipt } from "../../api/types";
import { ReceiptDetails } from "./ReceiptDetails";

export function CostToggle({ requestId }: { requestId: string }) {
    const client = useApi();
    const [open, setOpen] = useState(false);
    const [receipt, setReceipt] = useState<Receipt | null>(null);
    const [error, setError] = useState<string | null>(null);

    async function toggle() {
        const opening = !open;
        setOpen(opening);
        if (!opening || receipt) return;
        setError(null);
        const result = await settle(
            client.GET("/requests/{request_id}/receipt", {
                params: { path: { request_id: requestId } },
            }),
        );
        if (result.ok) setReceipt(result.data);
        else setError(result.message);
    }

    return (
        <div>
            <button
                type="button"
                aria-expanded={open}
                onClick={() => void toggle()}
                className="text-xs font-medium text-accent underline-offset-2 hover:underline"
            >
                {open ? "Hide cost" : "Show cost"}
            </button>
            {open && (
                <section
                    aria-label="Cost receipt"
                    className="mt-2 rounded-md border border-stone-200 bg-stone-50 p-3"
                >
                    {receipt && <ReceiptDetails receipt={receipt} />}
                    {!receipt && !error && <p className="text-xs text-stone-500">Loading cost</p>}
                    {error && <p className="text-xs text-red-700">{error}</p>}
                </section>
            )}
        </div>
    );
}
