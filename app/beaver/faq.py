"""
faq.py — questions & answers (click the beaver or press P, then "Questions & answers"): the questions a first-time user asks, answered in
a few lines each. Keys 1–9, 0 pick a question.
"""

FAQ = [
    ("How do I add an element?",
     "Drag it from the ADD palette (left) onto the plot, or just click it: it lands in the middle of the view. "
     "Set its values and press Apply. Elements -> Add does the same."),
    ("How do I edit or delete one?",
     "Double-click it in the Elements list (or on the plot) to change its values. Select it and press Delete to "
     "remove it. Ctrl+Z undoes anything, Ctrl+Y redoes."),
    ("How do I move an element?",
     "Press MOVE (or M) above the plot and drag the element's symbol. In SELECT mode (V) a click only selects; "
     "PAN (H) drags the view. The mouse wheel zooms, F fits the view."),
    ("How do I build a (lifting) cylinder?",
     "Uniform flow + a doublet whose axis points along the flow. Put a vortex on the doublet for a lifting "
     "cylinder. Presets -> Verification cases has both, ready to open."),
    ("What are the crossed circles?",
     "Stagnation points: the velocity is zero there and Cp = 1. Click one to read its exact position. Lines "
     "starting from them (dividing streamlines) outline the bodies."),
    ("Why is there a red banner?",
     "The scene breaks a rule of potential flow, for example an element behind a wall. The banner tells why. "
     "Click the warnings in the status bar (bottom right) to read all of them."),
    ("How do I animate the flow?",
     "PARTICLES: tracer particles carried by the flow, colour = speed. PULSES: pulses running along the "
     "streamlines. Space pauses, STATIC goes back to arrows."),
    ("How do I see Cp, speed, lift?",
     "Plot settings -> Layers: Cp or |V| colour bands, equipotential (phi) lines, solid bodies, surface "
     "pressure. Surface pressure opens a panel with Cp along the body and the lift and drag."),
    ("How do I save and export?",
     "File -> Save (Ctrl+S) keeps your scene as a .pflow file. EXPORT (top right of the plot) writes a figure "
     "(PNG, SVG, PDF), an animation (GIF, MP4) or the data (CSV) for your report."),
    ("Is the program right?",
     "Help -> Run verification compares the program with the theory: 108 checks, each with how it is "
     "computed. All of them pass."),
]
