from __future__ import annotations

from typing import List

from .models import BillingBatch


class BillingAgent:
    """Thin orchestration layer for the deterministic finance rules."""

    def explain_next_actions(self, batch: BillingBatch) -> List[str]:
        errors = [issue for issue in batch.issues if issue.severity == "error"]
        warnings = [issue for issue in batch.issues if issue.severity == "warning"]
        if errors:
            return [
                "先处理阻断异常，再重新上传批次。",
                "优先查看缺失字段、金额异常、发票文件缺失或发票文件重复。",
                "异常清理后再次生成模板，并由经办人确认提交。",
            ]
        if warnings:
            return [
                "复核提醒项是否符合业务预期。",
                "确认二级公司汇总金额、门店明细和发票匹配结果。",
                "确认无误后提交到财务系统测试环境。",
            ]
        return [
            "复核汇总金额和上传模板。",
            "确认发票附件完整。",
            "提交到财务系统测试环境。",
        ]
