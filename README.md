# 采购Agent

这是一个可运行的首版网页型采购/财务 agent，用于季度服务费账单处理：

- 上传固定格式服务费 Excel，按二级公司和季度汇总账单。
- 上传公司架构/匹配表，将门店按最新二级公司主体重新归集。
- 提取合同编号、门店代码、发票号码、服务费金额等字段。
- 按发票文件名中的发票号码匹配附件，支持选择发票根文件夹或上传 zip 压缩包。
- 生成系统上传模板，并按二级公司导出各自的门店明细表。
- 按二级公司整理发票文件夹，每个文件夹只包含该主体下门店的发票。
- 提交前由经办人确认，再写入财务系统测试适配器。
- 管理员可在线维护字段别名、发票命名规则、模板列和 API 配置。

## 本地运行

推荐使用 Codex 内置 Python 运行时，里面已包含 Excel 处理依赖：

```bash
/Users/kk/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m finance_agent.server --port 8787
```

打开：

```text
http://127.0.0.1:8787
```

如果使用普通 Python 环境，请先安装 `openpyxl`。

## 生成示例数据

```bash
/Users/kk/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 samples/generate_sample.py
```

生成后，在网页中上传：

- `samples/service_fee_2026_q1.xlsx`
- `samples/invoices/` 下的发票文件
- 公司架构/匹配表示例可使用包含 `账单主体匹配` sheet 的匹配表，或原始 `公司代码（国内+海外）` 架构表。

如果发票解压后分散在多个子文件夹中，可在网页选择“发票根文件夹”，系统会递归收集 PDF、OFD 和常见图片格式发票。也可以直接上传包含多层目录的 `.zip` 压缩包。

## 海底捞付款申请表适配

对于 `2026年1-3月海底捞付款申请(含发票号).xlsx` 这类工作簿，系统会自动识别：

- `付款明细1`、`付款明细 2`、`付款明细3`、`付款明细4` 作为服务费明细来源。
- `火锅门店` 作为门店到 `公司代码` 的映射来源。
- 如果上传公司架构/匹配表，则优先按门店名称或公司代码匹配到最新二级公司，如 `1118 北京十八店 -> 1003`。
- `公司代码` 写入导入模板的 `leCode`，`ccCode` 默认按 `leCode + 200002` 生成。
- `operationSubTypeCode` 默认填 `hdl0085-001`，`taxType` 默认填 `001105`。

## 角色

- 经办：上传批次、查看汇总、下载模板、确认提交。
- 管理员：具备经办能力，并可保存规则和模板配置。

网页左侧可切换当前角色。首版使用轻量角色模拟，正式内网部署时应接入企业统一登录。

## 财务系统对接

当前 `MockFinanceSystemAdapter` 是测试适配器，已经固定了真实 API 的边界：

- 创建二级公司季度表单。
- 写入字段。
- 上传匹配到的发票附件。
- 返回系统表单号和附件号。

拿到财务系统测试 API 文档后，只需要替换 `finance_agent/adapter.py` 中的适配器实现，前端和规则引擎不需要重写。

## 测试

```bash
/Users/kk/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest discover -s tests
```
