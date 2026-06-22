from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .config import load_config, save_config
from .models import BillingBatch, batch_from_dict, to_dict


class AppStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.batches_dir = root / "batches"
        self.config_path = root / "config.json"
        self.batches_dir.mkdir(parents=True, exist_ok=True)

    def load_config(self) -> Dict:
        return load_config(self.config_path)

    def save_config(self, config: Dict) -> None:
        save_config(self.config_path, config)

    def save_batch(self, batch: BillingBatch) -> None:
        path = self.batches_dir / f"{batch.id}.json"
        with path.open("w", encoding="utf-8") as handle:
            json.dump(to_dict(batch), handle, ensure_ascii=False, indent=2)

    def load_batch(self, batch_id: str) -> BillingBatch:
        path = self.batches_dir / f"{batch_id}.json"
        if not path.exists():
            raise KeyError(batch_id)
        with path.open("r", encoding="utf-8") as handle:
            return batch_from_dict(json.load(handle))

    def list_batches(self) -> List[BillingBatch]:
        batches: List[BillingBatch] = []
        for path in sorted(self.batches_dir.glob("*.json"), reverse=True):
            with path.open("r", encoding="utf-8") as handle:
                batches.append(batch_from_dict(json.load(handle)))
        return sorted(batches, key=lambda item: item.created_at, reverse=True)
