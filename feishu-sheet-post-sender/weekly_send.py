#!/usr/bin/env python3
"""Run the project progress sender from environment settings for schedulers."""

import os
import sys
from pathlib import Path
from typing import List

import contact_cache
import feishu_sheet_post_sender as sender


TRUE_VALUES = {"1", "true", "yes", "y", "on"}


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


def receive_ids_from_env() -> List[str]:
    raw_ids = env_value("FEISHU_WEEKLY_RECEIVE_IDS")
    if not raw_ids:
        raw_ids = require_env("FEISHU_WEEKLY_RECEIVE_ID")
    receive_ids = [item.strip() for item in raw_ids.split(",") if item.strip()]
    if not receive_ids:
        raise ValueError("Missing required environment variable: FEISHU_WEEKLY_RECEIVE_ID or FEISHU_WEEKLY_RECEIVE_IDS")
    return receive_ids


def resolved_receive_ids_from_env() -> List[str]:
    receive_ids = receive_ids_from_env()
    if not env_bool("FEISHU_CONTACT_CACHE_ENABLED"):
        return receive_ids
    cache_path = env_value("FEISHU_CONTACT_CACHE_PATH", contact_cache.DEFAULT_CACHE_PATH)
    cache = contact_cache.load_cache(cache_path)
    receive_id_type = env_value("FEISHU_WEEKLY_RECEIVE_ID_TYPE", "user_id")
    return [contact_cache.resolve_receive_id(cache, receive_id, receive_id_type) for receive_id in receive_ids]


def build_sender_args(receive_id: str) -> List[str]:
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
        env_value("FEISHU_WEEKLY_RECEIVE_ID_TYPE", "user_id"),
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
        for receive_id in resolved_receive_ids_from_env():
            result = sender.main(build_sender_args(receive_id))
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
