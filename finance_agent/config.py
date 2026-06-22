from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict


DEFAULT_CONFIG: Dict[str, Any] = {
    "field_mapping_version": "service-fee-v1",
    "field_aliases": {
        "secondary_company": ["二级公司", "二级公司名称", "所属二级公司"],
        "quarter": ["季度", "账期", "计费季度"],
        "store_code": ["门店代码", "门店编码", "店铺代码"],
        "store_name": ["门店名称", "店铺名称"],
        "contract_number": ["合同编号", "合同号"],
        "invoice_number": ["发票号码", "发票号", "发票代码"],
        "service_fee": ["服务费", "季度服务费", "2026年1-3月服务费"],
    },
    "required_fields": [
        "secondary_company",
        "store_code",
        "contract_number",
        "invoice_number",
        "service_fee",
    ],
    "invoice_regex": r"(?P<number>\d{8,20})",
    "finance_api": {
        "mode": "mock",
        "base_url": "https://finance-test.example.internal",
        "timeout_seconds": 20,
    },
    "upload_template_columns": [
        "二级公司",
        "季度",
        "合同编号",
        "门店代码",
        "门店名称",
        "发票号码",
        "服务费金额",
        "单据合计",
    ],
    "finance_import_defaults": {
        "operationSubTypeCode": "hdl0085-001",
        "taxType": "001105",
        "ccCode_suffix": "200002",
    },
    "validation": {
        "block_on_missing_invoice_file": True,
        "block_on_duplicate_invoice_file": True,
        "warn_on_duplicate_store_in_company_quarter": True,
    },
}


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        save_config(path, DEFAULT_CONFIG)
        return deepcopy(DEFAULT_CONFIG)
    with path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    return merge_defaults(config)


def save_config(path: Path, config: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(merge_defaults(config), handle, ensure_ascii=False, indent=2)


def merge_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(DEFAULT_CONFIG)
    for key, value in config.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged
