from __future__ import annotations
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class JSONMemoryStore:
    npc_id: str
    base_dir: str = "memory"
    max_items: int = 200

    @property
    def path(self) -> Path:
        Path(self.base_dir).mkdir(parents=True, exist_ok=True)
        return Path(self.base_dir) / f"{self.npc_id}.json"

    def _read(self) -> List[Dict[str, Any]]:
        p = self.path
        if not p.exists():
            return []
        try:
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                return []
        except Exception:
            # Se o arquivo estiver corrompido, começamos limpo
            return []

    def _write(self, items: List[Dict[str, Any]]) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

    def append(self, item: Dict[str, Any]) -> None:
        items = self._read()
        items.append(item)
        if len(items) > self.max_items:
            items = items[-self.max_items:]
        self._write(items)

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def minimal_record(
        self,
        *,
        user_text: str,
        reply_text: Optional[str],
        intent: Optional[str] = None,
        action: Optional[Dict[str, Any]] = None,
        events: Optional[List[Dict[str, Any]]] = None,
        extras: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        rec: Dict[str, Any] = {
            "ts": self.now_iso(),
            "npc_id": self.npc_id,
            "user": user_text,
            "reply": reply_text,
        }
        if intent is not None:
            rec["intent"] = intent
        if action is not None:
            # apenas campos essenciais para leitura
            rec["action"] = {k: action.get(k) for k in ("type", "name", "content") if k in action}
        if events:
            # armazena eventos de forma compacta e legível
            rec["events"] = events[:5]
        if extras:
            for k, v in extras.items():
                if v is not None:
                    rec[k] = v
        return rec


@dataclass
class CategorizedMemoryStore:
    """Knowledge-base por categorias simples e editável em JSON.

    Estrutura do arquivo:
    {
      "life": [ {"title": str, "summary": str, "metadata": {...}, "last_updated": iso} ],
      "people": [ ... ],
      "places": [ ... ],
      "skills": [ ... ],
      "objects": [ ... ]
    }
    """
    npc_id: str
    base_dir: str = "memory"

    CATEGORIES = ("life", "people", "places", "skills", "objects")

    @property
    def path(self) -> Path:
        Path(self.base_dir).mkdir(parents=True, exist_ok=True)
        return Path(self.base_dir) / f"{self.npc_id}.kb.json"

    def _empty(self) -> Dict[str, List[Dict[str, Any]]]:
        return {c: [] for c in self.CATEGORIES}

    def read(self) -> Dict[str, List[Dict[str, Any]]]:
        p = self.path
        if not p.exists():
            return self._empty()
        try:
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # garante todas categorias
                    for c in self.CATEGORIES:
                        if c not in data or not isinstance(data[c], list):
                            data[c] = []
                    return data
                return self._empty()
        except Exception:
            return self._empty()

    def write(self, data: Dict[str, List[Dict[str, Any]]]) -> None:
        # normaliza categorias
        norm = {c: data.get(c, []) for c in self.CATEGORIES}
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(norm, f, ensure_ascii=False, indent=2)

    def _find_index(self, items: List[Dict[str, Any]], title: str) -> int:
        t = (title or "").strip().lower()
        for i, it in enumerate(items):
            if (it.get("title", "").strip().lower()) == t:
                return i
        return -1

    def upsert_item(
        self,
        *,
        category: str,
        title: str,
        summary: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Insere ou atualiza um item por título dentro da categoria."""
        if category not in self.CATEGORIES:
            return
        data = self.read()
        lst = data.get(category, [])
        idx = self._find_index(lst, title)
        now = JSONMemoryStore.now_iso()
        record = {
            "title": title.strip(),
            "summary": summary.strip(),
            "metadata": metadata or {},
            "last_updated": now,
        }
        if idx >= 0:
            # merge simples: mantém metadata antiga e sobrescreve chaves novas
            old = lst[idx]
            merged_meta = dict(old.get("metadata", {}))
            merged_meta.update(record["metadata"])  # type: ignore
            old.update({
                "summary": record["summary"],
                "metadata": merged_meta,
                "last_updated": now,
            })
            lst[idx] = old
        else:
            lst.append(record)
        data[category] = lst
        self.write(data)

    def all(self) -> Dict[str, List[Dict[str, Any]]]:
        return self.read()

