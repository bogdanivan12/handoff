from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class DecisionContent(BaseModel):
    kind: Literal["decision"] = "decision"
    subject: str
    chosen: str
    alternatives_considered: list[str] = []
    rationale: str


class ConventionContent(BaseModel):
    kind: Literal["convention"] = "convention"
    subject: str
    rule: str
    example: str | None = None


class ConstraintContent(BaseModel):
    kind: Literal["constraint"] = "constraint"
    subject: str
    rule: str
    rationale: str | None = None
    severity: Literal["hard", "soft"]


class DomainConceptContent(BaseModel):
    kind: Literal["domain_concept"] = "domain_concept"
    term: str
    definition: str
    related_terms: list[str] = []


class TechnicalFactContent(BaseModel):
    kind: Literal["technical_fact"] = "technical_fact"
    subject: str
    fact: str
    verified_at: str | None = None


class KnownIssueContent(BaseModel):
    kind: Literal["known_issue"] = "known_issue"
    subject: str
    description: str
    workaround: str | None = None
    status: str = "open"


KnowledgeContent = Annotated[
    Union[
        DecisionContent,
        ConventionContent,
        ConstraintContent,
        DomainConceptContent,
        TechnicalFactContent,
        KnownIssueContent,
    ],
    Field(discriminator="kind"),
]
