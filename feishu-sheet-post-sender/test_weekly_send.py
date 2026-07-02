import os
import unittest
from unittest.mock import patch

import weekly_send


class WeeklySendTests(unittest.TestCase):
    def test_disabled_by_default_skips_send(self):
        env = {
            "FEISHU_WEEKLY_SHEET_URL": "https://tenant.feishu.cn/wiki/node?sheet=abc",
            "FEISHU_WEEKLY_RANGE": "A1:C16",
            "FEISHU_WEEKLY_RECEIVE_ID": "12139762",
        }

        with patch.dict(os.environ, env, clear=True), patch.object(weekly_send.sender, "main") as sender_main:
            result = weekly_send.run_from_env()

        self.assertEqual(result, 0)
        sender_main.assert_not_called()

    def test_enabled_builds_send_command_from_environment(self):
        env = {
            "FEISHU_WEEKLY_SEND_ENABLED": "true",
            "FEISHU_WEEKLY_ENV_FILE": ".env.local",
            "FEISHU_WEEKLY_SHEET_URL": "https://tenant.feishu.cn/wiki/node?sheet=abc",
            "FEISHU_WEEKLY_RANGE": "A1:C16",
            "FEISHU_WEEKLY_RECEIVE_ID": "12139762",
            "FEISHU_WEEKLY_RECEIVE_ID_TYPE": "user_id",
            "FEISHU_WEEKLY_TITLE": "项目进展",
            "FEISHU_WEEKLY_MESSAGE_FORMAT": "card",
        }

        with patch.dict(os.environ, env, clear=True), patch.object(weekly_send.sender, "main", return_value=0) as sender_main:
            result = weekly_send.run_from_env()

        self.assertEqual(result, 0)
        sender_main.assert_called_once_with(
            [
                "--env-file",
                ".env.local",
                "--sheet-url",
                "https://tenant.feishu.cn/wiki/node?sheet=abc",
                "--range",
                "A1:C16",
                "--receive-id",
                "12139762",
                "--receive-id-type",
                "user_id",
                "--title",
                "项目进展",
                "--message-format",
                "card",
                "--send",
            ]
        )

    def test_enabled_sends_to_multiple_receive_ids(self):
        env = {
            "FEISHU_WEEKLY_SEND_ENABLED": "true",
            "FEISHU_WEEKLY_ENV_FILE": ".env.local",
            "FEISHU_WEEKLY_SHEET_URL": "https://tenant.feishu.cn/wiki/node?sheet=abc",
            "FEISHU_WEEKLY_RANGE": "A1:C16",
            "FEISHU_WEEKLY_RECEIVE_IDS": "12139762, 12345678",
            "FEISHU_WEEKLY_RECEIVE_ID_TYPE": "user_id",
            "FEISHU_WEEKLY_TITLE": "项目进展",
            "FEISHU_WEEKLY_MESSAGE_FORMAT": "card",
        }

        with patch.dict(os.environ, env, clear=True), patch.object(weekly_send.sender, "main", return_value=0) as sender_main:
            result = weekly_send.run_from_env()

        self.assertEqual(result, 0)
        self.assertEqual(sender_main.call_count, 2)
        self.assertEqual(sender_main.call_args_list[0][0][0][7], "12139762")
        self.assertEqual(sender_main.call_args_list[1][0][0][7], "12345678")


if __name__ == "__main__":
    unittest.main()
