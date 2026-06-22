# 部署说明

## 推荐部署形态

不建议把应用直接暴露到公网。推荐：

1. 云服务器或容器服务运行本应用。
2. 前面加 HTTPS 反向代理。
3. 再加 Cloudflare Access、Tailscale、企业 SSO 或至少 Basic Auth。
4. 将 `data/` 和 `uploads/` 挂载到持久化磁盘，并定期备份。

## Docker 本机验证

```bash
docker build -t finance-quarterly-billing-agent .
docker run --rm \
  -p 8787:8787 \
  -e FINANCE_AGENT_BASIC_AUTH_USER=finance \
  -e FINANCE_AGENT_BASIC_AUTH_PASSWORD='change-me-long-password' \
  -v "$PWD/data:/app/data" \
  -v "$PWD/uploads:/app/uploads" \
  finance-quarterly-billing-agent
```

访问：

```text
http://127.0.0.1:8787
```

## 云服务器部署

在云服务器上执行：

```bash
git clone <your-repo-url> finance-agent
cd finance-agent
docker build -t finance-quarterly-billing-agent .
docker run -d \
  --name finance-agent \
  --restart unless-stopped \
  -p 127.0.0.1:8787:8787 \
  -e FINANCE_AGENT_BASIC_AUTH_USER=finance \
  -e FINANCE_AGENT_BASIC_AUTH_PASSWORD='<replace-with-strong-password>' \
  -v "$PWD/data:/app/data" \
  -v "$PWD/uploads:/app/uploads" \
  finance-quarterly-billing-agent
```

再用 Nginx/Caddy/Cloudflare Tunnel/Tailscale 将服务安全发布出去。

## 生产环境必须配置

- `FINANCE_AGENT_BASIC_AUTH_PASSWORD`：至少设置一个长随机密码。
- `FINANCE_AGENT_DATA_DIR`：批次、配置和审计记录目录。
- `FINANCE_AGENT_UPLOADS_DIR`：上传 Excel、发票和解压文件目录。
- 磁盘备份：每天备份 `data/`，按合规要求决定是否备份 `uploads/`。
- HTTPS：不要用 HTTP 明文传输财务数据。

## 后续增强

- 接企业统一登录，替换 Basic Auth。
- 将数据迁移到数据库和对象存储。
- 接真实财务系统 API。
- 增加日志脱敏、操作审计导出和数据留存策略。
