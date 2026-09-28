import { PageHeader } from "../components/PageHeader";

const DASHBOARDS = [
    { title: "Budget", path: "/grafana/d/bas-budget/budget?orgId=1", height: 1100 },
    {
        title: "Quality & adoption",
        path: "/grafana/d/bas-quality/quality-and-adoption?orgId=1",
        height: 1900,
    },
];

export function DashboardsPage() {
    return (
        <div className="space-y-8">
            <PageHeader title="Dashboards">
                Live numbers from this demo. Ask a question, then refresh.
            </PageHeader>
            {DASHBOARDS.map(({ title, path, height }) => (
                <section key={path} aria-label={title} className="space-y-2">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <h2 className="text-base font-semibold">{title}</h2>
                        <a
                            href={path}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm font-medium text-accent hover:underline"
                        >
                            Open in Grafana
                            <span className="sr-only"> (opens in a new tab)</span>
                        </a>
                    </div>
                    <iframe
                        title={`${title} dashboard`}
                        src={`${path}&kiosk`}
                        loading="lazy"
                        style={{ height }}
                        className="w-full rounded-lg border border-stone-200 bg-white"
                    />
                </section>
            ))}
        </div>
    );
}
