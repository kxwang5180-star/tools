import json
from datetime import date
import unittest

import feishu_sheet_post_sender as sender


class FeishuSheetPostSenderTests(unittest.TestCase):
    def test_parse_sheet_url_extracts_token_and_sheet_id(self):
        result = sender.parse_sheet_url(
            "https://example.feishu.cn/sheets/shtcnABC123?sheet=abc456&view=grid"
        )

        self.assertEqual(result["spreadsheet_token"], "shtcnABC123")
        self.assertEqual(result["sheet_id"], "abc456")

    def test_parse_wiki_url_extracts_node_token_and_table_hint(self):
        result = sender.parse_wiki_url(
            "https://haidilao.feishu.cn/wiki/XY6Uwdj8XiLGttkRkEmcCXUon9e?sheet=ec004f"
        )

        self.assertEqual(result["node_token"], "XY6Uwdj8XiLGttkRkEmcCXUon9e")
        self.assertEqual(result["table_id"], "ec004f")

    def test_build_range_uses_sheet_id_and_cell_range(self):
        self.assertEqual(sender.build_range("abc456", "A1:D5"), "abc456!A1:D5")
        self.assertEqual(sender.build_range("abc456", "abc456!A1:D5"), "abc456!A1:D5")

    def test_parse_a1_range_for_bitable_limits_columns_and_records(self):
        parsed = sender.parse_a1_range_for_bitable("A1:C16")

        self.assertEqual(parsed["max_columns"], 3)
        self.assertEqual(parsed["max_records"], 15)

    def test_values_to_markdown_escapes_pipes_and_limits_rows(self):
        markdown = sender.values_to_markdown(
            [
                ["项目", "状态", "备注"],
                ["A|B", "进行中", "第一行\n第二行"],
                ["C", "", "x" * 80],
                ["D", "待处理", "超出展示行数"],
            ],
            max_rows=2,
            max_cell_length=12,
        )

        self.assertIn("| 项目 | 状态 | 备注 |", markdown)
        self.assertIn("| --- | --- | --- |", markdown)
        self.assertIn("A\\|B", markdown)
        self.assertIn("第一行<br>第二行", markdown)
        self.assertIn("xxxxxxxxxxxx...", markdown)
        self.assertIn("仅展示前 2 行", markdown)

    def test_filter_nearest_milestone_keeps_closest_dated_row(self):
        values = sender.filter_nearest_milestone(
            [
                ["里程碑", "计划时间", "状态"],
                ["需求评审", "2026-06-20", "完成"],
                ["开发完成", "2026-07-05", "进行中"],
                ["上线", "2026-08-01", "未开始"],
            ],
            today=date(2026, 7, 2),
        )

        self.assertEqual(values, [["里程碑", "计划时间", "状态"], ["开发完成", "2026-07-05", "进行中"]])

    def test_filter_nearest_milestone_leaves_non_milestone_tables_unchanged(self):
        values = [
            ["项目", "状态"],
            ["A", "2026-07-05"],
            ["B", "2026-08-01"],
        ]

        self.assertEqual(sender.filter_nearest_milestone(values, today=date(2026, 7, 2)), values)

    def test_build_markdown_message_adds_summary_and_table(self):
        markdown = sender.build_markdown_message(
            title="表格消息",
            values=[["里程碑", "计划时间"], ["开发完成", "2026-07-05"]],
            max_rows=20,
            max_columns=8,
            max_cell_length=80,
            generated_at="2026-07-02 14:30",
        )

        self.assertIn("**表格消息**", markdown)
        self.assertIn("更新时间：2026-07-02 14:30", markdown)
        self.assertIn("数据范围：1 条", markdown)
        self.assertIn("| 里程碑 | 计划时间 |", markdown)

    def test_build_post_message_payload_uses_post_md_tag(self):
        payload = sender.build_post_message_payload(
            receive_id="ou_test",
            receive_id_type="open_id",
            title="表格日报",
            markdown="| 项目 | 状态 |\n| --- | --- |\n| A | OK |",
        )

        self.assertEqual(payload["receive_id"], "ou_test")
        self.assertEqual(payload["msg_type"], "post")
        content = json.loads(payload["content"])
        self.assertEqual(content["zh_cn"]["title"], "表格日报")
        self.assertEqual(content["zh_cn"]["content"][0][0]["tag"], "md")

    def test_build_card_message_payload_uses_interactive_card(self):
        payload = sender.build_card_message_payload(
            receive_id="12139762",
            receive_id_type="user_id",
            title="表格消息",
            markdown="**表格消息**\n\n| 里程碑 | 时间 |\n| --- | --- |\n| 开发完成 | 2026-07-05 |",
        )

        self.assertEqual(payload["receive_id"], "12139762")
        self.assertEqual(payload["msg_type"], "interactive")
        card = json.loads(payload["content"])
        self.assertEqual(card["schema"], "2.0")
        self.assertEqual(card["header"]["template"], "blue")
        self.assertEqual(card["body"]["elements"][0]["tag"], "markdown")

    def test_extract_values_supports_feishu_value_range_shape(self):
        values = sender.extract_values(
            {
                "code": 0,
                "data": {
                    "valueRange": {
                        "values": [
                            ["项目", "状态"],
                            ["A", "OK"],
                        ]
                    }
                },
            }
        )

        self.assertEqual(values, [["项目", "状态"], ["A", "OK"]])

    def test_extract_user_id_prefers_requested_id_type(self):
        user_id = sender.extract_user_id(
            {
                "code": 0,
                "data": {
                    "user_list": [
                        {
                            "email": "person@example.com",
                            "user_id": "user_123",
                            "open_id": "ou_123",
                        }
                    ]
                },
            },
            "open_id",
        )

        self.assertEqual(user_id, "ou_123")

    def test_extract_user_id_raises_when_no_user_found(self):
        with self.assertRaises(sender.FeishuApiError):
            sender.extract_user_id({"code": 0, "data": {"user_list": []}}, "open_id")

    def test_bitable_records_to_values_keeps_field_order_and_limit(self):
        values = sender.bitable_records_to_values(
            [
                {"fields": {"项目": "A", "状态": "进行中", "负责人": [{"name": "王康旭"}], "备注": "忽略"}},
                {"fields": {"状态": "完成", "项目": "B", "负责人": "李四"}},
            ],
            max_columns=3,
            max_records=2,
        )

        self.assertEqual(values[0], ["项目", "状态", "负责人"])
        self.assertEqual(values[1], ["A", "进行中", "王康旭"])
        self.assertEqual(values[2], ["B", "完成", "李四"])

    def test_get_wiki_node_sends_wiki_obj_type(self):
        class FakeClient(sender.FeishuClient):
            def __init__(self):
                super().__init__("app", "secret")
                self.query = None

            def request(self, method, path, token="", body=None, query=None):
                self.query = query
                return {"code": 0, "data": {"node": {"obj_type": "bitable", "obj_token": "app_token"}}}

        client = FakeClient()
        client.get_wiki_node("tenant", "XY6Uwdj8XiLGttkRkEmcCXUon9e")

        self.assertEqual(client.query, {"token": "XY6Uwdj8XiLGttkRkEmcCXUon9e", "obj_type": "wiki"})

    def test_wiki_sheet_node_reads_as_spreadsheet(self):
        class FakeClient(sender.FeishuClient):
            def __init__(self):
                super().__init__("app", "secret")
                self.read_args = None

            def get_wiki_node(self, tenant_token, node_token):
                return {"obj_type": "sheet", "obj_token": "shtcn_from_wiki"}

            def read_sheet_range(self, tenant_token, spreadsheet_token, range_ref):
                self.read_args = (spreadsheet_token, range_ref)
                return [["项目", "状态"], ["A", "OK"]]

        args = type(
            "Args",
            (),
            {
                "sheet_url": "https://haidilao.feishu.cn/wiki/XY6Uwdj8XiLGttkRkEmcCXUon9e?sheet=ec004f",
                "range": "A1:C16",
                "table_id": "",
                "sheet_id": "",
                "max_columns": 8,
                "max_rows": 20,
            },
        )()
        client = FakeClient()

        values = sender.read_values_from_source(client, "tenant", args)

        self.assertEqual(values, [["项目", "状态"], ["A", "OK"]])
        self.assertEqual(client.read_args, ("shtcn_from_wiki", "ec004f!A1:C16"))


if __name__ == "__main__":
    unittest.main()
