# 飞书项目进展定时推送交接说明

## 1. 工具用途

这个工具用于读取飞书知识库里的在线表格：

```text
https://haidilao.feishu.cn/wiki/XY6Uwdj8XiLGttkRkEmcCXUon9e?sheet=ec004f
```

默认读取范围：

```text
A1:C16
```

脚本会生成标题为 `项目进展` 的飞书卡片消息，并发送给配置好的收件人。

里程碑处理规则：

- 每个项目只保留离当前日期最近的一条里程碑。
- 如果一个单元格里写了多个里程碑，也只保留最近的那一段。
- 某个收件人发送失败时，不影响其他收件人继续发送；最后会在日志里汇总失败项。

## 2. 代码和服务器路径

本机开发仓库：

```sh
cd /Users/kk/Documents/Codex/2026-07-02/new-chat/work/tools-repo
```

工具目录：

```sh
cd /Users/kk/Documents/Codex/2026-07-02/new-chat/work/tools-repo/feishu-sheet-post-sender
```

服务器仓库根目录：

```sh
cd /opt/feishu-milestone-send
```

服务器脚本目录：

```sh
cd /opt/feishu-milestone-send/feishu-sheet-post-sender
```

注意：

- `git pull` 在服务器仓库根目录执行：`/opt/feishu-milestone-send`
- `python3 weekly_send.py` 在服务器脚本目录执行：`/opt/feishu-milestone-send/feishu-sheet-post-sender`

## 3. 文件说明

- `feishu_sheet_post_sender.py`: 主发送脚本。一次发送给一个收件人，也可用于预览和排查。
- `weekly_send.py`: 定时任务入口。读取 `.env.local`，支持多人发送、混合 ID 类型、邮箱查询。
- `contact_cache.py`: 可选的通讯录缓存脚本，需要飞书通讯录权限。
- `.env.example`: 配置模板。
- `.env.local`: 服务器本地真实配置，不提交 GitHub。
- `README.md`: 完整说明。
- `HANDOFF.md`: 当前交接文档。
- `test_*.py`: 测试文件。

## 4. 推荐 `.env.local` 配置

在服务器脚本目录编辑：

```sh
cd /opt/feishu-milestone-send/feishu-sheet-post-sender
vi .env.local
```

推荐使用 `FEISHU_WEEKLY_RECIPIENTS` 配置收件人：

```env
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=你的真实 app_secret
FEISHU_BASE_URL=https://open.feishu.cn

FEISHU_WEEKLY_SEND_ENABLED=true
FEISHU_WEEKLY_ENV_FILE=.env.local
FEISHU_WEEKLY_SHEET_URL=https://haidilao.feishu.cn/wiki/XY6Uwdj8XiLGttkRkEmcCXUon9e?sheet=ec004f
FEISHU_WEEKLY_RANGE=A1:C16
FEISHU_WEEKLY_RECIPIENTS=user_id:12139762,email:yaoxy@haidilao.com,email:zhaocs@haidilao.com
FEISHU_WEEKLY_EMAIL_LOOKUP_ID_TYPE=open_id
FEISHU_WEEKLY_TITLE=项目进展
FEISHU_WEEKLY_MESSAGE_FORMAT=card
FEISHU_WEEKLY_SHOW_ALL_MILESTONES=false
FEISHU_WEEKLY_DEBUG=false
```

旧字段仍然保留是为了兼容历史配置。使用 `FEISHU_WEEKLY_RECIPIENTS` 时，建议旧字段留空：

```env
FEISHU_WEEKLY_RECEIVE_ID=
FEISHU_WEEKLY_RECEIVE_IDS=
FEISHU_WEEKLY_RECEIVE_ID_TYPE=user_id
```

`FEISHU_WEEKLY_RECIPIENTS` 优先级最高。

## 5. 收件人配置规则

推荐写法：

```env
FEISHU_WEEKLY_RECIPIENTS=user_id:12139762,open_id:ou_xxx,email:person@example.com
```

支持的类型：

- `user_id:12139762`: 直接用飞书 `user_id` 发送。你自己的 `12139762` 已验证可用。
- `open_id:ou_xxx`: 直接用飞书 `open_id` 发送。
- `union_id:on_xxx`: 直接用飞书 `union_id` 发送。
- `chat_id:oc_xxx`: 发送到群聊。
- `email:person@example.com`: 先用邮箱查询，再按 `FEISHU_WEEKLY_EMAIL_LOOKUP_ID_TYPE` 指定的 ID 类型发送。
- `mobile:13800000000`: 先用手机号查询，再按 `FEISHU_WEEKLY_EMAIL_LOOKUP_ID_TYPE` 指定的 ID 类型发送。

邮箱查询默认查 `open_id`：

```env
FEISHU_WEEKLY_EMAIL_LOOKUP_ID_TYPE=open_id
```

如果某个邮箱查不到 `open_id`，这个收件人会失败，但其他收件人会继续发送。

## 6. `FEISHU_WEEKLY_SEND_ENABLED` 怎么用

```env
FEISHU_WEEKLY_SEND_ENABLED=false
```

表示禁用真实发送。执行 `python3 weekly_send.py` 时只会输出跳过发送，适合临时关闭定时任务、防误发。

```env
FEISHU_WEEKLY_SEND_ENABLED=true
```

表示允许真实发送。手动测试 `weekly_send.py` 或 cron 定时发送都需要设置为 `true`。

如果只想预览消息，不想发送，不要用 `weekly_send.py`，而是用主脚本且不加 `--send`。

## 7. 手动预览，不发送

进入服务器脚本目录：

```sh
cd /opt/feishu-milestone-send/feishu-sheet-post-sender
```

执行：

```sh
python3 feishu_sheet_post_sender.py \
  --env-file .env.local \
  --sheet-url 'https://haidilao.feishu.cn/wiki/XY6Uwdj8XiLGttkRkEmcCXUon9e?sheet=ec004f' \
  --range A1:C16 \
  --receive-id 12139762 \
  --receive-id-type user_id \
  --title '项目进展' \
  --message-format card \
  --debug
```

没有 `--send` 就不会真正发送，只会输出预览 payload。

## 8. 手动真实发送

确认 `.env.local` 中：

```env
FEISHU_WEEKLY_SEND_ENABLED=true
```

进入服务器脚本目录：

```sh
cd /opt/feishu-milestone-send/feishu-sheet-post-sender
```

执行：

```sh
python3 weekly_send.py
```

如果有部分收件人失败，日志会出现：

```text
weekly send completed with failures:
- email:xxx@haidilao.com ...
```

这表示失败项已记录，其他可发送的收件人仍会继续发送。

## 9. 测试某个邮箱是否能查到 open_id

```sh
cd /opt/feishu-milestone-send/feishu-sheet-post-sender

python3 feishu_sheet_post_sender.py \
  --env-file .env.local \
  --sheet-url 'https://haidilao.feishu.cn/wiki/XY6Uwdj8XiLGttkRkEmcCXUon9e?sheet=ec004f' \
  --range A1:C16 \
  --lookup-email yaoxy@haidilao.com \
  --receive-id-type open_id \
  --title '项目进展' \
  --message-format card \
  --debug
```

成功时，输出里会出现：

```json
"receive_id": "ou_xxx"
```

如果报：

```text
Feishu user record does not contain open_id
```

说明当前应用权限或可见范围拿不到这个邮箱对应的 `open_id`。可以改用已知 `user_id/open_id`，或者让管理员补飞书通讯录权限。

## 10. 本机开发和推送

本机代码目录：

```sh
cd /Users/kk/Documents/Codex/2026-07-02/new-chat/work/tools-repo
```

查看改动：

```sh
git status
```

运行测试：

```sh
cd /Users/kk/Documents/Codex/2026-07-02/new-chat/work/tools-repo/feishu-sheet-post-sender
python3 -m unittest test_feishu_sheet_post_sender.py test_weekly_send.py test_contact_cache.py
```

提交并推送：

```sh
cd /Users/kk/Documents/Codex/2026-07-02/new-chat/work/tools-repo
git add feishu-sheet-post-sender
git commit -m "你的提交说明"
git push origin main
```

## 11. 服务器更新代码

在服务器执行：

```sh
cd /opt/feishu-milestone-send
git pull
```

然后进入脚本目录测试：

```sh
cd /opt/feishu-milestone-send/feishu-sheet-post-sender
python3 weekly_send.py
```

## 12. 定时任务

查看当前定时任务：

```sh
crontab -l
```

编辑定时任务：

```sh
crontab -e
```

每周一 14:00 自动发送：

```cron
0 14 * * 1 cd /opt/feishu-milestone-send/feishu-sheet-post-sender && /usr/bin/python3 weekly_send.py >> weekly_send.log 2>&1
```

服务器 cron 使用服务器本地时区。可以用下面命令确认：

```sh
date
```

## 13. 通讯录缓存，可选

如果要拉通讯录缓存，先确认飞书应用有通讯录权限和部门可见范围。

刷新缓存：

```sh
cd /opt/feishu-milestone-send/feishu-sheet-post-sender
python3 contact_cache.py --env-file .env.local --output contacts_cache.json --debug
```

启用缓存：

```env
FEISHU_CONTACT_CACHE_ENABLED=true
FEISHU_CONTACT_CACHE_PATH=contacts_cache.json
```

如果报：

```text
no dept authority error
```

说明应用没有部门通讯录权限。可以不开缓存，直接使用 `FEISHU_WEEKLY_RECIPIENTS`。

## 14. 常见问题

### `Invalid ids: [someone@haidilao.com]`

原因：把邮箱当成普通 ID 发送了。

错误写法：

```env
FEISHU_WEEKLY_RECEIVE_IDS=someone@haidilao.com
FEISHU_WEEKLY_RECEIVE_ID_TYPE=user_id
```

正确写法：

```env
FEISHU_WEEKLY_RECIPIENTS=email:someone@haidilao.com
FEISHU_WEEKLY_EMAIL_LOOKUP_ID_TYPE=open_id
```

### `Feishu user record does not contain open_id`

原因：飞书接口能看到邮箱，但当前应用拿不到该用户的 `open_id`。

处理方式：

- 换成已知可用的 `user_id/open_id/union_id`
- 或让管理员给飞书应用补通讯录权限和可见范围

### `app secret invalid`

原因：`.env.local` 里的 `FEISHU_APP_SECRET` 不对。

处理方式：

```sh
vi .env.local
```

检查：

```env
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=真实密钥
FEISHU_BASE_URL=https://open.feishu.cn
```

### `Missing sheet id`

原因：表格链接缺少 `?sheet=ec004f`。

正确写法：

```env
FEISHU_WEEKLY_SHEET_URL=https://haidilao.feishu.cn/wiki/XY6Uwdj8XiLGttkRkEmcCXUon9e?sheet=ec004f
```

