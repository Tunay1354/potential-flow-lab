"""The beaver mascot (his name: app_info.MASCOT_NAME):

    beaver.py     what he does (on the ruler, on the plot, carried by the flow, knocked by pulses), his dialogs
    art.py        the pixel art, drawn from shapes (crisp at every size and rotation)
    bubble.py     the speech bubble (typed text, choices, buttons)
    lines.py      what he says ({name} = his name)
    faq.py        questions & answers
    tour.py       the guided tour; spotlight.py highlights the part it explains
"""
from .beaver import Beaver, BeaverSprite

__all__ = ["Beaver", "BeaverSprite"]
