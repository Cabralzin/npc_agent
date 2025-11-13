from langchain.tools import tool
import random
import re

@tool
def roll_dice(spec: str) -> str:
    """Rola dados no formato NdM[+/-bônus], e retorna total e rolagens."""
    m = re.fullmatch(r"(\d+)d(\d+)([+-]\d+)?", spec.strip())
    if not m:
        return "Formato inválido. Ex.: 2d6+1"
    n, sides, mod = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    rolls = [random.randint(1, sides) for _ in range(n)]
    total = sum(rolls) + mod
    return f"{spec} => rolagens {rolls} + {mod} = {total}"