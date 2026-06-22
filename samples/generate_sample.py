from __future__ import annotations

from pathlib import Path


def main() -> None:
    from openpyxl import Workbook

    root = Path(__file__).resolve().parent
    invoices_dir = root / "invoices"
    invoices_dir.mkdir(exist_ok=True)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "服务费"
    sheet.append(["二级公司", "季度", "门店代码", "门店名称", "合同编号", "发票号码", "服务费"])
    sheet.append(["华东二级公司", "2026 Q1", "S001", "上海一店", "C-001", "12345678", 1000])
    sheet.append(["华东二级公司", "2026 Q1", "S002", "上海二店", "C-002", "87654321", 2500.5])
    sheet.append(["华南二级公司", "2026 Q1", "S003", "广州一店", "C-003", "11112222", 300.2])
    source_path = root / "service_fee_2026_q1.xlsx"
    workbook.save(source_path)

    for number in ["12345678", "87654321", "11112222"]:
        (invoices_dir / f"服务费发票_{number}.pdf").write_bytes(b"%PDF-1.4\n% sample invoice placeholder\n")

    print(f"sample_source={source_path}")
    print(f"sample_invoices={invoices_dir}")


if __name__ == "__main__":
    main()
