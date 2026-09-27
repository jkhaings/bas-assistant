import type { CategoryScores } from "../../api/evalScores";

const CATEGORY_ORDER = [
    "spec",
    "ordering",
    "wiring-power",
    "protocol",
    "compatibility",
    "engineer-only",
];

const METRICS = [
    { key: "faithfulness", label: "Faithfulness" },
    { key: "answer_relevancy", label: "Answer relevancy" },
    { key: "context_precision", label: "Context precision" },
    { key: "context_recall", label: "Context recall" },
] as const;

const LOW_SCORE = 0.5;
const CELL = "px-3 py-2 text-right tabular-nums";

function categoryRank(category: string): number {
    const index = CATEGORY_ORDER.indexOf(category);
    return index === -1 ? CATEGORY_ORDER.length : index;
}

function ScoreCell({ value }: { value: number | null }) {
    if (value === null) return <td className={`${CELL} text-stone-400`}>–</td>;
    if (value >= LOW_SCORE) return <td className={CELL}>{value.toFixed(3)}</td>;
    return (
        <td className={`${CELL} bg-amber-50 font-semibold text-amber-800`} title="Below 0.5">
            {value.toFixed(3)}
            <span className="sr-only"> (low)</span>
        </td>
    );
}

function ScoreRow({
    name,
    scores,
    strong,
}: {
    name: string;
    scores: CategoryScores;
    strong?: boolean;
}) {
    return (
        <tr
            className={
                strong ? "border-t-2 border-stone-300 font-semibold" : "border-t border-stone-100"
            }
        >
            <th scope="row" className="px-3 py-2 text-left font-medium">
                {name}
            </th>
            <td className={CELL}>{scores.n}</td>
            {METRICS.map(({ key }) => (
                <ScoreCell key={key} value={scores[key]} />
            ))}
        </tr>
    );
}

type Props = { byCategory: Record<string, CategoryScores>; overall: CategoryScores };

export function RagasTable({ byCategory, overall }: Props) {
    const rows = Object.entries(byCategory).sort(([a], [b]) => categoryRank(a) - categoryRank(b));
    return (
        <div className="overflow-x-auto rounded-lg border border-stone-200 bg-white">
            <table className="w-full text-sm">
                <caption className="sr-only">RAGAS scores by question category</caption>
                <thead className="bg-stone-50 text-xs text-stone-500">
                    <tr>
                        <th scope="col" className="px-3 py-2 text-left">
                            Category
                        </th>
                        <th scope="col" className="px-3 py-2 text-right">
                            n
                        </th>
                        {METRICS.map(({ key, label }) => (
                            <th key={key} scope="col" className="px-3 py-2 text-right">
                                {label}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rows.map(([name, scores]) => (
                        <ScoreRow key={name} name={name} scores={scores} />
                    ))}
                    <ScoreRow name="overall" scores={overall} strong />
                </tbody>
            </table>
        </div>
    );
}
