from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class ExtractedAccount(BaseModel):
    kind: Literal["pretax", "roth", "taxable", "cash", "hsa"]
    owner_hint: str
    owner: Literal["self", "spouse"] = "self"
    label: str
    balance: float = Field(ge=0)
    cost_basis: float | None = Field(default=None, ge=0)
    last4: str | None = Field(default=None, pattern=r"^\d{4}$")


class ExtractedStatement(BaseModel):
    doc_type: Literal["account"]
    institution: str
    statement_date: date
    accounts: list[ExtractedAccount]


class ExtractedSsStatement(BaseModel):
    doc_type: Literal["social_security"]
    statement_date: date
    person: Literal["self", "spouse"] | None = None
    monthly_at_62: float = Field(ge=0)
    monthly_at_fra: float = Field(ge=0)
    fra_age: str
    monthly_at_70: float = Field(ge=0)


ExtractedDocument = Annotated[
    ExtractedStatement | ExtractedSsStatement, Field(discriminator="doc_type")
]


class UploadResult(BaseModel):
    filename: str
    id: int | None = None
    error: str | None = None


class StatementRow(BaseModel):
    id: int
    filename: str
    status: str
    extracted: ExtractedDocument | None
    created_at: str
