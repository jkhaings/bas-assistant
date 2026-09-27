"""Behaviour: answers that cite unseen passages, link elsewhere or embed images never ship."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from bas_assistant.agent.nodes import FAILED_MESSAGE, TICKET_WITHOUT_DOCS_MESSAGE
from bas_assistant.agent.state import AnswerOut, TicketDraft
from bas_assistant.db.activity import Audit, Request
from bas_assistant.guardrails.output import find_violations
from tests.graph_fakes import (
    ADMIN_TOKEN,
    CHUNK_1,
    PASSAGES,
    SOURCE_URL,
    FakeProxy,
    answer_json,
    ask,
)

pytestmark = pytest.mark.unit


def _draft(answer: str, citations: list[str] | None = None) -> AnswerOut:
    return AnswerOut(
        answerable=True,
        answer=answer,
        citations=[CHUNK_1] if citations is None else citations,
        confidence="high",
        needs_ticket=False,
        ticket_draft=None,
    )


def test_fabricated_citation_is_retried_then_fails_closed(
    client: TestClient, proxy: FakeProxy, engine: Engine
) -> None:
    fabricated = answer_json(answer="It draws 9 W.", citations=("c999",))
    proxy.answers = [fabricated, fabricated]

    response = ask(client, "Power draw?")

    body = response.json()
    assert body["decision"] == "failed"
    assert body["answer"] == FAILED_MESSAGE
    assert body["citations"] == []
    assert "c999" not in response.text
    assert "9 W" not in response.text
    assert len(proxy.answer_calls()) == 2
    with engine.connect() as conn:
        actions: list[str] = list(conn.execute(select(Audit.action)).scalars())
    assert actions == ["answer_rejected", "decision"]


def test_rejected_answer_is_retried_with_the_violations_listed(
    client: TestClient, proxy: FakeProxy
) -> None:
    proxy.answers = [answer_json(citations=("c999",)), answer_json()]

    body = ask(client, "Power draw?").json()

    assert body["decision"] == "answered"
    retry_prompt = proxy.answer_calls()[1]["messages"][-1]["content"]
    assert "previous answer was rejected" in retry_prompt
    assert "c999" in retry_prompt


def test_output_that_is_not_the_schema_counts_as_a_rejected_answer(
    client: TestClient, proxy: FakeProxy
) -> None:
    proxy.answers = ["not json", answer_json()]

    assert ask(client, "Power draw?").json()["decision"] == "answered"
    assert len(proxy.answer_calls()) == 2


def test_citation_of_a_provided_passage_passes() -> None:
    assert find_violations(_draft("4 W at 24 VAC."), PASSAGES) == []


def test_answer_without_citations_is_a_violation() -> None:
    assert find_violations(_draft("4 W.", citations=[]), PASSAGES) == [
        "the answer cites no passage"
    ]


def test_url_outside_the_passage_sources_is_a_violation() -> None:
    violations = find_violations(_draft("See https://evil.example.net/x now."), PASSAGES)
    assert violations == [
        "link 'https://evil.example.net/x' is not the source url of a provided passage"
    ]


@pytest.mark.parametrize(
    "answer",
    [
        "See HTTPS://evil.example.net/x",
        "[here](//evil.example.net/x)",
        "Visit www.evil.example.net today",
        "[click](javascript:alert(1))",
        "<mailto:someone@evil.example.net>",
        "[x][1]\n\n[1]: javascript:alert(1)",
        "See [the sheet][s].\n\n[s]: //evil.example.net/p",
        '<a href="//evil.example.net">here</a>',
    ],
)
def test_every_followable_link_outside_the_sources_is_a_violation(answer: str) -> None:
    violations = find_violations(_draft(answer), PASSAGES)
    assert any(v.startswith("link ") for v in violations)
    # The one non-link violation any of these may add: the mailto address is personal data.
    others = [v for v in violations if not v.startswith("link ")]
    assert others in ([], ["the answer contains a EMAIL_ADDRESS that is not in the passages"])


def test_markdown_link_to_a_source_url_is_allowed() -> None:
    assert find_violations(_draft(f"See [the catalog sheet]({SOURCE_URL})."), PASSAGES) == []


def test_link_inside_a_ticket_draft_is_a_violation() -> None:
    draft = _draft("Drafted.").model_copy(
        update={
            "needs_ticket": True,
            "ticket_draft": TicketDraft(title="t", body="Details at https://evil.example.net"),
        }
    )
    assert find_violations(draft, PASSAGES) == [
        "link 'https://evil.example.net' is not the source url of a provided passage"
    ]


def test_source_url_of_a_provided_passage_is_allowed() -> None:
    assert find_violations(_draft(f"See {SOURCE_URL}."), PASSAGES) == []


def test_markdown_image_is_a_violation() -> None:
    violations = find_violations(_draft(f"![chart]({SOURCE_URL})"), PASSAGES)
    assert violations == ["the answer contains an image"]


def test_ticket_without_a_draft_is_a_violation() -> None:
    draft = _draft("Opening a ticket.").model_copy(update={"needs_ticket": True})
    assert find_violations(draft, PASSAGES) == ["needs_ticket is true but ticket_draft is null"]


def test_ticket_with_a_draft_passes() -> None:
    draft = _draft("Opening a ticket.").model_copy(
        update={"needs_ticket": True, "ticket_draft": TicketDraft(title="t", body="b")}
    )
    assert find_violations(draft, PASSAGES) == []


def test_model_saying_the_passages_do_not_cover_it_abstains(
    client: TestClient, proxy: FakeProxy
) -> None:
    proxy.answers = [
        answer_json(answer="Not covered, but try http://x.test", citations=(), answerable=False)
    ]

    body = ask(client, "What is the warranty period?").json()

    assert body["decision"] == "abstained"
    assert "couldn't find this in the documentation" in body["answer"]
    assert "x.test" not in body["answer"]
    assert len(proxy.answer_calls()) == 1


def test_ticket_for_something_the_docs_do_not_cover_shows_a_fixed_message(
    client: TestClient, proxy: FakeProxy, engine: Engine
) -> None:
    proxy.answers = [
        answer_json(
            answer="free text",
            citations=(CHUNK_1,),
            ticket_title="Warranty claim",
            answerable=False,
        )
    ]

    body = ask(client, "Open a ticket for a warranty claim", role="engineer").json()
    client.post(
        "/approve",
        json={"thread_id": body["thread_id"], "approve": True},
        headers={"X-Admin-Token": ADMIN_TOKEN, "X-Demo-Role": "admin"},
    )

    assert body["decision"] == "paused"
    assert body["answer"] == TICKET_WITHOUT_DOCS_MESSAGE
    assert body["citations"] == []
    with engine.connect() as conn:
        assert conn.execute(select(Request.decision)).scalar_one() == "abstained"


@pytest.mark.parametrize(
    "answer",
    [
        "![s][p]\n\n[p]: https://docs.example.com/sample-controller.pdf",
        "![a[b]c](https://docs.example.com/sample-controller.pdf)",
        '<img src="https://docs.example.com/sample-controller.pdf">',
    ],
)
def test_every_image_form_is_a_violation(answer: str) -> None:
    assert "the answer contains an image" in find_violations(_draft(answer), PASSAGES)


def test_reference_link_to_a_source_url_is_allowed() -> None:
    answer = f"See [the catalog sheet][s].\n\n[s]: {SOURCE_URL}"
    assert find_violations(_draft(answer), PASSAGES) == []


def test_role_without_tickets_abstains_when_the_docs_do_not_cover_it(
    client: TestClient, proxy: FakeProxy
) -> None:
    proxy.answers = [
        answer_json(answer="free text", citations=(), ticket_title="Claim", answerable=False)
    ]

    body = ask(client, "Open a ticket for a warranty claim", role="support").json()

    assert body["decision"] == "abstained"
    assert "couldn't find this in the documentation" in body["answer"]
    assert (body["ticket_id"], body["notes"]) == (None, [])


def test_personal_data_the_passages_do_not_contain_is_a_violation() -> None:
    violations = find_violations(
        _draft("4 W at 24 VAC. Ask Jane Doe at jane.doe@example.com."), PASSAGES
    )

    assert violations == [
        "the answer contains a EMAIL_ADDRESS that is not in the passages",
        "the answer contains a PERSON that is not in the passages",
    ]


def test_contact_details_quoted_from_a_passage_are_allowed() -> None:
    passage = PASSAGES[0].model_copy(
        update={"text": "Support line: 604-574-9444. The sample controller draws 4 W."}
    )

    assert find_violations(_draft("Call support on 604-574-9444."), [passage]) == []
