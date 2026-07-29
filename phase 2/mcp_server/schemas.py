"""
schemas.py
==========
Pydantic models used for elicitation confirmations in the write tools.
Kept separate so tools.py stays import-clean and these can be tested
in isolation.
"""

from pydantic import BaseModel, Field


class GradeOverrideConfirmation(BaseModel):
    confirmed: bool = Field(
        description="Apply this grade change even though it affects the student's "
        "scholarship eligibility or is a large change to an existing grade?"
    )
    note: str | None = Field(default=None, description="Optional reason for the record")


class WithdrawalConfirmation(BaseModel):
    confirmed: bool = Field(
        description="Confirm marking this enrollment as dropped after the "
        "no-penalty withdrawal window has passed?"
    )