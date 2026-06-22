from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from .models import AuditEvent, BillingBatch, FinanceSubmission, now_iso
from .parser import cents_to_amount


class FinanceSystemAdapter:
    def submit_batch(self, batch: BillingBatch, actor: str) -> List[FinanceSubmission]:
        raise NotImplementedError


class MockFinanceSystemAdapter(FinanceSystemAdapter):
    """A deterministic test adapter that mirrors the real API boundary."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    def submit_batch(self, batch: BillingBatch, actor: str) -> List[FinanceSubmission]:
        if batch.has_blocking_issues():
            raise ValueError("批次存在阻断异常，不能提交。")

        submissions: List[FinanceSubmission] = []
        for bill in batch.bills:
            form_id = _stable_form_id(batch.id, bill.secondary_company, bill.quarter)
            payload = {
                "secondary_company": bill.secondary_company,
                "quarter": bill.quarter,
                "total_amount": cents_to_amount(bill.total_amount_cents),
                "line_count": bill.line_count,
                "store_codes": bill.store_codes,
                "contract_numbers": bill.contract_numbers,
                "invoice_numbers": bill.invoice_numbers,
            }
            invoice_uploads = [
                {
                    "file_name": file_name,
                    "status": "uploaded",
                    "remote_attachment_id": _stable_attachment_id(form_id, file_name),
                }
                for file_name in bill.invoice_files
            ]
            response = {
                "form_id": form_id,
                "api_mode": self.config.get("finance_api", {}).get("mode", "mock"),
                "message": "测试财务系统已接收表单和附件。",
            }
            submission = FinanceSubmission(
                batch_id=batch.id,
                company=bill.secondary_company,
                quarter=bill.quarter,
                form_id=form_id,
                status="submitted",
                submitted_at=now_iso(),
                request_payload=payload,
                response_payload=response,
                invoice_uploads=invoice_uploads,
            )
            submissions.append(submission)
            bill.external_form_id = form_id
            bill.submission_status = "submitted"

        batch.submissions.extend(submissions)
        batch.status = "submitted"
        batch.updated_at = now_iso()
        batch.audit_events.append(
            AuditEvent(
                event_type="batch_submitted",
                actor=actor,
                message="批次已提交到财务系统测试适配器。",
                detail={"submission_count": len(submissions)},
            )
        )
        return submissions


def _stable_form_id(*parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:10].upper()
    return f"FIN-{digest}"


def _stable_attachment_id(form_id: str, file_name: str) -> str:
    digest = hashlib.sha1(f"{form_id}|{file_name}".encode("utf-8")).hexdigest()[:12]
    return f"ATT-{digest}"
