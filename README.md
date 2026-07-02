# Procurement Tool Workspace

This repository now contains two related tools in separate folders:

- `procurement-tool/`: the original procurement settlement web tool.
- `feishu-sheet-post-sender/`: a Feishu app robot utility that reads a Feishu Wiki/Sheet range, formats the nearest milestone row, and sends it as a Feishu message or card.

## Procurement Tool

```bash
cd procurement-tool
python3 -m finance_agent.server --port 8787
```

See `procurement-tool/README.md` for the original usage notes.

## Feishu Sheet Post Sender

```bash
cd feishu-sheet-post-sender
cp .env.example .env.local
python3 feishu_sheet_post_sender.py --help
```

Use `.env.local` for local Feishu credentials. It is ignored by Git and must not be committed.
