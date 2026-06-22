from __future__ import annotations

import argparse
import base64
import cgi
import json
import mimetypes
import os
import re
import secrets
import shutil
import uuid
import zipfile
from io import BytesIO
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import unquote, urlparse

from .adapter import MockFinanceSystemAdapter
from .agent import BillingAgent
from .engine import process_batch
from .models import AuditEvent, BillingBatch, now_iso, to_dict
from .storage import AppStorage
from .template import export_upload_template_csv, export_upload_template_xlsx


BASE_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = Path(os.environ.get("FINANCE_AGENT_DATA_DIR", BASE_DIR / "data"))
UPLOADS_DIR = Path(os.environ.get("FINANCE_AGENT_UPLOADS_DIR", BASE_DIR / "uploads"))
INVOICE_FILE_SUFFIXES = {".pdf", ".ofd", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}


class FinanceAgentHandler(SimpleHTTPRequestHandler):
    server_version = "FinanceQuarterlyBillingAgent/0.1"

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if not self._authorize(path):
            return
        try:
            if path == "/api/health":
                self._send_json({"status": "ok", "service": "finance-quarterly-billing-agent"})
            elif path == "/api/config":
                self._send_json(self._storage().load_config())
            elif path == "/api/batches":
                batches = [self._batch_summary(batch) for batch in self._storage().list_batches()]
                self._send_json({"batches": batches})
            elif re.fullmatch(r"/api/batches/[^/]+", path):
                batch = self._storage().load_batch(_last_path_part(path))
                self._send_json(self._batch_payload(batch))
            elif re.fullmatch(r"/api/batches/[^/]+/template", path):
                self._send_template(_path_part(path, -2))
            elif re.fullmatch(r"/api/batches/[^/]+/invoices", path):
                self._send_invoice_package(_path_part(path, -2), package_type="organized")
            elif re.fullmatch(r"/api/batches/[^/]+/company-workbooks", path):
                self._send_company_workbook_package(_path_part(path, -2))
            else:
                self._serve_static(path)
        except KeyError:
            self._send_json({"error": "not_found", "message": "批次不存在。"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:  # pragma: no cover - defensive HTTP boundary
            self._send_json(
                {"error": "server_error", "message": str(exc)},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if not self._authorize(path):
            return
        try:
            if path == "/api/batches":
                self._handle_create_batch()
            elif re.fullmatch(r"/api/batches/[^/]+/submit", path):
                self._handle_submit_batch(_path_part(path, -2))
            else:
                self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
        except KeyError:
            self._send_json({"error": "not_found", "message": "批次不存在。"}, HTTPStatus.NOT_FOUND)
        except ValueError as exc:
            self._send_json({"error": "invalid_request", "message": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # pragma: no cover - defensive HTTP boundary
            self._send_json(
                {"error": "server_error", "message": str(exc)},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        if not self._authorize(path):
            return
        try:
            if path == "/api/config":
                self._require_admin()
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8")
                config = json.loads(raw or "{}")
                self._storage().save_config(config)
                self._send_json(self._storage().load_config())
            else:
                self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
        except PermissionError as exc:
            self._send_json({"error": "forbidden", "message": str(exc)}, HTTPStatus.FORBIDDEN)
        except json.JSONDecodeError:
            self._send_json(
                {"error": "invalid_json", "message": "配置不是有效 JSON。"},
                HTTPStatus.BAD_REQUEST,
            )

    def _handle_create_batch(self) -> None:
        form = self._read_multipart()
        batch_id = uuid.uuid4().hex[:12]
        batch_dir = UPLOADS_DIR / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)

        source_item = _first_file(_form_item(form, "service_excel"))
        if source_item is None:
            raise ValueError("请上传服务费 Excel。")

        quarter = _field_value(form, "quarter") or "未指定季度"
        created_by = _field_value(form, "created_by") or self._actor()
        source_path = _save_uploaded_file(source_item, batch_dir, "service_fee")

        template_path: Optional[Path] = None
        template_item = _first_file(_form_item(form, "upload_template"))
        if template_item is not None and template_item.filename:
            template_path = _save_uploaded_file(template_item, batch_dir, "upload_template")

        structure_path: Optional[Path] = None
        structure_item = _first_file(_form_item(form, "company_structure"))
        if structure_item is not None and structure_item.filename:
            structure_path = _save_uploaded_file(structure_item, batch_dir, "company_structure")

        uploaded_invoice_paths: List[Path] = []
        for item in _files(_form_item(form, "invoices")):
            if item.filename:
                uploaded_invoice_paths.append(
                    _save_uploaded_file(item, batch_dir / "invoice_uploads", "invoice")
                )
        invoice_paths = _expand_invoice_uploads(uploaded_invoice_paths, batch_dir / "invoices")

        config = self._storage().load_config()
        batch = process_batch(
            batch_id=batch_id,
            name=f"{quarter} 服务费季度账单",
            source_file=source_path,
            invoice_files=invoice_paths,
            template_file=template_path,
            quarter=quarter,
            created_by=created_by,
            config=config,
            structure_file=structure_path,
            organized_invoice_dir=batch_dir / "organized_invoices",
            company_workbook_dir=batch_dir / "company_workbooks",
        )
        next_actions = BillingAgent().explain_next_actions(batch)
        batch.audit_events.append(
            AuditEvent(
                event_type="agent_next_actions",
                actor="billing-agent",
                message="Agent 已生成下一步处理建议。",
                detail={"next_actions": next_actions},
            )
        )
        self._storage().save_batch(batch)
        self._send_json(self._batch_payload(batch), HTTPStatus.CREATED)

    def _handle_submit_batch(self, batch_id: str) -> None:
        role = self._role()
        if role not in {"operator", "admin"}:
            raise PermissionError("当前角色没有提交权限。")
        batch = self._storage().load_batch(batch_id)
        adapter = MockFinanceSystemAdapter(self._storage().load_config())
        adapter.submit_batch(batch, self._actor())
        self._storage().save_batch(batch)
        self._send_json(self._batch_payload(batch))

    def _send_template(self, batch_id: str) -> None:
        batch = self._storage().load_batch(batch_id)
        config = self._storage().load_config()
        try:
            payload = export_upload_template_xlsx(batch, config)
            file_name = f"{batch.quarter}-服务费上传模板.xlsx"
            self.send_response(HTTPStatus.OK)
            self.send_header(
                "Content-Type",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{_url_quote(file_name)}")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except RuntimeError:
            payload = export_upload_template_csv(batch, config).encode("utf-8-sig")
            file_name = f"{batch.quarter}-服务费上传模板.csv"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{_url_quote(file_name)}")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    def _send_invoice_package(self, batch_id: str, package_type: str) -> None:
        batch = self._storage().load_batch(batch_id)
        source_dir = batch.organized_invoice_dir
        if not source_dir:
            self._send_json(
                {"error": "not_found", "message": "本批次没有整理后的发票文件。"},
                HTTPStatus.NOT_FOUND,
            )
            return
        invoice_dir = Path(source_dir)
        if not invoice_dir.exists() or not invoice_dir.is_dir():
            self._send_json(
                {"error": "not_found", "message": "整理后的发票文件夹不存在。"},
                HTTPStatus.NOT_FOUND,
            )
            return

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for file_path in sorted(invoice_dir.rglob("*")):
                if file_path.is_file():
                    archive.write(file_path, file_path.relative_to(invoice_dir))
        payload = buffer.getvalue()
        file_name = f"{batch.quarter}-按二级公司整理发票包.zip"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{_url_quote(file_name)}")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_company_workbook_package(self, batch_id: str) -> None:
        batch = self._storage().load_batch(batch_id)
        if not batch.company_workbook_dir:
            self._send_json(
                {"error": "not_found", "message": "本批次没有二级公司明细表。"},
                HTTPStatus.NOT_FOUND,
            )
            return
        workbook_dir = Path(batch.company_workbook_dir)
        if not workbook_dir.exists() or not workbook_dir.is_dir():
            self._send_json(
                {"error": "not_found", "message": "二级公司明细表文件夹不存在。"},
                HTTPStatus.NOT_FOUND,
            )
            return
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for file_path in sorted(workbook_dir.rglob("*.xlsx")):
                archive.write(file_path, file_path.relative_to(workbook_dir))
        payload = buffer.getvalue()
        file_name = f"{batch.quarter}-二级公司明细表包.zip"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{_url_quote(file_name)}")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_multipart(self) -> cgi.FieldStorage:
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            raise ValueError("请求必须是 multipart/form-data。")
        return cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
            },
        )

    def _serve_static(self, path: str) -> None:
        if path == "/":
            file_path = STATIC_DIR / "index.html"
        else:
            safe = unquote(path).lstrip("/")
            file_path = STATIC_DIR / safe
        if not file_path.exists() or not file_path.is_file() or STATIC_DIR not in file_path.resolve().parents:
            self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        payload = file_path.read_bytes()
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _storage(self) -> AppStorage:
        return AppStorage(DATA_DIR)

    def _authorize(self, path: str) -> bool:
        if path == "/api/health":
            return True
        user = os.environ.get("FINANCE_AGENT_BASIC_AUTH_USER", "finance")
        password = os.environ.get("FINANCE_AGENT_BASIC_AUTH_PASSWORD", "")
        if not password:
            return True
        header = self.headers.get("Authorization", "")
        prefix = "Basic "
        if not header.startswith(prefix):
            self._send_auth_required()
            return False
        try:
            decoded = base64.b64decode(header[len(prefix) :]).decode("utf-8")
        except Exception:
            self._send_auth_required()
            return False
        provided_user, _, provided_password = decoded.partition(":")
        if _safe_compare(provided_user, user) and _safe_compare(provided_password, password):
            return True
        self._send_auth_required()
        return False

    def _send_auth_required(self) -> None:
        body = json.dumps(
            {"error": "unauthorized", "message": "请先登录。"},
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", 'Basic realm="Finance Agent"')
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _role(self) -> str:
        return self.headers.get("X-Role", "operator")

    def _actor(self) -> str:
        return unquote(self.headers.get("X-User", "%E7%BB%8F%E5%8A%9E%E4%BA%BA"))

    def _require_admin(self) -> None:
        if self._role() != "admin":
            raise PermissionError("只有管理员可以维护配置。")

    def _batch_payload(self, batch: BillingBatch) -> Dict[str, Any]:
        payload = to_dict(batch)
        payload["template_download_url"] = f"/api/batches/{batch.id}/template"
        if batch.organized_invoice_dir:
            payload["invoice_package_download_url"] = f"/api/batches/{batch.id}/invoices"
        if batch.company_workbook_dir:
            payload["company_workbook_download_url"] = f"/api/batches/{batch.id}/company-workbooks"
        payload["next_actions"] = BillingAgent().explain_next_actions(batch)
        return payload

    def _batch_summary(self, batch: BillingBatch) -> Dict[str, Any]:
        return {
            "id": batch.id,
            "name": batch.name,
            "quarter": batch.quarter,
            "status": batch.status,
            "created_by": batch.created_by,
            "created_at": batch.created_at,
            "updated_at": batch.updated_at,
            "line_count": batch.line_count,
            "company_count": batch.company_count,
            "issue_count": len(batch.issues),
            "blocking_issue_count": sum(1 for issue in batch.issues if issue.severity == "error"),
        }

    def _send_json(self, payload: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def _field_value(form: cgi.FieldStorage, name: str) -> str:
    item = form.getfirst(name)
    return str(item).strip() if item is not None else ""


def _safe_compare(left: str, right: str) -> bool:
    return secrets.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def _form_item(form: cgi.FieldStorage, name: str) -> Any:
    if name not in form:
        return None
    return form[name]


def _files(value: Any) -> List[cgi.FieldStorage]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if getattr(item, "filename", None)]
    return [value] if getattr(value, "filename", None) else []


def _first_file(value: Any) -> Optional[cgi.FieldStorage]:
    files = _files(value)
    return files[0] if files else None


def _save_uploaded_file(item: cgi.FieldStorage, target_dir: Path, prefix: str) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    original = _uploaded_basename(item.filename or f"{prefix}.bin")
    safe_name = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", original)
    target = target_dir / safe_name
    if target.exists():
        target = target_dir / f"{uuid.uuid4().hex[:6]}_{safe_name}"
    with target.open("wb") as handle:
        shutil.copyfileobj(item.file, handle)
    return target


def _expand_invoice_uploads(uploaded_paths: List[Path], target_dir: Path) -> List[Path]:
    invoice_paths: List[Path] = []
    target_dir.mkdir(parents=True, exist_ok=True)
    for uploaded_path in uploaded_paths:
        if uploaded_path.suffix.lower() == ".zip":
            invoice_paths.extend(_extract_invoice_zip(uploaded_path, target_dir / uploaded_path.stem))
        elif _is_invoice_file(uploaded_path):
            invoice_paths.append(uploaded_path)
    return invoice_paths


def _extract_invoice_zip(zip_path: Path, target_dir: Path) -> List[Path]:
    if not zipfile.is_zipfile(zip_path):
        raise ValueError(f"压缩包无法读取：{zip_path.name}")
    extracted_paths: List[Path] = []
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            member_name = member.filename.replace("\\", "/")
            if member_name.startswith("__MACOSX/") or "/__MACOSX/" in member_name:
                continue
            source_name = _uploaded_basename(member_name)
            if not source_name or source_name.startswith("."):
                continue
            if not _is_invoice_name(source_name):
                continue
            target = _unique_path(target_dir, source_name)
            with archive.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            extracted_paths.append(target)
    return extracted_paths


def _uploaded_basename(file_name: str) -> str:
    normalized = file_name.replace("\\", "/")
    return Path(normalized).name


def _is_invoice_file(path: Path) -> bool:
    return _is_invoice_name(path.name)


def _is_invoice_name(file_name: str) -> bool:
    return Path(file_name).suffix.lower() in INVOICE_FILE_SUFFIXES


def _unique_path(target_dir: Path, file_name: str) -> Path:
    safe_name = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", file_name)
    target = target_dir / safe_name
    if not target.exists():
        return target
    return target_dir / f"{uuid.uuid4().hex[:6]}_{safe_name}"


def _last_path_part(path: str) -> str:
    return _path_part(path, -1)


def _path_part(path: str, index: int) -> str:
    parts = [part for part in path.split("/") if part]
    return parts[index]


def _url_quote(value: str) -> str:
    from urllib.parse import quote

    return quote(value.encode("utf-8"))


def run(port: int, host: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((host, port), FinanceAgentHandler)
    print(f"Finance quarterly billing agent running at http://{host}:{port}")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8787")))
    args = parser.parse_args()
    run(args.port, args.host)


if __name__ == "__main__":
    main()
