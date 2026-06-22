from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .invoice import match_invoices, organize_invoice_files_by_bill
from .models import (
    AuditEvent,
    BillingBatch,
    CompanyQuarterBill,
    StoreFeeLine,
    ValidationIssue,
    now_iso,
)
from .parser import cents_to_amount, parse_service_fee_file
from .structure import remap_lines_to_secondary_company
from .template import export_company_detail_workbooks


def process_batch(
    batch_id: str,
    name: str,
    source_file: Path,
    invoice_files: Iterable[Path],
    template_file: Path | None,
    quarter: str,
    created_by: str,
    config: Dict[str, Any],
    structure_file: Path | None = None,
    organized_invoice_dir: Path | None = None,
    flat_invoice_dir: Path | None = None,
    company_workbook_dir: Path | None = None,
) -> BillingBatch:
    invoice_file_list = list(invoice_files)
    parsed = parse_service_fee_file(source_file, config, quarter)
    structure_source = ""
    if structure_file is not None:
        parsed.lines, structure_issues, structure_source = remap_lines_to_secondary_company(parsed.lines, structure_file)
        parsed.issues.extend(structure_issues)
    invoice_matches, invoice_issues = match_invoices(invoice_file_list, parsed.lines, config)
    issues = parsed.issues + invoice_issues
    bills = aggregate_company_quarter_bills(parsed.lines, invoice_matches)
    if organized_invoice_dir is not None:
        organize_invoice_files_by_bill(
            bills,
            invoice_matches,
            organized_invoice_dir,
            flat_target_dir=flat_invoice_dir,
        )
    if company_workbook_dir is not None:
        export_company_detail_workbooks(bills, parsed.lines, company_workbook_dir)

    status = "blocked" if any(issue.severity == "error" for issue in issues) else "ready"
    created_at = now_iso()
    batch = BillingBatch(
        id=batch_id,
        name=name,
        quarter=quarter,
        created_by=created_by,
        status=status,
        created_at=created_at,
        updated_at=created_at,
        source_file=str(source_file),
        template_file=str(template_file) if template_file else None,
        field_mapping_version=config.get("field_mapping_version", "unknown"),
        invoice_regex=config.get("invoice_regex", ""),
        line_count=len(parsed.lines),
        company_count=len(bills),
        invoice_file_count=len(invoice_file_list),
        lines=parsed.lines,
        bills=bills,
        invoice_matches=invoice_matches,
        issues=issues,
        audit_events=[
            AuditEvent(
                event_type="batch_created",
                actor=created_by,
                message="批次已解析并完成规则校验。",
                detail={
                    "detected_headers": parsed.detected_headers,
                    "structure_source": structure_source,
                    "line_count": len(parsed.lines),
                    "company_count": len(bills),
                    "issue_count": len(issues),
                },
            )
        ],
        structure_file=str(structure_file) if structure_file else None,
        organized_invoice_dir=str(organized_invoice_dir) if organized_invoice_dir else None,
        flat_invoice_dir=str(flat_invoice_dir) if flat_invoice_dir else None,
        company_workbook_dir=str(company_workbook_dir) if company_workbook_dir else None,
    )
    batch.agent_summary = build_agent_summary(batch)
    return batch


def aggregate_company_quarter_bills(
    lines: List[StoreFeeLine], invoice_matches: List
) -> List[CompanyQuarterBill]:
    file_by_invoice: Dict[str, List[str]] = defaultdict(list)
    for match in invoice_matches:
        if match.status == "matched" and match.file_name:
            file_by_invoice[match.invoice_number].append(match.file_name)

    groups: Dict[tuple, List[StoreFeeLine]] = defaultdict(list)
    for line in lines:
        groups[(line.secondary_company, line.quarter)].append(line)

    bills: List[CompanyQuarterBill] = []
    for (company, quarter), group_lines in sorted(groups.items()):
        invoice_numbers = sorted({line.invoice_number for line in group_lines if line.invoice_number})
        invoice_files = sorted(
            {
                file_name
                for invoice_number in invoice_numbers
                for file_name in file_by_invoice.get(invoice_number, [])
            }
        )
        bills.append(
            CompanyQuarterBill(
                secondary_company=company,
                quarter=quarter,
                total_amount_cents=sum(line.service_fee_cents for line in group_lines),
                line_count=len(group_lines),
                store_codes=sorted({line.store_code for line in group_lines}),
                contract_numbers=sorted({line.contract_number for line in group_lines}),
                invoice_numbers=invoice_numbers,
                invoice_files=invoice_files,
            )
        )
    return bills


def build_agent_summary(batch: BillingBatch) -> str:
    error_count = sum(1 for issue in batch.issues if issue.severity == "error")
    warning_count = sum(1 for issue in batch.issues if issue.severity == "warning")
    total_cents = sum(bill.total_amount_cents for bill in batch.bills)
    lines = [
        f"已解析 {batch.line_count} 条门店服务费明细，形成 {batch.company_count} 张二级公司季度账单。",
        f"本批次合计金额 {cents_to_amount(total_cents)} 元，当前状态为 {'可提交' if batch.status == 'ready' else '需处理异常'}。",
    ]
    if error_count or warning_count:
        lines.append(f"发现 {error_count} 个阻断项、{warning_count} 个提醒项，请先查看异常清单。")
    else:
        lines.append("字段、金额和发票文件匹配校验均通过，提交前请复核汇总与模板预览。")
    return "\n".join(lines)


def blocking_issue_messages(issues: List[ValidationIssue]) -> List[str]:
    return [issue.message for issue in issues if issue.severity == "error"]
