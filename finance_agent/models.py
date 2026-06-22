from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ValidationIssue:
    severity: str
    code: str
    message: str
    row_number: Optional[int] = None
    company: Optional[str] = None
    invoice_number: Optional[str] = None


@dataclass
class StoreFeeLine:
    source_row: int
    secondary_company: str
    quarter: str
    store_code: str
    store_name: str
    contract_number: str
    invoice_number: str
    service_fee_cents: int


@dataclass
class InvoiceMatch:
    invoice_number: str
    file_name: str
    status: str
    file_path: Optional[str] = None
    related_store_codes: List[str] = field(default_factory=list)


@dataclass
class CompanyQuarterBill:
    secondary_company: str
    quarter: str
    total_amount_cents: int
    line_count: int
    store_codes: List[str]
    contract_numbers: List[str]
    invoice_numbers: List[str]
    invoice_files: List[str]
    external_form_id: Optional[str] = None
    submission_status: str = "draft"


@dataclass
class FinanceSubmission:
    batch_id: str
    company: str
    quarter: str
    form_id: str
    status: str
    submitted_at: str
    request_payload: Dict[str, Any]
    response_payload: Dict[str, Any]
    invoice_uploads: List[Dict[str, Any]]


@dataclass
class AuditEvent:
    event_type: str
    actor: str
    message: str
    created_at: str = field(default_factory=now_iso)
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BillingBatch:
    id: str
    name: str
    quarter: str
    created_by: str
    status: str
    created_at: str
    updated_at: str
    source_file: str
    template_file: Optional[str]
    field_mapping_version: str
    invoice_regex: str
    line_count: int
    company_count: int
    invoice_file_count: int
    lines: List[StoreFeeLine] = field(default_factory=list)
    bills: List[CompanyQuarterBill] = field(default_factory=list)
    invoice_matches: List[InvoiceMatch] = field(default_factory=list)
    issues: List[ValidationIssue] = field(default_factory=list)
    submissions: List[FinanceSubmission] = field(default_factory=list)
    audit_events: List[AuditEvent] = field(default_factory=list)
    agent_summary: str = ""
    structure_file: Optional[str] = None
    organized_invoice_dir: Optional[str] = None
    flat_invoice_dir: Optional[str] = None
    company_workbook_dir: Optional[str] = None

    def has_blocking_issues(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)


def to_dict(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: to_dict(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: to_dict(item) for key, item in value.items()}
    return value


def issue_from_dict(data: Dict[str, Any]) -> ValidationIssue:
    return ValidationIssue(**data)


def line_from_dict(data: Dict[str, Any]) -> StoreFeeLine:
    return StoreFeeLine(**data)


def invoice_match_from_dict(data: Dict[str, Any]) -> InvoiceMatch:
    return InvoiceMatch(**data)


def bill_from_dict(data: Dict[str, Any]) -> CompanyQuarterBill:
    return CompanyQuarterBill(**data)


def submission_from_dict(data: Dict[str, Any]) -> FinanceSubmission:
    return FinanceSubmission(**data)


def audit_event_from_dict(data: Dict[str, Any]) -> AuditEvent:
    return AuditEvent(**data)


def batch_from_dict(data: Dict[str, Any]) -> BillingBatch:
    data = dict(data)
    data["lines"] = [line_from_dict(item) for item in data.get("lines", [])]
    data["bills"] = [bill_from_dict(item) for item in data.get("bills", [])]
    data["invoice_matches"] = [
        invoice_match_from_dict(item) for item in data.get("invoice_matches", [])
    ]
    data["issues"] = [issue_from_dict(item) for item in data.get("issues", [])]
    data["submissions"] = [
        submission_from_dict(item) for item in data.get("submissions", [])
    ]
    data["audit_events"] = [
        audit_event_from_dict(item) for item in data.get("audit_events", [])
    ]
    return BillingBatch(**data)
