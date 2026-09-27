"""Input fence: Presidio redaction and the pattern half of the injection rail.

The model half of the rail rides on the router call (llm/router.py), so screening a question
costs no extra model call.
"""

import re
from collections import Counter
from dataclasses import dataclass
from functools import cache

from presidio_analyzer import (
    AnalyzerEngine,
    Pattern,
    PatternRecognizer,
    RecognizerRegistry,
    RecognizerResult,
)
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.predefined_recognizers import EmailRecognizer
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer import RecognizerResult as Found

PII_ENTITIES = ("EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON", "LOCATION", "STREET_ADDRESS")
# spaCy labels with no Presidio entity; left in, Presidio logs a warning for each one found.
_UNUSED_SPACY_LABELS = [
    "CARDINAL",
    "ORDINAL",
    "QUANTITY",
    "PERCENT",
    "MONEY",
    "PRODUCT",
    "WORK_OF_ART",
    "LAW",
    "LANGUAGE",
    "EVENT",
    "FAC",
]

# en_core_web_sm finds cities only some of the time and street lines never.
_STREET_ADDRESS = Pattern(
    name="street_address",
    regex=(
        r"\b\d{1,6}\s+(?:[a-z0-9.'-]+\s+){1,4}"
        r"(?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|way|court|ct"
        r"|place|pl|crescent|cres|highway|hwy)\b"
    ),
    score=0.6,
)

# Phrasings that only make sense as an attempt to change the assistant's instructions.
# Kept narrow: "ignore the wiring instructions" is a real support question.
_INJECTION_PATTERNS = {
    "override_instructions": re.compile(
        r"\b(?:ignore|disregard|forget|override)\s+(?:all\s+|any\s+)?"
        r"(?:(?:the|your|my|these|those)\s+)?"
        r"(?:previous\s+|prior\s+|above\s+|earlier\s+|system\s+|original\s+)?"
        r"(?:instructions|rules|prompts?|guidelines)\b",
        re.IGNORECASE,
    ),
    "reveal_prompt": re.compile(
        r"\bsystem\s+prompt\b|\b(?:reveal|print|show|repeat)\s+(?:me\s+)?(?:your|the)\s+"
        r"(?:hidden\s+)?(?:instructions|prompt|rules)\b",
        re.IGNORECASE,
    ),
    "role_change": re.compile(
        r"\b(?:you\s+are\s+now|from\s+now\s+on\s+you|pretend\s+(?:to\s+be|you\s+are)"
        r"|roleplay\s+as)\b",
        re.IGNORECASE,
    ),
    "jailbreak": re.compile(
        r"\b(?:jailbreak|developer\s+mode|do\s+anything\s+now|dan\s+mode)\b", re.IGNORECASE
    ),
}


@dataclass(frozen=True)
class Redaction:
    text: str
    # Entity type -> how many were replaced. Never the values.
    counts: dict[str, int]


@cache
def _analyzer() -> AnalyzerEngine:
    nlp = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
            "ner_model_configuration": {"labels_to_ignore": _UNUSED_SPACY_LABELS},
        }
    ).create_engine()
    registry = RecognizerRegistry(supported_languages=["en"])
    registry.load_predefined_recognizers(languages=["en"], nlp_engine=nlp, countries=["us"])
    # Presidio's email recognizer validates domains with tldextract, which downloads the
    # public suffix list on first use. Its patterns alone need no network.
    registry.remove_recognizer("EmailRecognizer")
    registry.add_recognizer(
        PatternRecognizer(
            supported_entity="EMAIL_ADDRESS",
            patterns=EmailRecognizer.PATTERNS,
            context=EmailRecognizer.CONTEXT,
        )
    )
    registry.add_recognizer(
        PatternRecognizer(supported_entity="STREET_ADDRESS", patterns=[_STREET_ADDRESS])
    )
    return AnalyzerEngine(nlp_engine=nlp, registry=registry, supported_languages=["en"])


@cache
def _anonymizer() -> AnonymizerEngine:
    # Presidio leaves AnonymizerEngine.__init__ unannotated.
    return AnonymizerEngine()  # type: ignore[no-untyped-call]


def find_pii(text: str, entities: tuple[str, ...] = PII_ENTITIES) -> list[RecognizerResult]:
    return _analyzer().analyze(text, language="en", entities=list(entities))


def redact(text: str) -> Redaction:
    """Replace every PII entity with its type, e.g. <EMAIL_ADDRESS>."""
    found = find_pii(text)
    if not found:
        return Redaction(text, {})
    # The anonymizer has its own result class with the same four fields.
    spans = [Found(item.entity_type, item.start, item.end, item.score) for item in found]
    result = _anonymizer().anonymize(text, spans)
    return Redaction(result.text, dict(Counter(item.entity_type for item in result.items)))


def injection_pattern(text: str) -> str | None:
    """The name of the first injection phrasing found in the text, if any."""
    return next((name for name, rx in _INJECTION_PATTERNS.items() if rx.search(text)), None)
