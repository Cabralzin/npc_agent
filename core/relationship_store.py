from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class RelationshipStore:
    """Armazena relacionamentos do NPC com outros personagens."""
    npc_id: str
    base_dir: str = "memory"

    @property
    def path(self) -> Path:
        Path(self.base_dir).mkdir(parents=True, exist_ok=True)
        return Path(self.base_dir) / f"{self.npc_id}_relationships.json"

    def read(self) -> Dict[str, Dict[str, Any]]:
        """Lê todos os relacionamentos do arquivo."""
        p = self.path
        if not p.exists():
            return {}
        try:
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                return {}
        except Exception:
            return {}

    def write(self, relationships: Dict[str, Dict[str, Any]]) -> None:
        """Escreve todos os relacionamentos no arquivo."""
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(relationships, f, ensure_ascii=False, indent=2)

    def get_relationship(self, character_name: str) -> Dict[str, Any]:
        """Obtém o relacionamento com um personagem específico."""
        relationships = self.read()
        return relationships.get(character_name, self._default_relationship(character_name))

    def update_relationship(
        self,
        character_name: str,
        *,
        trust: Optional[float] = None,
        fear: Optional[float] = None,
        respect: Optional[float] = None,
        attachment: Optional[float] = None,
        hostility: Optional[float] = None,
        dependance: Optional[float] = None,
        betrayal_memory: Optional[str] = None,
        interaction_event: Optional[str] = None,
        interaction_impact: Optional[Dict[str, float]] = None,
    ) -> None:
        """Atualiza o relacionamento com um personagem."""
        relationships = self.read()
        
        if character_name not in relationships:
            relationships[character_name] = self._default_relationship(character_name)
        
        rel = relationships[character_name]
        
        # Atualiza valores se fornecidos
        if trust is not None:
            rel["trust"] = max(0.0, min(1.0, float(trust)))
        if fear is not None:
            rel["fear"] = max(0.0, min(1.0, float(fear)))
        if respect is not None:
            rel["respect"] = max(0.0, min(1.0, float(respect)))
        if attachment is not None:
            rel["attachment"] = max(0.0, min(1.0, float(attachment)))
        if hostility is not None:
            rel["hostility"] = max(0.0, min(1.0, float(hostility)))
        if dependance is not None:
            rel["dependance"] = max(0.0, min(1.0, float(dependance)))
        if betrayal_memory is not None:
            rel["betrayal_memory"] = betrayal_memory
        
        # Adiciona interação ao histórico
        if interaction_event and interaction_impact:
            interaction = {
                "event": interaction_event,
                "impact": interaction_impact,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            rel["interaction_history"].append(interaction)
            # Mantém apenas as últimas 50 interações
            if len(rel["interaction_history"]) > 50:
                rel["interaction_history"] = rel["interaction_history"][-50:]
        
        relationships[character_name] = rel
        self.write(relationships)

    def _default_relationship(self, character_name: str) -> Dict[str, Any]:
        """Retorna um relacionamento padrão para um novo personagem."""
        return {
            "nome": character_name,
            "trust": 0.5,
            "fear": 0.0,
            "respect": 0.5,
            "attachment": 0.0,
            "hostility": 0.0,
            "dependance": 0.0,
            "betrayal_memory": "",
            "interaction_history": []
        }

