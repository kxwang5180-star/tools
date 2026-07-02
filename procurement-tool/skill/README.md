# 采购Agent Skill

用于后续维护采购Agent项目时快速恢复上下文。

## 项目定位

采购Agent是一个网页型季度服务费处理工具：

- 上传服务费 Excel、系统上传模板、公司架构/匹配表、发票文件或发票压缩包。
- 按最新二级公司口径汇总门店费用。
- 生成财务系统上传模板。
- 按二级公司生成门店明细表。
- 按二级公司整理发票文件夹。
- 经办人确认后提交到财务系统测试适配器。

## 关键目录

- `finance_agent/`：后端解析、匹配、汇总、模板导出、HTTP 服务。
- `static/`：网页页面、样式和交互逻辑。
- `tests/`：核心规则测试。
- `deploy/`：服务器部署说明。

## 注意事项

- 不要提交 `data/`、`uploads/`、`outputs/`，这些目录可能包含真实发票、账单和批次记录。
- 公司架构表、付款申请表、发票文件应通过网页上传或在服务器运行目录单独保存。
- 当前财务系统对接是 `MockFinanceSystemAdapter`，正式接口在 `finance_agent/adapter.py` 替换。

## 本地运行

```bash
python3 -m finance_agent.server --port 8788
```

如需 Basic Auth：

```bash
FINANCE_AGENT_BASIC_AUTH_USER=xxjsb \
FINANCE_AGENT_BASIC_AUTH_PASSWORD='hdl123！' \
python3 -m finance_agent.server --port 8788
```

## 测试

```bash
python3 -m unittest discover -s tests
```
