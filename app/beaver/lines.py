"""
lines.py — what the beaver says (English). One key per situation, many lines per key; pick() takes a random
line of a key, never one of the last few said for that key, so the jokes do not repeat quickly.

PRIORITY: 2 = an event he must tell (waits until the line before it can be read), 1 = normal (skipped if he
is still talking), 0 = small talk (skipped if he is talking).
"""
import random

NAME = "Psi"            # his name (a placeholder: the owner will choose one); shown on his speech bubbles

LINES = {
    "hello": ["Hi! I'm Psi, your flow buddy.\nGrab me and drop me on the plot!",
              "Hello there! I'm Psi.\nDrag me onto the plot, I dare you."],
    "menu": ["What can I do for you?", "Yes? Need a paw?", "Hi! How can I help?", "At your service!"],
    "poked": ["Hey! I'm busy!", "Hehe, that tickles.", "Not now, I'm working!", "Boop!", "Paws off, I'm flowing!"],
    "ask_tour": ["Hi! I'm Psi, your flow buddy. First time here? Want a quick tour? It takes about two minutes.",
                 "Hello! I'm Psi. Looks like you're new here. Shall I show you around? Two minutes, promise."],
    "tour_declined": ["Okay! Click me or press P whenever you need help.",
                      "No problem. Click me any time, I'll show you around later."],
    "rescue": ["Okay, that's enough flow for me. Home!", "Phew, I've been out long enough. Back to my shelf!",
               "Time's up! Hop, hop, home.", "That's my lot for today. Shelf time!"],
    "menu_bye": ["Okay! I'm here if you need me.", "Alright. Click me or press P if you need me.",
                 "Sure. I'll be on my shelf if you need me.", "No problem. I'm right here if you need me."],
    "tour_clear_unsaved": ["The tour starts on an empty sheet, and your scene has unsaved changes. Save it first?",
                           "Before we start: the tour clears the plot, and your scene isn't saved. Save it first?"],
    "tour_clear_saved": ["The tour starts on an empty sheet. Your scene is saved, so I'll clear the plot. Okay?",
                         "The tour needs an empty sheet. Your scene is saved: shall I clear the plot?"],
    "tour_later": ["Okay, maybe later! Click me when you're ready.", "No problem. The tour waits for you."],
    "tour_skipped": ["Okay! The tour is in Help -> Beaver, or click me.", "Tour ended. Click me if you need me!"],
    "tour_nice": ["Nice!", "Well done!", "Perfect!", "Just like that!", "You're a natural!", "Great!"],
    "welcome_back": ["Welcome back!", "Oh, you're back! Let's flow.", "Hello again!", "Ready for more streamlines?"],
    "grabbed": ["Whoa, whoa!", "Hey, hey! What are you doing?!", "Put me down gently,\nI bruise like a peach.",
                "Wheee— wait, where are we going?", "Careful, that's my good scruff!",
                "I can walk, you know.", "Up we go! I hope you know\nwhat you're doing.",
                "Is this a field trip?", "Don't drop me in a sink!", "Okay, okay, I'm coming!"],
    "glass_drop": ["Did you think I'd fall?", "Ha! Did you think I'd fall?", "Nope. Not falling today.",
                   "Surprise! I'm still here.", "Bonk. Hello, glass.", "Still floating. Magic? No: glass."],
    "glass_tap": ["Static mode: there's glass\nin front of the plot. *tap tap*",
                  "See? Glass. Static mode\nkeeps the flow behind it.",
                  "*tap tap* Anybody in there?\nThe flow is behind the glass.",
                  "I can see the streamlines,\nbut I can't touch them. Sad.",
                  "Switch to Particles or Pulses\nif you want me to get wet.",
                  "This glass is very clean.\nI should know, I'm licking it."],
    "glass_back": ["Nice try. Back to my shelf!", "Okay, back to my shelf.", "I'll be on my ruler if you need me.",
                   "Show's over. Home time!", "Fine, I'll walk back. Again."],
    "glass_again": ["Hey! Who put the glass back?", "Wait, the glass is back?!", "Static mode again? Clunk."],
    "splash": ["Splash!", "Into the flow we go!", "Cannonball!", "Glass is gone. SPLASH!"],
    "flow_start": ["Wheee!", "Here we go!", "Riding the streamlines!", "Like a particle, but cuter.",
                   "Following the flow!", "I'm a tracer now!", "Off I go, wherever the flow goes."],
    "flow_too_fast": ["Whoa, way too fast!", "AAAAH, speed slider!", "Too fast to wave hello!",
                      "Somebody turned the speed up!"],
    "flow_slow": ["Hmm, this flow is... slow.", "Is it moving? I think it's moving.",
                  "At this speed I'll arrive\nnext semester.", "Slow and steady... very slow."],
    "flow_bored": ["This is taking forever.\nI'll walk, thanks.", "Wake me up when we get there.\n...Actually, never mind.",
                   "Even creeping flow is faster.\nBye!", "Booooring. I'm out.",
                   "I've got better things to do.\nLike gnawing a pencil."],
    "flow_fast": ["Wheee! Faster over the top!", "Circulation, baby!", "So fast! Bernoulli says\nthe pressure drops here.",
                  "Speed up, pressure down!", "Fast lane!", "Hold on to your tail!", "Zoom zoom!"],
    "flow_exit": ["Bye-bye! See you at the shelf.", "And... I'm out!", "That was fun! Again?",
                  "Exit stage right!", "Off the edge of the plot!", "Out of the view, into the unknown!"],
    "paused": ["Frozen in time!", "Hey, who pressed pause?", "I can't move! Is this Space?",
               "Paused. Like my heartbeat."],
    "paused_leave": ["Still paused? I'll walk.", "Fine, I'll find my own way home."],
    "zoomed_out": ["Hey, you zoomed me\nout of the picture!", "Where did the plot go?!", "I'm off the map!",
                   "Panned away? Rude."],
    "vortex_dizzy": ["Round and round...\nclosed streamlines, no exit!", "I'm dizzy. Jumping out!",
                     "A free vortex never lets go.\nI'll jump!", "Lap two. Enough. Bleh.",
                     "The streamlines are circles!\nI'm going in circles!"],
    "drain": ["Uh-oh, a drain...", "Not the sink, not the sink!", "Why is everything spiralling?",
              "I see a whirlpool. I don't like it."],
    "drain_gone": ["...bloop.", "Slurp!", "Glug glug...", "Bye...ee...ee..."],
    "stagnation": ["V = 0. I'm not stuck,\nI'm *stagnating*.", "A stagnation point.\nNothing moves here. Boring!",
                   "Velocity zero. Pressure max.\nFeels squeezy.", "Stuck at the front of the body!",
                   "Cp = 1. That's me."],
    "source": ["Too much pressure!", "Whoa, that source pushes!", "Out of the source, into the flow!",
               "A source! It's all coming at me!"],
    "solid": ["That's a solid body.\nBeavers can't swim in rock.", "Ouch! That's solid.",
              "No fluid in there. Only body.", "Can't swim in a cylinder."],
    "wall": ["Ouch, a wall!", "Can't swim through walls.", "There's no fluid behind that wall.",
             "Wrong side of the wall!"],
    "no_flow": ["No flow here... boring.", "Hello? Is there any flow?", "Add some elements first!",
                "Empty plot, empty heart."],
    "flow_gone": ["Where did the flow go?", "The flow vanished!", "Hey, I was swimming in that!"],
    "pulse_wait": ["What are those blinking things?", "I'll just stand here...", "Nice line. I'll stand on it.",
                   "Something's coming...", "Is that a pulse?"],
    "pulse_hit": ["Ow! Something hit my foot!", "Hey! Stop pushing!", "Oof!", "Not again!", "Ouch!",
                  "Who keeps doing that?!", "My tail!", "I'm being swept away!", "Pulse again?!"],
    "pulse_bonk": ["BONK. Don't do that again!", "Ouch! My tail!", "End of the line. Literally.",
                   "Who put an edge here?!", "That's it, I'm going home."],
    "pulse_slow": ["These pulses are sooo slow.", "I could walk faster than those pulses.",
                   "Ha! Catch me if you can!", "Nope, not waiting for that one."],
    "pulse_run": ["Running away! Bye!", "Too slow, pulses!", "See you, slowpokes!", "I'll take the shortcut!"],
    "pulse_leave": ["Okay, I'm out of here.", "Enough pulses for today.", "My feet hurt. Home!"],
    "no_pulses": ["No pulses? Quiet day.", "No lines here to stand on."],
    "error": ["Uh-oh. Something's not physical.", "Hmm, that scene breaks physics.",
              "Red banner! Someone fix that.", "That's not potential flow,\nthat's potential trouble."],
    "verify_ok": ["{n} out of {n}! I knew it.", "All {n} checks passed. Told you!", "Verified! The math holds water.",
                  "{n} green checks. Beautiful."],
    "verify_fail": ["Some checks failed.\nNot my fault!", "Hmm, not all green.\nLet's look at the red ones."],
    "saved": ["Saved! Safe and sound.", "Saved. Good habit!", "In the file! Nice."],
    "sleep": ["Zzz... potential flow...\nso smooth...", "Zzz... irrotational dreams...", "Zzz... phi... psi... zzz"],
    "wake": ["Huh? I wasn't sleeping!", "I'm awake! Totally awake.", "Five more minutes...", "Whuh? Who? Flow?"],
    "facts": ["Fun fact: a doublet is a source\nand a sink kissing.",
              "Fun fact: in potential flow\na cylinder feels no drag.\n(d'Alembert was not amused.)",
              "Fun fact: lift = rho * V * Gamma.\nKutta and Joukowski said so.",
              "Fun fact: streamlines never cross.\nExcept at stagnation points.",
              "Fun fact: a free vortex spins\nbut its fluid does not rotate.",
              "Fun fact: phi lines and psi lines\nalways meet at right angles.",
              "Fun fact: a uniform flow plus\na source makes a Rankine half-body.",
              "Fun fact: a symmetry wall is just\na mirror for the flow.",
              "Fun fact: real beavers build dams.\nI build streamlines."],
}

PRIORITY = {k: 1 for k in LINES}
PRIORITY.update({k: 2 for k in ("glass_drop", "glass_tap", "glass_back", "glass_again", "flow_exit", "flow_bored",
                                "zoomed_out", "vortex_dizzy", "drain_gone", "stagnation", "solid", "wall", "no_flow",
                                "flow_gone", "pulse_bonk", "pulse_run", "pulse_leave", "no_pulses", "paused_leave",
                                "error", "verify_ok", "verify_fail", "hello", "flow_slow", "pulse_slow", "paused",
                                "flow_too_fast", "saved", "tour_declined",
                                "tour_skipped", "menu_bye", "tour_later", "rescue")})
PRIORITY.update({k: 0 for k in ("flow_fast", "pulse_wait", "sleep", "welcome_back")})


class Picker:
    def __init__(self, seed=None, memory: int = 3):
        self.rng = random.Random(seed)
        self.recent = {}
        self.memory = memory

    def pick(self, key: str, **fmt) -> str:
        options = LINES[key]
        recent = self.recent.setdefault(key, [])
        choices = [o for o in options if o not in recent] or options
        line = self.rng.choice(choices)
        recent.append(line)
        del recent[:-min(self.memory, max(1, len(options) - 1))]
        return line.format(**fmt) if fmt else line
