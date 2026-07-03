# Feishu Milestone Sender Handoff

## Purpose

This tool reads the Feishu wiki sheet range `A1:C16`, keeps the nearest milestone for each project, and sends a Feishu card message titled `项目进展`.

It is designed for server execution through `weekly_send.py`, normally scheduled by cron every Monday at 14:00.

## Files

- `feishu_sheet_post_sender.py`: core sender. Reads the sheet and sends one message to one recipient.
- `weekly_send.py`: scheduler entrypoint. Reads `.env.local`, supports multiple recipients, and continues sending when one recipient fails.
- `contact_cache.py`: optional contact cache refresher. Requires Feishu contact permissions.
- `.env.example`: environment variable template.
- `README.md`: full usage guide.
- `test_*.py`: local tests.

## Recommended `.env.local`

Use `FEISHU_WEEKLY_RECIPIENTS` for recipients. It supports mixed recipient types and is the current recommended format.

```env
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=your_real_secret
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

Legacy fields still exist for backward compatibility:

```env
FEISHU_WEEKLY_RECEIVE_ID=
FEISHU_WEEKLY_RECEIVE_IDS=
FEISHU_WEEKLY_RECEIVE_ID_TYPE=user_id
```

Keep these empty when `FEISHU_WEEKLY_RECIPIENTS` is used.

## About `FEISHU_WEEKLY_SEND_ENABLED`

- `false`: `weekly_send.py` exits safely and does not send messages. This is useful for deployment safety and cron disablement.
- `true`: `weekly_send.py` performs real sending. Use this for actual manual verification and scheduled sending.

For dry-run preview without sending, use the core script without `--send`:

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

## Recipient Rules

Recommended format:

```env
FEISHU_WEEKLY_RECIPIENTS=user_id:12139762,open_id:ou_xxx,email:person@example.com
```

Supported prefixes:

- `user_id:` sends directly using a Feishu `user_id`.
- `open_id:` sends directly using a Feishu `open_id`.
- `union_id:` sends directly using a Feishu `union_id`.
- `chat_id:` sends to a group chat.
- `email:` first looks up the user, then sends using `FEISHU_WEEKLY_EMAIL_LOOKUP_ID_TYPE`.
- `mobile:` first looks up the user, then sends using `FEISHU_WEEKLY_EMAIL_LOOKUP_ID_TYPE`.

If email lookup fails for one recipient, the tool continues sending to the remaining recipients. The run exits with code `1` and logs the failed recipients.

## Manual Checks

Check whether an email can be resolved:

```sh
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

Run the actual weekly sender manually:

```sh
python3 weekly_send.py
```

Run local tests:

```sh
python3 -m unittest test_feishu_sheet_post_sender.py test_weekly_send.py test_contact_cache.py
```

## Server Deployment

Repository root on server:

```sh
cd /opt/feishu-milestone-send
git pull
```

Script directory:

```sh
cd /opt/feishu-milestone-send/feishu-sheet-post-sender
```

Cron:

```cron
0 14 * * 1 cd /opt/feishu-milestone-send/feishu-sheet-post-sender && /usr/bin/python3 weekly_send.py >> weekly_send.log 2>&1
```

## Common Failures

`Invalid ids: [someone@haidilao.com]`

The email was sent as a raw ID. Use `FEISHU_WEEKLY_RECIPIENTS=email:someone@haidilao.com`, not `FEISHU_WEEKLY_RECEIVE_IDS=someone@haidilao.com`.

`Feishu user record does not contain open_id`

The app can see the email but cannot obtain the requested ID type. Use a known `user_id/open_id`, or ask the Feishu app admin to grant the required contact permissions and visible scope.

`no dept authority error`

The app cannot read the target department for contact cache. Grant department contact permission or skip contact cache.
