import { Section } from "./Section";

export function Problem() {
    return (
        <Section id="the-problem" title="The problem">
            <p>
                A building-automation support or sales desk answers the same kinds of product
                questions all day. How many inputs does this controller have? What does it draw?
                Which browsers does the web front end support? Which BACnet profile does it
                carry? The answers exist, spread across a hundred catalog sheets and product
                pages.
            </p>
            <p>
                A wrong answer is expensive. An off power figure sends a technician to site with
                the wrong transformer. So the assistant has three jobs: answer only from the
                documents, show the page so a person can check it in five seconds, and say "I
                couldn't find this" when the documents are silent.
            </p>
            <p>
                Two numbers decide whether it helps. How often is an answer used without edits,
                and how often does it sound right but turn out wrong? Every answer carries a
                "Flag as wrong" button for the second, and the Dashboards tab shows both. In a
                real deployment the support team rates each answer used as-is, used with edits
                or not used, and that is where the adoption number comes from; this public demo
                hides those buttons because its visitors are not the support team.
            </p>
        </Section>
    );
}
