from .dice import roll_dice
from .clock import game_clock
from .lore import recall_fact

TOOLS_REGISTRY = {
    "roll_dice": roll_dice,
    "game_clock": game_clock,
    "recall_fact": recall_fact,
}
