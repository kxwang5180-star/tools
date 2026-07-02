# Feishu Sheet Post Sender

读取一张飞书在线表格或知识库 Wiki 中的表格，生成项目进展消息，并用飞书应用机器人发送给一个联系人或群聊。支持 `msg_type: post` + `md` 标签，也支持飞书交互式卡片。

## 准备

飞书应用需要具备：

- 读取飞书电子表格或云空间文件的权限
- 如果读取知识库中的多维表格，需要知识库节点读取权限和多维表格读取权限
- 发送消息的权限
- 如果用 `email` 作为接收人类型，需要相应通讯录或消息接收权限
- 如果用 `--lookup-email` 或 `--lookup-mobile` 自动换取用户 ID，需要通讯录“通过手机号或邮箱获取用户 ID”相关权限
- 目标在线表格需要授权给该应用，否则会拿到权限错误

创建本地环境变量文件：

```sh
cp .env.example .env.local
```

把 `.env.local` 中的 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` 改成你的飞书应用配置。不要把真实密钥提交到仓库。

## 预览消息

默认只预览，不发送：

```sh
python3 feishu_sheet_post_sender.py \
  --env-file .env.local \
  --sheet-url 'https://tenant.feishu.cn/sheets/shtcnxxxx?sheet=xxxxxx' \
  --range A1:F20 \
  --receive-id ou_xxxxx \
  --receive-id-type open_id \
  --title '项目进展'
```

输出里会包含最终发送 payload，其中 `content` 是飞书接口要求的 JSON 字符串。

消息正文只展示表格本身，不额外插入更新时间、数据条数等说明。如果识别到表头里包含“里程碑/节点/计划时间/截止时间”等字段，会按项目分组，每个项目只展示日期离当前时间最近的一条里程碑。若多条里程碑写在同一个单元格里，工具也会在该单元格内部只保留最近的那一段。需要展示全部时加 `--show-all-milestones`。

也支持知识库中的多维表格链接：

```text
https://haidilao.feishu.cn/wiki/XY6Uwdj8XiLGttkRkEmcCXUon9e?sheet=ec004f
```

工具会先调用知识库节点接口，把 `wiki` 后面的节点 token 转成实际对象 token。若节点是普通电子表格，会按 Sheets API 读取；若节点是多维表格，会按 Bitable API 读取。对多维表格来说，`A1:C16` 会被解释为“取前 3 个字段，最多 15 条数据记录”，第一行作为表头。

```sh
python3 feishu_sheet_post_sender.py \
  --env-file .env.local \
  --sheet-url 'https://haidilao.feishu.cn/wiki/XY6Uwdj8XiLGttkRkEmcCXUon9e?sheet=ec004f' \
  --range A1:C16 \
  --receive-id 12139762 \
  --receive-id-type user_id \
  --title '项目进展' \
  --message-format card
```

## 正式发送

确认预览无误后加 `--send`：

```sh
python3 feishu_sheet_post_sender.py \
  --env-file .env.local \
  --sheet-url 'https://tenant.feishu.cn/sheets/shtcnxxxx?sheet=xxxxxx' \
  --range A1:F20 \
  --receive-id ou_xxxxx \
  --receive-id-type open_id \
  --title '项目进展' \
  --send
```

如果要发送到群聊，把 `--receive-id-type` 改成 `chat_id`，`--receive-id` 填群聊 `chat_id`。

如果你的企业把工号作为飞书消息接口的 `user_id` 使用，并且应用已开通“获取用户 user ID”相关权限，可以这样直接发给工号：

```sh
python3 feishu_sheet_post_sender.py \
  --env-file .env.local \
  --sheet-url 'https://haidilao.feishu.cn/wiki/XY6Uwdj8XiLGttkRkEmcCXUon9e?sheet=ec004f' \
  --range A1:C16 \
  --receive-id 12139762 \
  --receive-id-type user_id \
  --title '项目进展' \
  --message-format card \
  --send
```

## 通过邮箱或手机号查接收人

如果你不知道 `open_id` 或 `user_id`，可以先用邮箱或手机号自动查询：

```sh
python3 feishu_sheet_post_sender.py \
  --env-file .env.local \
  --sheet-url 'https://tenant.feishu.cn/sheets/shtcnxxxx?sheet=xxxxxx' \
  --range A1:C16 \
  --lookup-email person@example.com \
  --receive-id-type open_id \
  --title '项目进展'
```

或者：

```sh
python3 feishu_sheet_post_sender.py \
  --env-file .env.local \
  --sheet-url 'https://tenant.feishu.cn/sheets/shtcnxxxx?sheet=xxxxxx' \
  --range A1:C16 \
  --lookup-mobile 13800000000 \
  --receive-id-type open_id \
  --title '项目进展'
```

如果直接用工号发送报错，说明该租户里消息接口识别的 `user_id` 不是工号；再改用邮箱或手机号查询 `open_id/user_id`。

## 参数说明

- `--sheet-url`: 飞书在线表格 `/sheets/` URL，或知识库多维表格 `/wiki/` URL
- `--spreadsheet-token`: 不使用 URL 时手动提供表格 token
- `--sheet-id`: 不使用 URL 或 URL 缺少 `sheet` 参数时手动提供工作表 id
- `--table-id`: 多维表格 table id；默认读取 `table` 或 `sheet` 查询参数，缺省时读取第一个表
- `--range`: 单元格范围，例如 `A1:F20`，也可传完整范围 `sheetId!A1:F20`
- `--receive-id`: 接收人或群聊 id
- `--receive-id-type`: `open_id`、`user_id`、`union_id`、`email`、`chat_id`
- `--lookup-email`: 用邮箱查询接收人的 `open_id/user_id/union_id`
- `--lookup-mobile`: 用手机号查询接收人的 `open_id/user_id/union_id`
- `--max-rows`: Markdown 表格最多展示的数据行数，默认 20
- `--max-columns`: Markdown 表格最多展示列数，默认 8
- `--max-cell-length`: 单元格最大字符数，默认 80
- `--message-format`: `post` 或 `card`，默认 `post`
- `--show-all-milestones`: 关闭按项目筛选最近里程碑，展示范围内所有行
- `--uuid`: 可选的飞书消息去重 id
- `--send`: 真正发送；不加时只预览

## 注意

飞书客户端对 `post` 消息里的 `md` 表格渲染能力可能受客户端版本影响。建议优先使用 `--message-format card`，卡片模式会用固定比例列布局渲染表格：项目名称、当前在做、里程碑三列比例为 `3:3:5`，避免不同行因为内容长短不同而错位。

当前目录本身不是 Git 仓库。如果要发布到 GitHub，需要先提供一个空仓库地址，或者在 GitHub 上创建仓库后把远端地址配置到这里。
