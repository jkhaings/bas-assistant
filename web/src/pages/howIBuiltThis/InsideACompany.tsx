import { Section } from "./Section";

export function InsideACompany() {
    return (
        <Section id="inside-a-company" title="What would change inside a company">
            <ul className="list-disc space-y-2 pl-6">
                <li>
                    Single sign-on (Entra ID) instead of the role switcher, with roles from
                    directory groups.
                </li>
                <li>
                    SharePoint and Confluence through Microsoft Graph connectors, copying each
                    document's own permissions into the access groups the SQL filters on.
                </li>
                <li>
                    Jira instead of the internal ticket table, with a token scoped to one
                    project.
                </li>
                <li>Budgets and proxy keys per team, not one global cap.</li>
                <li>
                    An MCP server, so Claude, Copilot and other clients use the same guarded
                    search and ticket tools.
                </li>
                <li>
                    Traces kept in Langfuse. They run locally here, but not on this small
                    demo server.
                </li>
                <li>A scheduled re-index.</li>
                <li>A small, cost-capped evaluation subset on every pull request.</li>
                <li>
                    Four weeks in shadow mode, with the rule written down in advance: expand
                    to the next team if flagged answers stay under 2% and used-as-is stays
                    above 60%.
                </li>
            </ul>
        </Section>
    );
}
