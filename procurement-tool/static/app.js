const state = {
  role: localStorage.getItem("financeAgentRole") || "operator",
  user: localStorage.getItem("financeAgentUser") || "经办人",
  config: null,
  activeBatch: null,
  activeTab: "issues",
};

const els = {
  serviceState: document.querySelector("#serviceState"),
  pageTitle: document.querySelector("#pageTitle"),
  uploadForm: document.querySelector("#uploadForm"),
  activeBatchPanel: document.querySelector("#activeBatchPanel"),
  historyList: document.querySelector("#historyList"),
  configEditor: document.querySelector("#configEditor"),
  roleSelect: document.querySelector("#roleSelect"),
  userName: document.querySelector("#userName"),
  toast: document.querySelector("#toast"),
  adminLockNotice: document.querySelector("#adminLockNotice"),
  adminNavItem: document.querySelector(".admin-only"),
};

function headers(extra = {}) {
  return {
    "X-Role": state.role,
    "X-User": encodeURIComponent(state.user),
    ...extra,
  };
}

async function api(path, options = {}) {
  if (typeof window.fetch === "function") {
    const response = await fetch(path, {
      ...options,
      headers: headers(options.headers || {}),
    });
    const contentType = response.headers.get("Content-Type") || "";
    const payload = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      throw new Error(payload.message || payload.error || "请求失败");
    }
    return payload;
  }
  return xhrApi(path, options);
}

function xhrApi(path, options = {}) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open(options.method || "GET", path);
    const requestHeaders = headers(options.headers || {});
    Object.entries(requestHeaders).forEach(([key, value]) => {
      if (!(options.body instanceof FormData) || key.toLowerCase() !== "content-type") {
        request.setRequestHeader(key, value);
      }
    });
    request.onload = () => {
      const contentType = request.getResponseHeader("Content-Type") || "";
      const payload = contentType.includes("application/json")
        ? JSON.parse(request.responseText || "{}")
        : request.responseText;
      if (request.status < 200 || request.status >= 300) {
        reject(new Error(payload.message || payload.error || "请求失败"));
        return;
      }
      resolve(payload);
    };
    request.onerror = () => reject(new Error("无法连接服务。"));
    request.send(options.body || null);
  });
}

async function boot() {
  els.roleSelect.value = state.role;
  els.userName.value = state.user;
  bindEvents();
  renderAdminAccess();
  await health();
  if (state.role === "admin") {
    await loadConfig();
  }
  await loadHistory();
}

function bindEvents() {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.view));
  });

  els.roleSelect.addEventListener("change", async () => {
    state.role = els.roleSelect.value;
    localStorage.setItem("financeAgentRole", state.role);
    renderAdminAccess();
    if (state.role !== "admin" && document.querySelector("#adminView").classList.contains("active")) {
      switchView("workspace");
    }
    if (state.role === "admin") {
      await loadConfig();
    }
  });

  els.userName.addEventListener("input", () => {
    state.user = els.userName.value || "经办人";
    localStorage.setItem("financeAgentUser", state.user);
  });

  els.uploadForm.addEventListener("submit", handleUpload);
  document.querySelectorAll("[data-invoice-mode]").forEach((button) => {
    button.addEventListener("click", () => setInvoiceMode(button.dataset.invoiceMode));
  });
  document.querySelector("#refreshHistory").addEventListener("click", loadHistory);
  document.querySelector("#saveConfig").addEventListener("click", saveConfig);
}

function setInvoiceMode(mode) {
  document.querySelectorAll("[data-invoice-mode]").forEach((button) => {
    const active = button.dataset.invoiceMode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll("[data-invoice-panel]").forEach((panel) => {
    const active = panel.dataset.invoicePanel === mode;
    panel.hidden = !active;
    panel.querySelectorAll("input").forEach((input) => {
      input.disabled = !active;
      if (!active) {
        input.value = "";
      }
    });
  });
}

async function health() {
  try {
    await api("/api/health");
    els.serviceState.textContent = "服务正常";
  } catch (error) {
    els.serviceState.textContent = "连接失败";
    showToast(error.message);
  }
}

async function loadConfig() {
  state.config = await api("/api/config");
  els.configEditor.value = JSON.stringify(state.config, null, 2);
  renderAdminAccess();
}

async function loadHistory() {
  const payload = await api("/api/batches");
  renderHistory(payload.batches || []);
}

async function handleUpload(event) {
  event.preventDefault();
  const formData = new FormData(els.uploadForm);
  const year = formData.get("period_year");
  const quarter = formData.get("period_quarter");
  formData.set("quarter", `${year} ${quarter}`);
  formData.set("created_by", state.user);
  const button = els.uploadForm.querySelector("button[type='submit']");
  button.disabled = true;
  button.textContent = "解析中";
  try {
    const batch = await api("/api/batches", { method: "POST", body: formData });
    state.activeBatch = batch;
    state.activeTab = "issues";
    renderActiveBatch();
    await loadHistory();
    showToast("批次已生成，请复核汇总和异常。");
  } catch (error) {
    showToast(error.message);
  } finally {
    button.disabled = false;
    button.textContent = "解析并生成批次";
  }
}

function switchView(view) {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  document.querySelectorAll(".view").forEach((panel) => panel.classList.remove("active"));
  document.querySelector(`#${view}View`).classList.add("active");
  const titles = {
    workspace: "批次工作台",
    history: "历史批次",
    admin: "管理员配置",
  };
  els.pageTitle.textContent = titles[view];
}

function renderHistory(batches) {
  if (!batches.length) {
    els.historyList.innerHTML = `<div class="empty-state"><h3>暂无历史批次</h3><p>上传后会自动保留解析、提交和审计记录。</p></div>`;
    return;
  }
  els.historyList.innerHTML = batches
    .map(
      (batch) => `
      <article class="history-item">
        <div>
          <h4>${escapeHtml(batch.name)}</h4>
          <div class="history-meta">
            ${escapeHtml(batch.quarter)} · ${batch.line_count} 条明细 · ${batch.company_count} 张单 ·
            ${batch.blocking_issue_count} 个阻断项 · 创建人 ${escapeHtml(batch.created_by)}
          </div>
        </div>
        <div class="actions">
          ${statusPill(batch.status)}
          <button class="secondary-action" data-open-batch="${batch.id}">打开</button>
        </div>
      </article>
    `,
    )
    .join("");
  document.querySelectorAll("[data-open-batch]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.activeBatch = await api(`/api/batches/${button.dataset.openBatch}`);
      state.activeTab = "issues";
      renderActiveBatch();
      switchView("workspace");
    });
  });
}

function renderActiveBatch() {
  const batch = state.activeBatch;
  if (!batch) return;
  const blocking = batch.issues.filter((issue) => issue.severity === "error").length;
  const warnings = batch.issues.filter((issue) => issue.severity === "warning").length;
  const total = batch.bills.reduce((sum, bill) => sum + bill.total_amount_cents, 0);
  const canSubmit = batch.status === "ready";
  els.activeBatchPanel.innerHTML = `
    <div class="panel-heading">
      <div>
        <h3>${escapeHtml(batch.name)}</h3>
        <p>${escapeHtml(batch.id)} · 字段版本 ${escapeHtml(batch.field_mapping_version)}</p>
      </div>
      ${statusPill(batch.status)}
    </div>
    <div class="metrics">
      ${metric("明细行", batch.line_count)}
      ${metric("二级公司账单", batch.company_count)}
      ${metric("合计金额", money(total))}
      ${metric("异常", `${blocking} / ${warnings}`)}
    </div>
    <div class="summary-box">${escapeHtml(batch.agent_summary)}</div>
    <div class="actions">
      <a class="secondary-action" href="${batch.template_download_url}" target="_blank">下载上传模板</a>
      ${
        batch.invoice_package_download_url
          ? `<a class="secondary-action" href="${batch.invoice_package_download_url}" target="_blank">下载二级公司发票包</a>`
          : ""
      }
      ${
        batch.company_workbook_download_url
          ? `<a class="secondary-action" href="${batch.company_workbook_download_url}" target="_blank">下载二级公司明细表包</a>`
          : ""
      }
      <button class="primary-action" id="submitBatch" ${canSubmit ? "" : "disabled"}>确认提交到测试系统</button>
    </div>
    <div class="tab-row">
      ${tabButton("issues", "异常清单")}
      ${tabButton("bills", "二级公司汇总")}
      ${tabButton("lines", "门店明细")}
      ${tabButton("invoices", "发票匹配")}
      ${tabButton("submissions", "提交记录")}
      ${tabButton("audit", "审计日志")}
    </div>
    <div id="batchTabContent"></div>
  `;
  document.querySelector("#submitBatch").addEventListener("click", submitBatch);
  document.querySelectorAll("[data-batch-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeTab = button.dataset.batchTab;
      renderActiveBatch();
    });
  });
  renderBatchTab();
}

function renderBatchTab() {
  const batch = state.activeBatch;
  const host = document.querySelector("#batchTabContent");
  if (state.activeTab === "issues") {
    host.innerHTML = renderIssues(batch.issues);
  } else if (state.activeTab === "bills") {
    host.innerHTML = renderBills(batch.bills);
  } else if (state.activeTab === "lines") {
    host.innerHTML = renderLines(batch.lines);
  } else if (state.activeTab === "invoices") {
    host.innerHTML = renderInvoices(batch.invoice_matches);
  } else if (state.activeTab === "submissions") {
    host.innerHTML = renderSubmissions(batch.submissions);
  } else {
    host.innerHTML = renderAudit(batch.audit_events);
  }
}

function renderIssues(issues) {
  if (!issues.length) return emptyMini("没有异常，批次可提交。");
  return table(
    ["级别", "代码", "说明", "行号", "二级公司", "发票号码"],
    issues.map((issue) => [
      `<span class="inline-pill issue-${issue.severity}">${issue.severity}</span>`,
      issue.code,
      issue.message,
      issue.row_number || "",
      issue.company || "",
      issue.invoice_number || "",
    ]),
  );
}

function renderBills(bills) {
  if (!bills.length) return emptyMini("没有形成二级公司账单。");
  return table(
    ["二级公司", "季度", "金额", "明细行", "门店", "合同", "发票", "系统表单"],
    bills.map((bill) => [
      bill.secondary_company,
      bill.quarter,
      money(bill.total_amount_cents),
      bill.line_count,
      bill.store_codes.join(", "),
      bill.contract_numbers.join(", "),
      bill.invoice_numbers.join(", "),
      bill.external_form_id || "",
    ]),
  );
}

function renderLines(lines) {
  if (!lines.length) return emptyMini("没有可用明细行。");
  return table(
    ["行号", "二级公司", "季度", "门店代码", "门店名称", "合同编号", "发票号码", "服务费"],
    lines.slice(0, 150).map((line) => [
      line.source_row,
      line.secondary_company,
      line.quarter,
      line.store_code,
      line.store_name,
      line.contract_number,
      line.invoice_number,
      money(line.service_fee_cents),
    ]),
  );
}

function renderInvoices(matches) {
  if (!matches.length) return emptyMini("没有发票匹配记录。");
  return table(
    ["发票号码", "文件名", "状态", "关联门店"],
    matches.map((match) => [
      match.invoice_number,
      match.file_name,
      match.status,
      (match.related_store_codes || []).join(", "),
    ]),
  );
}

function renderSubmissions(submissions) {
  if (!submissions.length) return emptyMini("尚未提交到财务系统。");
  return table(
    ["二级公司", "季度", "系统表单", "状态", "提交时间", "附件数"],
    submissions.map((item) => [
      item.company,
      item.quarter,
      item.form_id,
      item.status,
      formatTime(item.submitted_at),
      item.invoice_uploads.length,
    ]),
  );
}

function renderAudit(events) {
  if (!events.length) return emptyMini("暂无审计记录。");
  return table(
    ["事件", "操作人", "说明", "时间"],
    events.map((event) => [
      event.event_type,
      event.actor,
      event.message,
      formatTime(event.created_at),
    ]),
  );
}

async function submitBatch() {
  if (!state.activeBatch) return;
  if (!confirm("确认将本批次提交到财务系统测试环境？")) return;
  try {
    state.activeBatch = await api(`/api/batches/${state.activeBatch.id}/submit`, { method: "POST" });
    renderActiveBatch();
    await loadHistory();
    showToast("已提交到财务系统测试适配器。");
  } catch (error) {
    showToast(error.message);
  }
}

async function saveConfig() {
  if (state.role !== "admin") {
    showToast("只有管理员可以保存配置。");
    return;
  }
  try {
    const config = JSON.parse(els.configEditor.value);
    state.config = await api("/api/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    els.configEditor.value = JSON.stringify(state.config, null, 2);
    showToast("配置已保存。");
  } catch (error) {
    showToast(error.message);
  }
}

function renderAdminAccess() {
  const isAdmin = state.role === "admin";
  els.adminNavItem.classList.toggle("hidden", !isAdmin);
  els.configEditor.disabled = !isAdmin;
  document.querySelector("#saveConfig").disabled = !isAdmin;
  els.adminLockNotice.textContent = isAdmin ? "当前可保存配置。" : "当前为经办角色，只能查看配置。";
}

function metric(label, value) {
  return `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></div>`;
}

function tabButton(key, label) {
  return `<button class="${state.activeTab === key ? "active" : ""}" data-batch-tab="${key}">${label}</button>`;
}

function table(headers, rows) {
  return `
    <div class="table-wrap">
      <table>
        <thead><tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("")}</tr></thead>
        <tbody>
          ${rows
            .map(
              (row) =>
                `<tr>${row.map((cell) => `<td>${String(cell).startsWith("<span") ? cell : escapeHtml(String(cell))}</td>`).join("")}</tr>`,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function emptyMini(message) {
  return `<div class="empty-state"><h3>${escapeHtml(message)}</h3></div>`;
}

function statusPill(status) {
  const labels = {
    ready: "可提交",
    blocked: "需处理异常",
    submitted: "已提交",
    draft: "草稿",
  };
  return `<span class="status-pill pill-${status}">${labels[status] || status}</span>`;
}

function money(cents) {
  return `${(Number(cents || 0) / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} 元`;
}

function formatTime(value) {
  if (!value) return "";
  return new Date(value).toLocaleString("zh-CN");
}

function showToast(message) {
  els.toast.textContent = message;
  els.toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => els.toast.classList.remove("show"), 3600);
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

boot().catch((error) => showToast(error.message));
