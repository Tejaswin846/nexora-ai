from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from ..contracts.models import (
    CONTRACT_VERSION,
    Severity,
    StepEnvelope,
    ValidationErrorDetail,
    ValidationResult,
)


class ContractValidator:
    def __init__(
        self,
        *,
        validator_version: str = "contract-validator-v1",
        model_registry: dict[str, type[BaseModel]] | None = None,
    ) -> None:
        self.validator_version = validator_version
        self.model_registry = model_registry or {}

    def validate(self, envelope: StepEnvelope) -> ValidationResult:
        contract = envelope.expected_contract or {}
        if not contract:
            return ValidationResult(
                contract_version=envelope.contract_version or CONTRACT_VERSION,
                validator_version=self.validator_version,
                valid=True,
                severity=Severity.INFO,
            )

        if contract.get("contract_type") == "pydantic":
            return self._validate_pydantic(envelope, contract)
        schema = (
            contract.get("schema")
            if isinstance(contract.get("schema"), dict)
            else contract
        )
        errors = self._validate_json_schema(envelope.output, schema)
        return ValidationResult(
            contract_version=str(contract.get("version") or envelope.contract_version),
            validator_version=self.validator_version,
            valid=not errors,
            errors=errors,
            severity=Severity.ERROR if errors else Severity.INFO,
        )

    def _validate_pydantic(
        self, envelope: StepEnvelope, contract: dict[str, Any]
    ) -> ValidationResult:
        model_name = str(contract.get("model") or "")
        model = self.model_registry.get(model_name)
        if model is None:
            return ValidationResult(
                contract_version=str(
                    contract.get("version") or envelope.contract_version
                ),
                validator_version=self.validator_version,
                valid=False,
                severity=Severity.ERROR,
                errors=[
                    ValidationErrorDetail(
                        path=[],
                        code="contract_model_missing",
                        message=f"Pydantic contract model is not registered: {model_name}",
                    )
                ],
            )
        try:
            model.model_validate(envelope.output)
            errors: list[ValidationErrorDetail] = []
        except ValidationError as error:
            errors = [
                ValidationErrorDetail(
                    path=list(item.get("loc", [])),
                    code=str(item.get("type") or "pydantic_validation_error"),
                    message=str(item.get("msg") or "Validation failed."),
                    severity=Severity.ERROR,
                )
                for item in error.errors(include_url=False)
            ]
        return ValidationResult(
            contract_version=str(contract.get("version") or envelope.contract_version),
            validator_version=self.validator_version,
            valid=not errors,
            errors=errors,
            severity=Severity.ERROR if errors else Severity.INFO,
        )

    def _validate_json_schema(
        self, value: Any, schema: dict[str, Any], path: list[str | int] | None = None
    ) -> list[ValidationErrorDetail]:
        path = path or []
        errors: list[ValidationErrorDetail] = []
        expected_type = schema.get("type")
        if expected_type and not self._matches_type(value, expected_type):
            errors.append(
                ValidationErrorDetail(
                    path=path,
                    code="type_mismatch",
                    message=f"Expected {expected_type}.",
                    severity=Severity.ERROR,
                )
            )
            return errors

        if expected_type == "object" or "properties" in schema:
            if not isinstance(value, dict):
                return errors or [
                    ValidationErrorDetail(
                        path=path,
                        code="type_mismatch",
                        message="Expected object.",
                        severity=Severity.ERROR,
                    )
                ]
            for required in schema.get("required", []):
                if required not in value:
                    errors.append(
                        ValidationErrorDetail(
                            path=path + [str(required)],
                            code="required",
                            message="Required field is missing.",
                            severity=Severity.ERROR,
                        )
                    )
            properties = schema.get("properties") or {}
            for key, child_schema in properties.items():
                if key in value and isinstance(child_schema, dict):
                    errors.extend(
                        self._validate_json_schema(
                            value[key], child_schema, path + [str(key)]
                        )
                    )

        if (
            expected_type == "array"
            and isinstance(value, list)
            and isinstance(schema.get("items"), dict)
        ):
            for index, item in enumerate(value):
                errors.extend(
                    self._validate_json_schema(item, schema["items"], path + [index])
                )

        enum_values = schema.get("enum")
        if enum_values is not None and value not in enum_values:
            errors.append(
                ValidationErrorDetail(
                    path=path,
                    code="enum",
                    message="Value is not one of the allowed enum values.",
                    severity=Severity.ERROR,
                )
            )
        return errors

    @staticmethod
    def _matches_type(value: Any, expected_type: str | list[str]) -> bool:
        if isinstance(expected_type, list):
            return any(
                ContractValidator._matches_type(value, item) for item in expected_type
            )
        if expected_type == "object":
            return isinstance(value, dict)
        if expected_type == "array":
            return isinstance(value, list)
        if expected_type == "string":
            return isinstance(value, str)
        if expected_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected_type == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if expected_type == "boolean":
            return isinstance(value, bool)
        if expected_type == "null":
            return value is None
        return True
