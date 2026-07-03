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

    def test_filter_nearest_milestone_keeps_closest_dated_row_per_project(self):
        values = sender.filter_nearest_milestone(
            [
                ["项目", "里程碑", "计划时间", "状态"],
                ["A项目", "需求评审", "2026-06-20", "完成"],
                ["A项目", "开发完成", "2026-07-05", "进行中"],
                ["B项目", "方案评审", "2026-06-30", "完成"],
                ["B项目", "上线", "2026-08-01", "未开始"],
            ],
            today=date(2026, 7, 2),
        )

        self.assertEqual(
            values,
            [
                ["项目", "里程碑", "计划时间", "状态"],
                ["A项目", "开发完成", "2026-07-05", "进行中"],
                ["B项目", "方案评审", "2026-06-30", "完成"],
            ],
        )

    def test_filter_nearest_milestone_without_project_column_keeps_one_closest_row(self):
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

    def test_filter_nearest_milestone_keeps_closest_segment_inside_milestone_cell(self):
        values = sender.filter_nearest_milestone(
            [
                ["项目名称", "当前在做", "里程碑"],
                [
                    "A项目",
                    "接口开发",
                    "项目里程碑1：6月10日完成需求评审\n项目里程碑2：6月30日完成开发\n项目里程碑3：8月1日上线",
                ],
                [
                    "B项目",
                    "体验优化",
                    "测试：6月2日-6月10日\n项目里程碑3：优惠券管理优化，6月30日完成",
                ],
            ],
            today=date(2026, 7, 2),
        )

        self.assertEqual(values[1][2], "项目里程碑2：6月30日完成开发")
        self.assertEqual(values[2][2], "项目里程碑3：优惠券管理优化，6月30日完成")
        self.assertNotIn("8月1日", values[1][2])
        self.assertNotIn("测试：6月2日-6月10日", values[2][2])

    def test_split_milestone_segments_supports_inline_markers(self):
        segments = sender.split_milestone_segments(
            "1. 6月10日完成需求评审 2. 6月30日完成开发 项目里程碑3：8月1日上线"
        )

        self.assertEqual(
            segments,
            [
                "1. 6月10日完成需求评审",
                "2. 6月30日完成开发",
                "项目里程碑3：8月1日上线",
            ],
        )

    def test_filter_nearest_milestone_leaves_non_milestone_tables_unchanged(self):
        values = [
            ["项目", "状态"],
            ["A", "2026-07-05"],
            ["B", "2026-08-01"],
        ]

        self.assertEqual(sender.filter_nearest_milestone(values, today=date(2026, 7, 2)), values)

    def test_build_markdown_message_returns_only_table(self):
        markdown = sender.build_markdown_message(
            title="项目进展",
            values=[["里程碑", "计划时间"], ["开发完成", "2026-07-05"]],
            max_rows=20,
            max_columns=8,
            max_cell_length=80,
            generated_at="2026-07-02 14:30",
        )

        self.assertNotIn("**项目进展**", markdown)
        self.assertNotIn("更新时间", markdown)
        self.assertNotIn("数据范围", markdown)
        self.assertIn("| 里程碑 | 计划时间 |", markdown)
        self.assertTrue(markdown.startswith("| 里程碑 | 计划时间 |"))

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
        self.assertEqual(card["header"]["title"]["content"], "表格消息")
        self.assertNotIn("subtitle", card["header"])
        self.assertEqual(card["body"]["elements"][0]["tag"], "markdown")

    def test_build_card_message_payload_uses_column_sets_for_table_rows(self):
        payload = sender.build_card_message_payload(
            receive_id="12139762",
            receive_id_type="user_id",
            title="项目进展",
            markdown="",
            values=[
                ["项目名称", "当前在做", "里程碑"],
                ["【合同系统】项目", "损耗率闭环配置开发", "6月30日完成开发"],
                ["【大会员体系】项目", "多轮对话优化", "6月30日完成优惠券管理优化"],
            ],
        )

        card = json.loads(payload["content"])
        elements = card["body"]["elements"]
        self.assertEqual(elements[0]["tag"], "column_set")
        self.assertEqual(elements[0]["element_id"], "row_header")
        self.assertEqual(elements[1]["tag"], "column_set")
        self.assertEqual(elements[1]["columns"][0]["width"], "weighted")
        self.assertEqual(elements[1]["columns"][0]["weight"], 3)
        self.assertEqual(elements[1]["columns"][1]["width"], "weighted")
        self.assertEqual(elements[1]["columns"][1]["weight"], 3)
        self.assertEqual(elements[1]["columns"][2]["width"], "weighted")
        self.assertEqual(elements[1]["columns"][2]["weight"], 5)
        column_profile = [
            (column["width"], column.get("weight"))
            for column in elements[0]["columns"]
        ]
        self.assertEqual(
            column_profile,
            [(column["width"], column.get("weight")) for column in elements[1]["columns"]],
        )
        self.assertEqual(
            column_profile,
            [(column["width"], column.get("weight")) for column in elements[2]["columns"]],
        )
        self.assertIn("【合同系统】项目", elements[1]["columns"][0]["elements"][0]["content"])
        self.assertIn("6月30日完成开发", elements[1]["columns"][2]["elements"][0]["content"])

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

    def test_lookup_user_id_requests_selected_id_type(self):
        class FakeClient(sender.FeishuClient):
            def __init__(self):
                super().__init__("app", "secret")
                self.query = None
                self.body = None

            def request(self, method, path, token="", body=None, query=None):
                self.query = query
                self.body = body
                return {"code": 0, "data": {"user_list": [{"email": "person@example.com", "open_id": "ou_123"}]}}

        client = FakeClient()
        user_id = client.lookup_user_id("tenant", receive_id_type="open_id", email="person@example.com")

        self.assertEqual(user_id, "ou_123")
        self.assertEqual(client.query, {"user_id_type": "open_id"})
        self.assertEqual(client.body, {"emails": ["person@example.com"]})

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
