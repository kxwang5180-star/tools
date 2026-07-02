#!/usr/bin/env python3
"""Fetch and cache Feishu contacts for recipient resolution."""

import argparse
import json
import os
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

import feishu_sheet_post_sender as sender


DEFAULT_CACHE_PATH = "contacts_cache.json"
ALIAS_FIELDS = (
    "user_id",
    "open_id",
    "union_id",
    "name",
    "en_name",
    "email",
    "enterprise_email",
    "mobile",
    "employee_no",
    "employee_id",
    "job_number",
)


def compact_user(raw_user: Dict[str, Any]) -> Dict[str, str]:
    user = {}  # type: Dict[str, str]
    for field in ALIAS_FIELDS:
        value = raw_user.get(field)
        if value is not None and str(value).strip():
            user[field] = str(value).strip()
    return user


def build_contact_cache(users: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    compact_users = []
    for user in users:
        compact = compact_user(user)
        if compact:
            compact_users.append(compact)
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "users": compact_users,
    }


def save_cache(cache: Dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(cache, handle, ensure_ascii=False, indent=2, sort_keys=True)


def load_cache(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(data.get("users"), list):
        raise ValueError("Contact cache must be a JSON object with a users list")
    return data


def user_aliases(user: Dict[str, str]) -> List[str]:
    aliases = []
    for field in ALIAS_FIELDS:
        value = user.get(field, "").strip()
        if value:
            aliases.append(value)
    return aliases


def resolve_receive_id(cache: Dict[str, Any], identifier: str, receive_id_type: str) -> str:
    target = str(identifier or "").strip()
    if not target:
        raise ValueError("Empty recipient identifier")
    for user in cache.get("users", []):
        if not isinstance(user, dict):
            continue
        aliases = user_aliases(user)
        if target in aliases:
            resolved = str(user.get(receive_id_type) or "").strip()
            if resolved:
                return resolved
            raise ValueError("Contact matched %s but has no %s" % (target, receive_id_type))
    raise ValueError("Recipient %s was not found in contact cache" % target)


def extract_contact_users(response_data: Dict[str, Any]) -> Dict[str, Any]:
    if response_data.get("code") not in (0, None):
        raise sender.FeishuApiError(sender.format_feishu_error(response_data, "Failed to fetch Feishu contacts"))
    data = response_data.get("data") or {}
    users = data.get("items") or data.get("users") or []
    if not isinstance(users, list):
        raise sender.FeishuApiError("Feishu contact response does not contain users")
    return {
        "users": users,
        "has_more": bool(data.get("has_more")),
        "page_token": str(data.get("page_token") or ""),
    }


def fetch_department_users(
    client: sender.FeishuClient,
    tenant_token: str,
    department_id: str,
    department_id_type: str,
    page_size: int,
) -> List[Dict[str, Any]]:
    all_users = []  # type: List[Dict[str, Any]]
    page_token = ""
    while True:
        query = {
            "department_id": department_id,
            "department_id_type": department_id_type,
            "page_size": str(page_size),
        }
        if page_token:
            query["page_token"] = page_token
        data = client.request(
            "GET",
            "/open-apis/contact/v3/users/find_by_department",
            token=tenant_token,
            query=query,
        )
        parsed = extract_contact_users(data)
        all_users.extend(parsed["users"])
        if not parsed["has_more"] or not parsed["page_token"]:
            break
        page_token = parsed["page_token"]
    return all_users


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch Feishu contacts and save a local cache.")
    parser.add_argument("--env-file", default=".env.local")
    parser.add_argument("--base-url", default=os.environ.get("FEISHU_BASE_URL", sender.DEFAULT_BASE_URL))
    parser.add_argument("--department-id", default=os.environ.get("FEISHU_CONTACT_DEPARTMENT_ID", "0"))
    parser.add_argument("--department-id-type", default=os.environ.get("FEISHU_CONTACT_DEPARTMENT_ID_TYPE", "department_id"))
    parser.add_argument("--page-size", type=int, default=int(os.environ.get("FEISHU_CONTACT_PAGE_SIZE", "50")))
    parser.add_argument("--output", default=os.environ.get("FEISHU_CONTACT_CACHE_PATH", DEFAULT_CACHE_PATH))
    parser.add_argument("--debug", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    sender.load_env_file(args.env_file)
    client = sender.FeishuClient(
        app_id=sender.required_env("FEISHU_APP_ID"),
        app_secret=sender.required_env("FEISHU_APP_SECRET"),
        base_url=args.base_url,
        debug=args.debug,
    )
    tenant_token = client.tenant_access_token()
    users = fetch_department_users(
        client,
        tenant_token,
        department_id=args.department_id,
        department_id_type=args.department_id_type,
        page_size=args.page_size,
    )
    cache = build_contact_cache(users)
    save_cache(cache, args.output)
    print(json.dumps({"mode": "cached", "path": args.output, "users": len(cache["users"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
