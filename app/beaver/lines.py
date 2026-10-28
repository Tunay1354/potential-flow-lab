"""
lines.py — what the beaver says (English). One key per situation; pick() takes a random line of it, not
the same one twice in a row.
"""
import random

LINES = {
    "hello": ["Hi! I'm Psi, your flow buddy.\nGrab me and drop me on the plot!"],
    "grabbed": ["Whoa, whoa!", "Hey, hey! What are you doing?!", "Put me down gently,\nI bruise like a peach.",
                "Wheee— wait, where are we going?"],
    "glass_drop": ["Did you think I'd fall?", "Ha! Did you think I'd fall?"],
    "glass_tap": ["Static mode: there's glass\nin front of the plot. *tap tap*",
                  "See? Glass. Static mode\nkeeps the flow behind it."],
    "glass_back": ["Nice try. Back to my shelf!", "Okay, back to my shelf."],
    "glass_again": ["Hey! Who put the glass back?"],
    "splash": ["Splash!", "Into the flow we go!"],
    "flow_start": ["Wheee!", "Here we go!", "Riding the streamlines!"],
    "flow_fast": ["Wheee! Faster over the top!", "Circulation, baby!", "So fast! Bernoulli says\nthe pressure drops here."],
    "flow_exit": ["Bye-bye! See you at the shelf.", "And... I'm out!"],
    "zoomed_out": ["Hey, you zoomed me\nout of the picture!", "Where did the plot go?!"],
    "vortex_dizzy": ["Round and round...\nclosed streamlines, no exit!", "I'm dizzy. Jumping out!"],
    "drain": ["Uh-oh, a drain...", "Not the sink, not the sink!"],
    "drain_gone": ["...bloop.", "Slurp!"],
    "stagnation": ["V = 0. I'm not stuck,\nI'm *stagnating*.", "A stagnation point.\nNothing moves here. Boring!"],
    "source": ["Too much pressure!", "Whoa, that source pushes!"],
    "solid": ["That's a solid body.\nBeavers can't swim in rock.", "Ouch! That's solid."],
    "wall": ["Ouch, a wall!", "Can't swim through walls."],
    "no_flow": ["No flow here... boring.", "Hello? Is there any flow?"],
    "flow_gone": ["Where did the flow go?"],
    "pulse_wait": ["What are those blinking things?", "I'll just stand here..."],
    "pulse_hit": ["Ow! Something hit my foot!", "Hey! Stop pushing!", "Oof!", "Not again!"],
    "pulse_bonk": ["BONK. Don't do that again!", "Ouch! My tail!"],
    "pulse_leave": ["Okay, I'm out of here.", "Enough pulses for today."],
    "no_pulses": ["No pulses? Quiet day."],
    "error": ["Uh-oh. Something's not physical.", "Hmm, that scene breaks physics."],
    "verify_ok": ["{n} out of {n}! I knew it.", "All {n} checks passed. Told you!"],
    "verify_fail": ["Some checks failed.\nNot my fault!"],
    "saved": ["Saved! Safe and sound."],
    "sleep": ["Zzz... potential flow...\nso smooth..."],
    "wake": ["Huh? I wasn't sleeping!", "I'm awake! Totally awake."],
    "facts": ["Fun fact: a doublet is a source\nand a sink kissing.",
              "Fun fact: in potential flow\na cylinder feels no drag.\n(d'Alembert was not amused.)",
              "Fun fact: lift = rho * V * Gamma.\nKutta and Joukowski said so.",
              "Fun fact: streamlines never cross.\nExcept at stagnation points.",
              "Fun fact: a free vortex spins\nbut its fluid does not rotate.",
              "Fun fact: phi lines and psi lines\nalways meet at right angles."],
}


class Picker:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.last = {}

    def pick(self, key: str, **fmt) -> str:
        options = LINES[key]
        choices = [o for o in options if o != self.last.get(key)] or options
        line = self.rng.choice(choices)
        self.last[key] = line
        return line.format(**fmt) if fmt else line
