from langchain.tools import tool
from datetime import datetime

@tool
def game_clock(_: str = "") -> str:
    """Retorna timestamp do mundo (UTC)."""
    return datetime.utcnow().isoformat()