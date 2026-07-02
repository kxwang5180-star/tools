#!/usr/bin/env python3
"""Read one Feishu Sheet range and send it as a post message with an md tag."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from typing import Any


DEFAULT_BASE_URL = "https://open.feishu.cn"
VALID_RECEIVE_ID_TYPES = {"open_id", "user_id", "union_id", "email", "chat_id"}
BITABLE_RANGE_DEFAULT = {"max_columns": 8, "max_records": 20}
MILESTONE_KEYWORDS = ("里程碑", "节点", "计划时间", "预计时间", "截止时间", "完成时间")


class FeishuApiError(RuntimeError):
    pass


def format_feishu_error(response_data: dict[str, Any], fallback: str) -> str:
    message = response_data.get("msg") or response_data.get("message") or fallback
    return f"{message}（飞书错误码：{response_data.get('code')}）"


def load_env_file(path: str) -> None:
    if not path:
        return
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise FeishuApiError(f"Missing required environment variable: {name}")
    return value


def parse_sheet_url(url: str) -> dict[str, str]:
    parsed = urllib.parse.urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    try:
        sheets_index = parts.index("sheets")
        spreadsheet_token = parts[sheets_index + 1]
    except (ValueError, IndexError) as exc:
        raise ValueError("Sheet URL must contain /sheets/<spreadsheet_token>") from exc

    query = urllib.parse.parse_qs(parsed.query)
    sheet_id = (query.get("sheet") or [""])[0]
    return {
        "spreadsheet_token": spreadsheet_token,
        "sheet_id": sheet_id,
    }


def parse_wiki_url(url: str) -> dict[str, str]:
    parsed = urllib.parse.urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    try:
        wiki_index = parts.index("wiki")
        node_token = parts[wiki_index + 1]
    except (ValueError, IndexError) as exc:
        raise ValueError("Wiki URL must contain /wiki/<node_token>") from exc

    query = urllib.parse.parse_qs(parsed.query)
    table_id = (query.get("table") or query.get("sheet") or [""])[0]
    return {
        "node_token": node_token,
        "table_id": table_id,
    }


def is_wiki_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return "/wiki/" in parsed.path


def column_name_to_number(column_name: str) -> int:
    total = 0
    for char in column_name.upper():
        if not ("A" <= char <= "Z"):
            raise ValueError(f"Invalid column in range: {column_name}")
        total = total * 26 + (ord(char) - ord("A") + 1)
    return total


def parse_a1_range_for_bitable(cell_range: str) -> dict[str, int]:
    value = str(cell_range or "").strip()
    if "!" in value:
        value = value.split("!", 1)[1]
    if ":" not in value:
        return dict(BITABLE_RANGE_DEFAULT)

    start, end = value.split(":", 1)
    start_col = "".join(char for char in start if char.isalpha())
    start_row = "".join(char for char in start if char.isdigit())
    end_col = "".join(char for char in end if char.isalpha())
    end_row = "".join(char for char in end if char.isdigit())
    if not start_col or not end_col or not start_row or not end_row:
        return dict(BITABLE_RANGE_DEFAULT)

    max_columns = column_name_to_number(end_col) - column_name_to_number(start_col) + 1
    max_records = int(end_row) - int(start_row)
    return {
        "max_columns": max(1, max_columns),
        "max_records": max(1, max_records),
    }


def build_range(sheet_id: str, cell_range: str) -> str:
    value = str(cell_range or "").strip()
    if not value:
        raise ValueError("Missing cell range, for example A1:F20")
    if "!" in value:
        return value
    sheet = str(sheet_id or "").strip()
    if not sheet:
        raise ValueError("Missing sheet id. Provide --sheet-id or a sheet URL with ?sheet=...")
    return f"{sheet}!{value}"


def extract_values(response_data: dict[str, Any]) -> list[list[Any]]:
    if response_data.get("code") not in (0, None):
        message = response_data.get("msg") or response_data.get("message") or "Feishu API returned an error"
        raise FeishuApiError(f"{message}（飞书错误码：{response_data.get('code')}）")

    data = response_data.get("data") or {}
    value_range = data.get("valueRange") or data.get("value_range") or {}
    values = value_range.get("values")
    if values is None:
        values = data.get("values")
    if not isinstance(values, list):
        raise FeishuApiError("Feishu Sheet response does not contain values")
    return values


def extract_user_id(response_data: dict[str, Any], receive_id_type: str) -> str:
    if response_data.get("code") not in (0, None):
        message = response_data.get("msg") or response_data.get("message") or "Feishu API returned an error"
        raise FeishuApiError(f"{message}（飞书错误码：{response_data.get('code')}）")

    data = response_data.get("data") or {}
    users = data.get("user_list") or data.get("users") or []
    if not users:
        raise FeishuApiError("No Feishu user found for the provided email or mobile")

    user = users[0]
    value = user.get(receive_id_type) or user.get("user_id") or user.get("open_id")
    if not value:
        raise FeishuApiError(f"Feishu user record does not contain {receive_id_type}")
    return str(value)


def extract_wiki_node(response_data: dict[str, Any]) -> dict[str, Any]:
    if response_data.get("code") not in (0, None):
        message = response_data.get("msg") or response_data.get("message") or "Feishu API returned an error"
        raise FeishuApiError(f"{message}（飞书错误码：{response_data.get('code')}）")
    data = response_data.get("data") or {}
    node = data.get("node") or data
    if not isinstance(node, dict):
        raise FeishuApiError("Wiki node response does not contain node data")
    return node


def extract_bitable_tables(response_data: dict[str, Any]) -> list[dict[str, Any]]:
    if response_data.get("code") not in (0, None):
        message = response_data.get("msg") or response_data.get("message") or "Feishu API returned an error"
        raise FeishuApiError(f"{message}（飞书错误码：{response_data.get('code')}）")
    data = response_data.get("data") or {}
    tables = data.get("items") or data.get("tables") or []
    if not isinstance(tables, list):
        raise FeishuApiError("Bitable table list response does not contain items")
    return tables


def extract_bitable_records(response_data: dict[str, Any]) -> list[dict[str, Any]]:
    if response_data.get("code") not in (0, None):
        message = response_data.get("msg") or response_data.get("message") or "Feishu API returned an error"
        raise FeishuApiError(f"{message}（飞书错误码：{response_data.get('code')}）")
    data = response_data.get("data") or {}
    records = data.get("items") or data.get("records") or []
    if not isinstance(records, list):
        raise FeishuApiError("Bitable record response does not contain items")
    return records


def bitable_cell_to_plain(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(str(item.get("name") or item.get("text") or item.get("email") or item.get("link") or item))
            else:
                parts.append(str(item))
        return ", ".join(part for part in parts if part)
    if isinstance(value, dict):
        return str(value.get("name") or value.get("text") or value.get("email") or value.get("link") or json.dumps(value, ensure_ascii=False))
    return str(value)


def bitable_records_to_values(
    records: list[dict[str, Any]],
    max_columns: int,
    max_records: int,
) -> list[list[Any]]:
    field_names: list[str] = []
    for record in records:
        fields = record.get("fields") or {}
        for field_name in fields.keys():
            if field_name not in field_names:
                field_names.append(field_name)
            if len(field_names) >= max_columns:
                break
        if len(field_names) >= max_columns:
            break
    if not field_names:
        raise FeishuApiError("Bitable records do not contain fields")

    values: list[list[Any]] = [field_names]
    for record in records[:max_records]:
        fields = record.get("fields") or {}
        values.append([bitable_cell_to_plain(fields.get(field_name)) for field_name in field_names])
    return values


def cell_to_text(value: Any, max_cell_length: int = 80) -> str:
    if value is None or value == "":
        text = "-"
    elif isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)

    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
    text = text.replace("|", "\\|")
    if len(text) > max_cell_length:
        text = f"{text[:max_cell_length]}..."
    return text


def normalize_rows(values: list[list[Any]], max_columns: int) -> list[list[Any]]:
    rows = [list(row) if isinstance(row, list) else [row] for row in values]
    if not rows:
        return []
    width = min(max(len(row) for row in rows), max_columns)
    normalized = []
    for row in rows:
        padded = row[:width] + [""] * max(0, width - len(row))
        normalized.append(padded)
    return normalized


def values_to_markdown(
    values: list[list[Any]],
    max_rows: int = 20,
    max_columns: int = 8,
    max_cell_length: int = 80,
) -> str:
    rows = normalize_rows(values, max_columns=max_columns)
    if not rows:
        raise ValueError("Sheet range is empty")

    header = [cell_to_text(cell, max_cell_length) for cell in rows[0]]
    data_rows = rows[1 : max_rows + 1]

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]
    for row in data_rows:
        lines.append("| " + " | ".join(cell_to_text(cell, max_cell_length) for cell in row) + " |")

    hidden = max(0, len(rows) - 1 - len(data_rows))
    if hidden:
        lines.append("")
        lines.append(f"> 仅展示前 {len(data_rows)} 行，另有 {hidden} 行未展示。")
    return "\n".join(lines)


def parse_date_candidates(text: str, today: date | None = None) -> list[date]:
    base = today or date.today()
    value = str(text or "")
    results: list[date] = []
    patterns = [
        r"(?P<year>\d{4})[-/.年](?P<month>\d{1,2})[-/.月](?P<day>\d{1,2})",
        r"(?P<month>\d{1,2})月(?P<day>\d{1,2})日?",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, value):
            year = int(match.groupdict().get("year") or base.year)
            month = int(match.group("month"))
            day = int(match.group("day"))
            try:
                results.append(date(year, month, day))
            except ValueError:
                continue
    return results


def is_milestone_table(values: list[list[Any]]) -> bool:
    if not values:
        return False
    header_text = " ".join(str(cell or "") for cell in values[0])
    return any(keyword in header_text for keyword in MILESTONE_KEYWORDS)


def filter_nearest_milestone(values: list[list[Any]], today: date | None = None) -> list[list[Any]]:
    if len(values) <= 2 or not is_milestone_table(values):
        return values

    base = today or date.today()
    nearest: tuple[int, int, list[Any]] | None = None
    for index, row in enumerate(values[1:]):
        row_dates: list[date] = []
        for cell in row:
            row_dates.extend(parse_date_candidates(str(cell or ""), today=base))
        if not row_dates:
            continue
        distance = min(abs((item - base).days) for item in row_dates)
        candidate = (distance, index, row)
        if nearest is None or candidate < nearest:
            nearest = candidate

    if nearest is None:
        return values
    return [values[0], nearest[2]]


def build_markdown_message(
    title: str,
    values: list[list[Any]],
    max_rows: int,
    max_columns: int,
    max_cell_length: int,
    generated_at: str | None = None,
) -> str:
    rows = normalize_rows(values, max_columns=max_columns)
    data_count = max(0, len(rows) - 1)
    generated = generated_at or datetime.now().strftime("%Y-%m-%d %H:%M")
    parts = [
        f"**{title}**",
        "",
        f"更新时间：{generated}",
        f"数据范围：{data_count} 条",
        "",
        values_to_markdown(rows, max_rows=max_rows, max_columns=max_columns, max_cell_length=max_cell_length),
    ]
    return "\n".join(parts)


def build_post_message_payload(
    receive_id: str,
    receive_id_type: str,
    title: str,
    markdown: str,
    uuid: str = "",
) -> dict[str, Any]:
    if receive_id_type not in VALID_RECEIVE_ID_TYPES:
        allowed = ", ".join(sorted(VALID_RECEIVE_ID_TYPES))
        raise ValueError(f"Unsupported receive_id_type: {receive_id_type}. Allowed: {allowed}")

    content = {
        "zh_cn": {
            "title": title,
            "content": [
                [
                    {
                        "tag": "md",
                        "text": markdown,
                    }
                ]
            ],
        }
    }
    payload: dict[str, Any] = {
        "receive_id": receive_id,
        "msg_type": "post",
        "content": json.dumps(content, ensure_ascii=False),
    }
    if uuid:
        payload["uuid"] = uuid[:50]
    return payload


def plain_text(content: str) -> dict[str, str]:
    return {
        "tag": "plain_text",
        "content": str(content or ""),
    }


def build_card_message_payload(
    receive_id: str,
    receive_id_type: str,
    title: str,
    markdown: str,
    uuid: str = "",
) -> dict[str, Any]:
    if receive_id_type not in VALID_RECEIVE_ID_TYPES:
        allowed = ", ".join(sorted(VALID_RECEIVE_ID_TYPES))
        raise ValueError(f"Unsupported receive_id_type: {receive_id_type}. Allowed: {allowed}")

    card = {
        "schema": "2.0",
        "config": {
            "update_multi": True,
            "style": {
                "text_size": {
                    "normal_v2": {
                        "default": "normal",
                        "pc": "normal",
                        "mobile": "heading",
                    },
                },
            },
        },
        "body": {
            "elements": [
                {
                    "tag": "markdown",
                    "element_id": "md_table",
                    "content": markdown,
                    "text_align": "left",
                    "text_size": "normal_v2",
                    "margin": "0px 0px 0px 0px",
                },
            ],
        },
        "header": {
            "title": plain_text(title),
            "subtitle": plain_text("自动读取飞书表格生成"),
            "template": "blue",
        },
    }
    payload: dict[str, Any] = {
        "receive_id": receive_id,
        "msg_type": "interactive",
        "content": json.dumps(card, ensure_ascii=False),
    }
    if uuid:
        payload["uuid"] = uuid[:50]
    return payload


class FeishuClient:
    def __init__(self, app_id: str, app_secret: str, base_url: str = DEFAULT_BASE_URL, debug: bool = False) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = base_url.rstrip("/")
        self.debug = debug

    def request(
        self,
        method: str,
        path: str,
        token: str = "",
        body: dict[str, Any] | None = None,
        query: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"
        if self.debug:
            print(f"[debug] request {method} {path} query={query or {}} body_keys={sorted((body or {}).keys())}", file=sys.stderr)

        headers = {"Content-Type": "application/json; charset=utf-8"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise FeishuApiError(f"HTTP {exc.code}: {raw}") from exc
        except urllib.error.URLError as exc:
            raise FeishuApiError(f"Network error: {exc.reason}") from exc

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise FeishuApiError(f"Feishu API returned non-JSON response: {raw[:200]}") from exc
        if self.debug:
            print(
                f"[debug] response {method} {path} code={parsed.get('code')} msg={parsed.get('msg') or parsed.get('message')}",
                file=sys.stderr,
            )
        return parsed

    def tenant_access_token(self) -> str:
        data = self.request(
            "POST",
            "/open-apis/auth/v3/tenant_access_token/internal",
            body={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        if data.get("code") != 0:
            raise FeishuApiError(format_feishu_error(data, "Failed to fetch tenant access token"))
        token = data.get("tenant_access_token", "")
        if not token:
            raise FeishuApiError("Feishu tenant access token is empty")
        return token

    def read_sheet_range(self, tenant_token: str, spreadsheet_token: str, range_ref: str) -> list[list[Any]]:
        encoded_token = urllib.parse.quote(spreadsheet_token, safe="")
        encoded_range = urllib.parse.quote(range_ref, safe="")
        data = self.request(
            "GET",
            f"/open-apis/sheets/v2/spreadsheets/{encoded_token}/values/{encoded_range}",
            token=tenant_token,
        )
        return extract_values(data)

    def get_wiki_node(self, tenant_token: str, node_token: str) -> dict[str, Any]:
        data = self.request(
            "GET",
            "/open-apis/wiki/v2/spaces/get_node",
            token=tenant_token,
            query={"token": node_token, "obj_type": "wiki"},
        )
        return extract_wiki_node(data)

    def list_bitable_tables(self, tenant_token: str, app_token: str) -> list[dict[str, Any]]:
        encoded_app_token = urllib.parse.quote(app_token, safe="")
        data = self.request(
            "GET",
            f"/open-apis/bitable/v1/apps/{encoded_app_token}/tables",
            token=tenant_token,
            query={"page_size": "100"},
        )
        return extract_bitable_tables(data)

    def read_bitable_records(
        self,
        tenant_token: str,
        app_token: str,
        table_id: str,
        page_size: int,
    ) -> list[dict[str, Any]]:
        encoded_app_token = urllib.parse.quote(app_token, safe="")
        encoded_table_id = urllib.parse.quote(table_id, safe="")
        data = self.request(
            "GET",
            f"/open-apis/bitable/v1/apps/{encoded_app_token}/tables/{encoded_table_id}/records",
            token=tenant_token,
            query={"page_size": str(page_size)},
        )
        return extract_bitable_records(data)

    def send_post_message(
        self,
        tenant_token: str,
        receive_id_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        data = self.request(
            "POST",
            "/open-apis/im/v1/messages",
            token=tenant_token,
            query={"receive_id_type": receive_id_type},
            body=payload,
        )
        if data.get("code") != 0:
            raise FeishuApiError(format_feishu_error(data, "Failed to send Feishu message"))
        return data.get("data") or {}

    def lookup_user_id(
        self,
        tenant_token: str,
        receive_id_type: str,
        email: str = "",
        mobile: str = "",
    ) -> str:
        body: dict[str, list[str]] = {}
        if email:
            body["emails"] = [email]
        if mobile:
            body["mobiles"] = [mobile]
        if not body:
            raise ValueError("Provide email or mobile for recipient lookup")
        data = self.request(
            "POST",
            "/open-apis/contact/v3/users/batch_get_id",
            token=tenant_token,
            body=body,
        )
        return extract_user_id(data, receive_id_type)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read one Feishu Sheet range and send it as a post message with an md table."
    )
    parser.add_argument("--env-file", default="", help="Optional env file containing FEISHU_APP_ID and FEISHU_APP_SECRET")
    parser.add_argument("--base-url", default=os.environ.get("FEISHU_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--sheet-url", default="", help="Feishu Sheet URL, used to parse spreadsheet token and sheet id")
    parser.add_argument("--spreadsheet-token", default="", help="Spreadsheet token, if --sheet-url is not used")
    parser.add_argument("--sheet-id", default="", help="Worksheet id, if not present in --sheet-url")
    parser.add_argument("--table-id", default="", help="Bitable table id. Used for wiki/bitable URLs; defaults to table/sheet query parameter or first table")
    parser.add_argument("--range", required=True, help="Cell range like A1:F20 or full range like sheetId!A1:F20")
    parser.add_argument("--receive-id", default="", help="Target user/chat id. Optional when --lookup-email or --lookup-mobile is used")
    parser.add_argument("--receive-id-type", default="open_id", choices=sorted(VALID_RECEIVE_ID_TYPES))
    parser.add_argument("--lookup-email", default="", help="Look up target user id by email before sending")
    parser.add_argument("--lookup-mobile", default="", help="Look up target user id by mobile before sending")
    parser.add_argument("--title", default="飞书表格消息")
    parser.add_argument("--max-rows", type=int, default=20)
    parser.add_argument("--max-columns", type=int, default=8)
    parser.add_argument("--max-cell-length", type=int, default=80)
    parser.add_argument("--message-format", default="post", choices=["post", "card"], help="Send as post md message or interactive card")
    parser.add_argument("--show-all-milestones", action="store_true", help="Do not auto-filter milestone tables to the nearest dated row")
    parser.add_argument("--uuid", default="", help="Optional Feishu message dedupe id, max 50 chars")
    parser.add_argument("--debug", action="store_true", help="Print Feishu API request path and response code for troubleshooting")
    parser.add_argument("--send", action="store_true", help="Actually send. Without this flag, only print a dry-run payload.")
    return parser


def resolve_sheet_args(args: argparse.Namespace) -> tuple[str, str, str]:
    parsed = {"spreadsheet_token": "", "sheet_id": ""}
    if args.sheet_url:
        parsed = parse_sheet_url(args.sheet_url)

    spreadsheet_token = args.spreadsheet_token or parsed["spreadsheet_token"]
    sheet_id = args.sheet_id or parsed["sheet_id"]
    if not spreadsheet_token:
        raise ValueError("Provide --sheet-url or --spreadsheet-token")
    return spreadsheet_token, sheet_id, build_range(sheet_id, args.range)


def read_values_from_source(
    client: FeishuClient,
    tenant_token: str,
    args: argparse.Namespace,
) -> list[list[Any]]:
    if args.sheet_url and is_wiki_url(args.sheet_url):
        parsed = parse_wiki_url(args.sheet_url)
        node = client.get_wiki_node(tenant_token, parsed["node_token"])
        obj_type = str(node.get("obj_type") or "")
        obj_token = str(node.get("obj_token") or "")
        if not obj_token:
            raise FeishuApiError("Wiki node does not contain obj_token")

        if obj_type == "sheet":
            sheet_id = args.sheet_id or parsed["table_id"]
            range_ref = build_range(sheet_id, args.range)
            return client.read_sheet_range(tenant_token, obj_token, range_ref)

        if obj_type != "bitable":
            raise FeishuApiError(f"Wiki node obj_type is {obj_type}, not sheet or bitable")

        app_token = obj_token
        if not app_token:
            raise FeishuApiError("Wiki node does not contain obj_token for bitable app_token")

        table_id = args.table_id or parsed["table_id"]
        if not table_id:
            tables = client.list_bitable_tables(tenant_token, app_token)
            if not tables:
                raise FeishuApiError("Bitable app does not contain tables")
            table_id = str(tables[0].get("table_id") or "")
        if not table_id:
            raise FeishuApiError("Missing bitable table id")

        limits = parse_a1_range_for_bitable(args.range)
        max_columns = min(args.max_columns, limits["max_columns"])
        max_records = min(args.max_rows, limits["max_records"])
        records = client.read_bitable_records(
            tenant_token,
            app_token=app_token,
            table_id=table_id,
            page_size=max_records,
        )
        return bitable_records_to_values(records, max_columns=max_columns, max_records=max_records)

    spreadsheet_token, _sheet_id, range_ref = resolve_sheet_args(args)
    return client.read_sheet_range(tenant_token, spreadsheet_token, range_ref)


def run(args: argparse.Namespace) -> int:
    load_env_file(args.env_file)

    client = FeishuClient(
        app_id=required_env("FEISHU_APP_ID"),
        app_secret=required_env("FEISHU_APP_SECRET"),
        base_url=args.base_url,
        debug=args.debug,
    )
    tenant_token = client.tenant_access_token()
    receive_id = args.receive_id
    if args.lookup_email or args.lookup_mobile:
        if args.receive_id_type in {"chat_id", "email"}:
            raise ValueError("--lookup-email/--lookup-mobile must be used with open_id, user_id, or union_id")
        receive_id = client.lookup_user_id(
            tenant_token,
            receive_id_type=args.receive_id_type,
            email=args.lookup_email,
            mobile=args.lookup_mobile,
        )
    if not receive_id:
        raise ValueError("Provide --receive-id, or use --lookup-email/--lookup-mobile")

    values = read_values_from_source(client, tenant_token, args)
    if not args.show_all_milestones:
        values = filter_nearest_milestone(values)
    markdown = build_markdown_message(
        title=args.title,
        values=values,
        max_rows=args.max_rows,
        max_columns=args.max_columns,
        max_cell_length=args.max_cell_length,
    )
    if args.message_format == "card":
        payload = build_card_message_payload(
            receive_id=receive_id,
            receive_id_type=args.receive_id_type,
            title=args.title,
            markdown=markdown,
            uuid=args.uuid,
        )
    else:
        payload = build_post_message_payload(
            receive_id=receive_id,
            receive_id_type=args.receive_id_type,
            title=args.title,
            markdown=markdown,
            uuid=args.uuid,
        )

    if not args.send:
        print(json.dumps({"mode": "dry_run", "receive_id_type": args.receive_id_type, "payload": payload}, ensure_ascii=False, indent=2))
        return 0

    result = client.send_post_message(tenant_token, args.receive_id_type, payload)
    print(json.dumps({"mode": "sent", "result": result}, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (FeishuApiError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
