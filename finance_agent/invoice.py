from __future__ import annotations

import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .models import CompanyQuarterBill, InvoiceMatch, StoreFeeLine, ValidationIssue


def match_invoices(
    invoice_files: Iterable[Path], lines: List[StoreFeeLine], config: Dict[str, Any]
) -> Tuple[List[InvoiceMatch], List[ValidationIssue]]:
    regex = config.get("invoice_regex") or r"(?P<number>\d{8,20})"
    invoice_to_files: Dict[str, List[Path]] = defaultdict(list)
    issues: List[ValidationIssue] = []

    for file_path in invoice_files:
        number = extract_invoice_number(file_path.name, regex)
        if not number:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="invoice_filename_unrecognized",
                    message=f"发票文件名未识别到发票号码：{file_path.name}",
                )
            )
            continue
        invoice_to_files[number].append(file_path)

    referenced: Dict[str, List[StoreFeeLine]] = defaultdict(list)
    for line in lines:
        referenced[line.invoice_number].append(line)

    matches: List[InvoiceMatch] = []
    for invoice_number, related_lines in sorted(referenced.items()):
        files = invoice_to_files.get(invoice_number, [])
        related_store_codes = sorted({line.store_code for line in related_lines})
        if not files:
            issues.append(
                ValidationIssue(
                    severity="error"
                    if config.get("validation", {}).get("block_on_missing_invoice_file", True)
                    else "warning",
                    code="invoice_file_missing",
                    message=f"发票号码 {invoice_number} 没有匹配到文件。",
                    invoice_number=invoice_number,
                    company=related_lines[0].secondary_company if related_lines else None,
                )
            )
            matches.append(
                InvoiceMatch(
                    invoice_number=invoice_number,
                    file_name="",
                    status="missing_invoice_file",
                    related_store_codes=related_store_codes,
                )
            )
            continue

        status = "matched" if len(files) == 1 else "duplicate_invoice_file"
        if len(files) > 1:
            issues.append(
                ValidationIssue(
                    severity="error"
                    if config.get("validation", {}).get("block_on_duplicate_invoice_file", True)
                    else "warning",
                    code="duplicate_invoice_file",
                    message=f"发票号码 {invoice_number} 匹配到多个文件。",
                    invoice_number=invoice_number,
                    company=related_lines[0].secondary_company if related_lines else None,
                )
            )
        for file_path in files:
            matches.append(
                InvoiceMatch(
                    invoice_number=invoice_number,
                    file_name=file_path.name,
                    status=status,
                    file_path=str(file_path),
                    related_store_codes=related_store_codes,
                )
            )

    for invoice_number, files in sorted(invoice_to_files.items()):
        if invoice_number in referenced:
            continue
        for file_path in files:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="unreferenced_invoice_file",
                    message=f"发票文件未在服务费明细中引用：{file_path.name}",
                    invoice_number=invoice_number,
                )
            )
            matches.append(
                InvoiceMatch(
                    invoice_number=invoice_number,
                    file_name=file_path.name,
                    status="unreferenced_file",
                    file_path=str(file_path),
                )
            )

    return matches, issues


def extract_invoice_number(file_name: str, regex: str) -> str:
    match = re.search(regex, file_name)
    if not match:
        return ""
    if "number" in match.groupdict():
        return match.group("number")
    return match.group(1) if match.groups() else match.group(0)


def organize_invoice_files_by_bill(
    bills: List[CompanyQuarterBill],
    invoice_matches: List[InvoiceMatch],
    target_dir: Path,
    flat_target_dir: Path | None = None,
) -> None:
    matched_path_by_invoice: Dict[str, List[Path]] = defaultdict(list)
    for match in invoice_matches:
        if match.status == "matched" and match.file_path:
            matched_path_by_invoice[match.invoice_number].append(Path(match.file_path))

    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    for bill in bills:
        bill_dir = target_dir / _safe_folder_name(f"{bill.secondary_company}_{bill.quarter}")
        bill_dir.mkdir(parents=True, exist_ok=True)
        for invoice_number in bill.invoice_numbers:
            for source in matched_path_by_invoice.get(invoice_number, []):
                if not source.exists():
                    continue
                target = _unique_target_path(bill_dir, source.name)
                shutil.copy2(source, target)

    if flat_target_dir is not None:
        if flat_target_dir.exists():
            shutil.rmtree(flat_target_dir)
        flat_target_dir.mkdir(parents=True, exist_ok=True)
        copied_sources: set[Path] = set()
        for paths in matched_path_by_invoice.values():
            for source in paths:
                if source in copied_sources or not source.exists():
                    continue
                target = _unique_target_path(flat_target_dir, source.name)
                shutil.copy2(source, target)
                copied_sources.add(source)


def _safe_folder_name(value: str) -> str:
    return re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", value).strip("_") or "invoices"


def _unique_target_path(target_dir: Path, file_name: str) -> Path:
    target = target_dir / file_name
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    counter = 2
    while True:
        candidate = target_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
