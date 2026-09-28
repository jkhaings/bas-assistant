import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { DashboardsPage } from "../pages/DashboardsPage";

test("both Grafana dashboards are embedded same-origin in kiosk mode", () => {
    render(<DashboardsPage />);

    expect(screen.getByTitle("Budget dashboard")).toHaveAttribute(
        "src",
        "/grafana/d/bas-budget/budget?orgId=1&kiosk",
    );
    expect(screen.getByTitle("Quality & adoption dashboard")).toHaveAttribute(
        "src",
        "/grafana/d/bas-quality/quality-and-adoption?orgId=1&kiosk",
    );
    expect(
        screen.getByText("Live numbers from this demo. Ask a question, then refresh."),
    ).toBeInTheDocument();
});
