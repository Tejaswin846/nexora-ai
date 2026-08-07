from __future__ import annotations

from typing import Any

from ..contracts.models import StepEnvelope, ValidationResult
from .contract_validator import ContractValidator


class Revalidator:
    def __init__(self, validator: ContractValidator) -> None:
        self.validator = validator

    def revalidate(self, envelope: StepEnvelope, recovered_output: Any, attempt_number: int) -> ValidationResult:
        recovered = envelope.model_copy(update={"output": recovered_output, "attempt_number": attempt_number})
        return self.validator.validate(recovered)
