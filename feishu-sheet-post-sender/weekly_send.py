#!/usr/bin/env python3
"""Run the project progress sender from environment settings for schedulers."""

import os
import sys
from pathlib import Path
from typing import List, Tuple

import contact_cache
import feishu_sheet_post_sender as sender


TRUE_VALUES = {"1", "true", "yes", "y", "on"}
DIRECT_RECEIVE_ID_TYPES = {"open_id", "user_id", "union_id", "chat_id"}


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def env_value(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def require_env(name: str) -> str:
    value = env_value(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def typed_recipients_from_env() -> List[Tuple[str, str]]:
    raw_recipients = env_value("FEISHU_WEEKLY_RECIPIENTS")
    if not raw_recipients:
        return []
    recipients = []  # type: List[Tuple[str, str]]
    for item in raw_recipients.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError("Typed recipient must use type:value format: %s" % item)
        receive_id_type, value = item.split(":", 1)
        receive_id_type = receive_id_type.strip()
        value = value.strip()
        if not receive_id_type or not value:
            raise ValueError("Typed recipient must use type:value format: %s" % item)
        recipients.append((receive_id_type, value))
    return recipients


def receive_ids_from_env() -> List[str]:
    raw_ids = env_value("FEISHU_WEEKLY_RECEIVE_IDS")
    if not raw_ids:
        raw_ids = require_env("FEISHU_WEEKLY_RECEIVE_ID")
    receive_ids = [item.strip() for item in raw_ids.split(",") if item.strip()]
    if not receive_ids:
        raise ValueError("Missing required environment variable: FEISHU_WEEKLY_RECEIVE_ID or FEISHU_WEEKLY_RECEIVE_IDS")
    return receive_ids


def lookup_recipient_by_email(email: str) -> Tuple[str, str]:
    return lookup_recipient("email", email)


def lookup_recipient_by_mobile(mobile: str) -> Tuple[str, str]:
    return lookup_recipient("mobile", mobile)


def lookup_recipient(identifier_type: str, identifier: str) -> Tuple[str, str]:
    env_file = env_value("FEISHU_WEEKLY_ENV_FILE", ".env.local")
    if Path(env_file).exists():
        sender.load_env_file(env_file)
    lookup_id_type = env_value("FEISHU_WEEKLY_EMAIL_LOOKUP_ID_TYPE", "open_id")
    client = sender.FeishuClient(
        app_id=sender.required_env("FEISHU_APP_ID"),
        app_secret=sender.required_env("FEISHU_APP_SECRET"),
        base_url=env_value("FEISHU_BASE_URL", sender.DEFAULT_BASE_URL),
        debug=env_bool("FEISHU_WEEKLY_DEBUG"),
    )
    tenant_token = client.tenant_access_token()
    if identifier_type == "email":
        receive_id = client.lookup_user_id(tenant_token, receive_id_type=lookup_id_type, email=identifier)
    elif identifier_type == "mobile":
        receive_id = client.lookup_user_id(tenant_token, receive_id_type=lookup_id_type, mobile=identifier)
    else:
        raise ValueError("Unsupported lookup recipient type: %s" % identifier_type)
    return lookup_id_type, receive_id


def resolve_typed_recipient(receive_id_type: str, value: str) -> Tuple[str, str]:
    if receive_id_type in DIRECT_RECEIVE_ID_TYPES:
        return receive_id_type, value
    if receive_id_type == "email":
        return lookup_recipient_by_email(value)
    if receive_id_type == "mobile":
        return lookup_recipient_by_mobile(value)
    raise ValueError("Unsupported recipient type: %s" % receive_id_type)


def resolved_recipients_from_env() -> List[Tuple[str, str]]:
    typed_recipients = typed_recipients_from_env()
    if typed_recipients:
        return [resolve_typed_recipient(receive_id_type, value) for receive_id_type, value in typed_recipients]

    receive_ids = receive_ids_from_env()
    if not env_bool("FEISHU_CONTACT_CACHE_ENABLED"):
        receive_id_type = env_value("FEISHU_WEEKLY_RECEIVE_ID_TYPE", "user_id")
        return [(receive_id_type, receive_id) for receive_id in receive_ids]
    cache_path = env_value("FEISHU_CONTACT_CACHE_PATH", contact_cache.DEFAULT_CACHE_PATH)
    cache = contact_cache.load_cache(cache_path)
    receive_id_type = env_value("FEISHU_WEEKLY_RECEIVE_ID_TYPE", "user_id")
    return [(receive_id_type, contact_cache.resolve_receive_id(cache, receive_id, receive_id_type)) for receive_id in receive_ids]


def build_sender_args(receive_id: str, receive_id_type: str) -> List[str]:
    env_file = env_value("FEISHU_WEEKLY_ENV_FILE", ".env.local")
    args = [
        "--env-file",
        env_file,
        "--sheet-url",
        require_env("FEISHU_WEEKLY_SHEET_URL"),
        "--range",
        env_value("FEISHU_WEEKLY_RANGE", "A1:C16"),
        "--receive-id",
        receive_id,
        "--receive-id-type",
        receive_id_type,
        "--title",
        env_value("FEISHU_WEEKLY_TITLE", "项目进展"),
        "--message-format",
        env_value("FEISHU_WEEKLY_MESSAGE_FORMAT", "card"),
        "--send",
    ]
    if env_bool("FEISHU_WEEKLY_SHOW_ALL_MILESTONES"):
        args.append("--show-all-milestones")
    if env_bool("FEISHU_WEEKLY_DEBUG"):
        args.append("--debug")
    return args


def run_from_env() -> int:
    env_file = env_value("FEISHU_WEEKLY_ENV_FILE", ".env.local")
    if Path(env_file).exists():
        sender.load_env_file(env_file)
    if not env_bool("FEISHU_WEEKLY_SEND_ENABLED"):
        print("weekly send skipped: FEISHU_WEEKLY_SEND_ENABLED is not true")
        return 0
    try:
        for receive_id_type, receive_id in resolved_recipients_from_env():
            result = sender.main(build_sender_args(receive_id, receive_id_type))
            if result != 0:
                return result
        return 0
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    return run_from_env()


if __name__ == "__main__":
    raise SystemExit(main())
