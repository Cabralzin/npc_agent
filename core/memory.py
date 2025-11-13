from dataclasses import dataclass, field
from typing import Any, List

@dataclass
class EpisodicMemory:
    max_turns: int = 50

    def reduce(self, msgs: List[Any]) -> List[Any]:
        return msgs[-self.max_turns:]

@dataclass
class SemanticMemory:
    """Stub simples para busca de lore; troque por um retriever LangChain."""
    lore_docs: List[str] = field(default_factory=list)

    def search(self, query: str, k: int = 3) -> List[str]:
        scored = [
            (doc, sum(q in doc.lower() for q in query.lower().split()))
            for doc in self.lore_docs
        ]
        scored = [d for d in scored if d[1] > 0]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [d for d, _ in scored[:k]]
    

# footnotes
# mudar estrutura de memória utilizando grafo em vez de ações especificas, fazer um "agente de memoria", 
# memorias podem ser aguardadas em memoria de curt, média e longa duração