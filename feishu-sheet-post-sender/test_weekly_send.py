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

    def test_enabled_resolves_receive_ids_from_contact_cache(self):
        env = {
            "FEISHU_WEEKLY_SEND_ENABLED": "true",
            "FEISHU_WEEKLY_ENV_FILE": ".env.local",
            "FEISHU_WEEKLY_SHEET_URL": "https://tenant.feishu.cn/wiki/node?sheet=abc",
            "FEISHU_WEEKLY_RANGE": "A1:C16",
            "FEISHU_WEEKLY_RECEIVE_IDS": "王康旭, E001",
            "FEISHU_WEEKLY_RECEIVE_ID_TYPE": "user_id",
            "FEISHU_WEEKLY_TITLE": "项目进展",
            "FEISHU_WEEKLY_MESSAGE_FORMAT": "card",
            "FEISHU_CONTACT_CACHE_ENABLED": "true",
            "FEISHU_CONTACT_CACHE_PATH": "contacts_cache.json",
        }
        cache = {
            "users": [
                {
                    "name": "王康旭",
                    "user_id": "12139762",
                    "employee_no": "E001",
                }
            ]
        }

        with patch.dict(os.environ, env, clear=True), patch.object(weekly_send.contact_cache, "load_cache", return_value=cache), patch.object(weekly_send.sender, "main", return_value=0) as sender_main:
            result = weekly_send.run_from_env()

        self.assertEqual(result, 0)
        self.assertEqual(sender_main.call_count, 2)
        self.assertEqual(sender_main.call_args_list[0][0][0][7], "12139762")
        self.assertEqual(sender_main.call_args_list[1][0][0][7], "12139762")

    def test_enabled_sends_to_typed_recipients(self):
        env = {
            "FEISHU_WEEKLY_SEND_ENABLED": "true",
            "FEISHU_WEEKLY_ENV_FILE": ".env.local",
            "FEISHU_WEEKLY_SHEET_URL": "https://tenant.feishu.cn/wiki/node?sheet=abc",
            "FEISHU_WEEKLY_RANGE": "A1:C16",
            "FEISHU_WEEKLY_RECIPIENTS": "user_id:12139762, open_id:ou_123",
            "FEISHU_WEEKLY_TITLE": "项目进展",
            "FEISHU_WEEKLY_MESSAGE_FORMAT": "card",
        }

        with patch.dict(os.environ, env, clear=True), patch.object(weekly_send.sender, "main", return_value=0) as sender_main:
            result = weekly_send.run_from_env()

        self.assertEqual(result, 0)
        self.assertEqual(sender_main.call_count, 2)
        self.assertEqual(sender_main.call_args_list[0][0][0][7], "12139762")
        self.assertEqual(sender_main.call_args_list[0][0][0][9], "user_id")
        self.assertEqual(sender_main.call_args_list[1][0][0][7], "ou_123")
        self.assertEqual(sender_main.call_args_list[1][0][0][9], "open_id")

    def test_enabled_resolves_email_recipient_before_sending(self):
        env = {
            "FEISHU_WEEKLY_SEND_ENABLED": "true",
            "FEISHU_WEEKLY_ENV_FILE": ".env.local",
            "FEISHU_WEEKLY_SHEET_URL": "https://tenant.feishu.cn/wiki/node?sheet=abc",
            "FEISHU_WEEKLY_RANGE": "A1:C16",
            "FEISHU_WEEKLY_RECIPIENTS": "email:person@example.com",
            "FEISHU_WEEKLY_EMAIL_LOOKUP_ID_TYPE": "open_id",
            "FEISHU_WEEKLY_TITLE": "项目进展",
            "FEISHU_WEEKLY_MESSAGE_FORMAT": "card",
        }

        with patch.dict(os.environ, env, clear=True), patch.object(weekly_send, "lookup_recipient_by_email", return_value=("open_id", "ou_123")) as lookup, patch.object(weekly_send.sender, "main", return_value=0) as sender_main:
            result = weekly_send.run_from_env()

        self.assertEqual(result, 0)
        lookup.assert_called_once_with("person@example.com")
        sender_main.assert_called_once()
        self.assertEqual(sender_main.call_args_list[0][0][0][7], "ou_123")
        self.assertEqual(sender_main.call_args_list[0][0][0][9], "open_id")

    def test_continues_when_one_typed_recipient_fails_to_send(self):
        env = {
            "FEISHU_WEEKLY_SEND_ENABLED": "true",
            "FEISHU_WEEKLY_ENV_FILE": ".env.local",
            "FEISHU_WEEKLY_SHEET_URL": "https://tenant.feishu.cn/wiki/node?sheet=abc",
            "FEISHU_WEEKLY_RANGE": "A1:C16",
            "FEISHU_WEEKLY_RECIPIENTS": "user_id:bad, user_id:good",
            "FEISHU_WEEKLY_TITLE": "项目进展",
            "FEISHU_WEEKLY_MESSAGE_FORMAT": "card",
        }

        with patch.dict(os.environ, env, clear=True), patch.object(weekly_send.sender, "main", side_effect=[1, 0]) as sender_main:
            result = weekly_send.run_from_env()

        self.assertEqual(result, 1)
        self.assertEqual(sender_main.call_count, 2)
        self.assertEqual(sender_main.call_args_list[0][0][0][7], "bad")
        self.assertEqual(sender_main.call_args_list[1][0][0][7], "good")

    def test_continues_when_one_email_recipient_cannot_be_resolved(self):
        env = {
            "FEISHU_WEEKLY_SEND_ENABLED": "true",
            "FEISHU_WEEKLY_ENV_FILE": ".env.local",
            "FEISHU_WEEKLY_SHEET_URL": "https://tenant.feishu.cn/wiki/node?sheet=abc",
            "FEISHU_WEEKLY_RANGE": "A1:C16",
            "FEISHU_WEEKLY_RECIPIENTS": "email:bad@example.com, user_id:12139762",
            "FEISHU_WEEKLY_TITLE": "项目进展",
            "FEISHU_WEEKLY_MESSAGE_FORMAT": "card",
        }

        with patch.dict(os.environ, env, clear=True), patch.object(weekly_send, "lookup_recipient_by_email", side_effect=ValueError("not found")), patch.object(weekly_send.sender, "main", return_value=0) as sender_main:
            result = weekly_send.run_from_env()

        self.assertEqual(result, 1)
        sender_main.assert_called_once()
        self.assertEqual(sender_main.call_args_list[0][0][0][7], "12139762")
        self.assertEqual(sender_main.call_args_list[0][0][0][9], "user_id")


if __name__ == "__main__":
    unittest.main()
