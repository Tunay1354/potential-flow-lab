"""
user_guide_text.py — the text of Help → User guide (app/user_guide.py): one chapter per part of the
program, plain HTML (what QTextBrowser shows). In a chapter {keys} is replaced by the table of the keyboard
shortcuts as they are set now (Edit → Keyboard shortcuts…), {app} by the program's name.

Keep it true to the program: when a feature changes, change its chapter here too.
"""

CHAPTERS = [
    ("start", "Getting started", """
<h2>Getting started</h2>
<p><b>{app}</b> builds two-dimensional, incompressible, irrotational (potential) flows by
<b>superposition</b> of elementary flows: uniform flow, source / sink, vortex, doublet, sector (wedge) flow and
straight walls. Everything you add is drawn at once: streamlines, stagnation points, and on request
equipotential lines, speed or pressure colours, solid bodies and the pressure on their surfaces.</p>
<h3>The window</h3>
<table>
<tr><td><b>Header</b></td><td>the program's name, the scene's file name (SHEET) and the <b>GPU</b> box
(draw with the graphics card).</td></tr>
<tr><td><b>Menus</b></td><td>File, Edit, Elements, View, Presets, Help — on the ruler under the header. The beaver
sits on the right of the ruler.</td></tr>
<tr><td><b>Add palette</b></td><td>left of the plot: one button per element type.</td></tr>
<tr><td><b>Plot</b></td><td>in the middle, with the buttons Static / Particles / Pulses, Select / Move / Pan,
Fit and Export above it.</td></tr>
<tr><td><b>Elements</b></td><td>right, top: the list of everything in the scene.</td></tr>
<tr><td><b>Plot settings</b></td><td>right, below: streamlines, layers, animations, computation.</td></tr>
<tr><td><b>Status bar</b></td><td>bottom: the values under the mouse (x, y, u, v, |V|, Cp, φ, ψ) and the
scene check.</td></tr>
</table>
<h3>Your first flow in one minute</h3>
<ol>
<li>Drag <b>Uniform</b> from the palette onto the plot (or click it) and press <b>Apply</b>: parallel
streamlines.</li>
<li>Drag <b>Doublet</b> to the middle and press <b>Apply</b>: the flow past a circular cylinder. The two
⊗ marks are the stagnation points.</li>
<li>Add a <b>Vortex</b> at the same place with Γ = −2: the lifting (rotating) cylinder; the stagnation
points move down.</li>
<li>Press <b>Particles</b> above the plot to watch the fluid move.</li>
</ol>
<p>The beaver can show you all this himself: Help → Beaver → Show me around (or click him).
Ready-made scenes are in the <b>Presets</b> menu — the first group holds the verification cases of the
assignment.</p>
"""),

    ("elements", "Adding elements", """
<h2>Adding elements</h2>
<p><b>Click</b> a palette button (or Elements → Add) to add an element in the middle of the view, or
<b>drag</b> it onto the plot to place it there. A window asks for its values; <b>Tab</b> goes to the next box,
<b>Apply</b> adds it, <b>Cancel</b> adds nothing.</p>
<table>
<tr><th>Element</th><th>Values</th><th>Meaning</th></tr>
<tr><td>Uniform flow</td><td>V∞, α</td><td>speed and direction (α counter-clockwise from +x)</td></tr>
<tr><td>Source / sink</td><td>|m|, source or sink, x₀, y₀</td><td>volume flow rate per unit depth;
a source pushes fluid out, a sink pulls it in</td></tr>
<tr><td>Vortex</td><td>|Γ|, direction, x₀, y₀</td><td>circulation; counter-clockwise is Γ &gt; 0</td></tr>
<tr><td>Doublet</td><td>μ, x₀, y₀, δ</td><td>strength and axis; with a uniform flow it makes a cylinder of radius
a = √(μ/V∞) when δ = α</td></tr>
<tr><td>Sector flow</td><td>|V|, direction, vertex, θ₁, θ₂</td><td>flow inside a wedge between the walls at θ₁
and θ₂</td></tr>
<tr><td>Wall</td><td>a point, θ<sub>w</sub>, fluid side</td><td>a straight impermeable wall (method of images);
the fluid is only on the chosen side</td></tr>
</table>
<p><b>Walls.</b> Every flow element gets its mirror images in every wall, so V·n = 0 holds on the wall exactly. One
wall, two walls meeting at 180°/k (90°, 60°, 45° …) and two parallel walls (a channel: the infinite rows of images
are summed in closed form) are exact; other corners are refused. A uniform flow must be parallel to every wall.</p>
<p><b>Sector flow and other elements.</b> A sector flow exists only inside its wedge, between the walls at θ₁ and
θ₂ — there is no fluid outside it. Its two sides are walls for the other elements: a source, vortex or doublet
inside the wedge gets mirror images in them, which is exact for β = 180°/k. The sector flow itself is not mirrored
(it already satisfies its walls). Refused, with a message: elements outside the wedge or on its sides, other
elements together with β &gt; 180°, a second sector flow, symmetry walls together with a sector flow, and a uniform
flow that is not parallel to the sides.</p>
<p>The window <b>checks the values while you type</b>. A <span class="warn">⚠ warning</span> means the result
may not be what you expect (for example a doublet whose axis is not along the flow: no closed cylinder). A
<span class="err">✖ error</span> means the scene would be physically inconsistent (for example a source
behind a wall); the button then says <b>Apply anyway</b>, and the plot shows a red strip until it is fixed.
Problems of other elements carry their list number, like <i>[2] …</i>.</p>
<p>Exact signs and angles: Help → Sign conventions.</p>
"""),

    ("editing", "Editing, moving, deleting", """
<h2>Editing, moving, deleting</h2>
<ul>
<li><b>Edit</b>: double-click the element in the list or its symbol on the plot, or select it and press
Enter, or the <b>Edit…</b> button, or Elements → (element) → Edit….</li>
<li><b>Move</b>: press <b>Move</b> above the plot (or M), then drag a symbol or a wall. Hold Shift to snap to
the grid; Esc cancels the drag. While you drag, the streamlines follow (Plot settings → Computation →
Live update while dragging).</li>
<li><b>Select</b>: click an element in the list or its symbol on the plot (click again where symbols overlap);
a click on empty space or Esc clears the selection.</li>
<li><b>Hide</b> an element for a moment: its tick box in the list.</li>
<li><b>Duplicate</b>: the Duplicate button or Ctrl+D (the copy is moved by (0.5, 0.5)).</li>
<li><b>Delete</b>: the Delete button, or the Delete key in the list or on the plot. File → Clear all removes
everything.</li>
<li><b>Undo / Redo</b>: Ctrl+Z / Ctrl+Y — every change, also loading a preset or clearing the scene.</li>
</ul>
"""),

    ("plot", "The plot", """
<h2>The plot</h2>
<ul>
<li><b>Zoom</b>: the mouse wheel (at the mouse). <b>Pan</b>: drag the empty plot, or the Pan mode (H).
<b>Fit</b> (F) shows all elements. The exact range can be typed in Plot settings → View range.</li>
<li><b>Mouse modes</b> above the plot: <b>Select</b> (V), <b>Move</b> (M), <b>Pan</b> (H).</li>
<li><b>Status bar</b>: x, y under the mouse with u, v, |V|, Cp, φ and ψ there; over a stagnation point its
details; "singular point" right at a source, vortex or doublet; "outside the fluid region" behind a
wall.</li>
<li><b>Stagnation points</b> (⊗, V = 0): click one to see its coordinates and the <b>dividing
streamlines</b> through it (thick dark lines). All of them at once: Layers → All dividing streamlines.</li>
<li><b>Scene check</b> (right of the status bar): ✔ scene OK, or the number of warnings / errors; click it
for the list.</li>
</ul>
<p>The streamlines are spaced evenly over the view (Density sets how close); they are computed in the
background, so the window stays responsive while they are drawn.</p>
"""),

    ("settings", "Plot settings and layers", """
<h2>Plot settings and layers</h2>
<p>The <b>Plot settings</b> panel (right) has sections; a right-click on its title (or View → Panels → Plot
settings sections) hides the ones you do not need.</p>
<table>
<tr><td><b>View range</b></td><td>x and y limits of the plot; Fit to elements.</td></tr>
<tr><td><b>Streamlines</b></td><td>Density (how many lines), Line width, Direction arrows and their
density.</td></tr>
<tr><td><b>Layers</b></td><td>what is drawn (also in View → Layers):
<br>Streamlines · All dividing streamlines · Stagnation points · Equipotential lines (φ) · Speed |V| colour
bands · Pressure coefficient Cp colour bands · Element markers · Walls · Solid bodies (filled) · Surface
pressure (Cp on surfaces) · Background grid.</td></tr>
<tr><td><b>Particles</b></td><td>Count, Speed, Trail length of the Particles animation.</td></tr>
<tr><td><b>Pulses</b></td><td>Speed, Pulse length, Spacing of the Pulses animation.</td></tr>
<tr><td><b>Computation</b></td><td>Grid quality of the colour bands and φ lines; the <b>Cp reference</b>
speed (V∞ of the uniform flow, or your own V_ref); Live update while dragging.</td></tr>
</table>
<p>The settings of the plot are saved with the scene. The panels can be moved to the other side and stacked
by dragging their titles; View → Panels → Reset layout brings back the first layout (the scene is not
touched).</p>
"""),

    ("animation", "Animation", """
<h2>Animation</h2>
<p>The three buttons at the left above the plot choose how the flow is shown:</p>
<ul>
<li><b>Static</b>: streamlines with direction arrows.</li>
<li><b>Particles</b>: tracer particles ride the flow; their colour is the speed (slow → fast) and they leave
short trails. Settings: Plot settings → Particles.</li>
<li><b>Pulses</b>: pulses run along the streamlines at the local speed — where the lines crowd, the flow is
fast. Settings: Plot settings → Pulses.</li>
</ul>
<p><b>Space</b> pauses and continues. Every view can be exported as a GIF or MP4 (Export → Animation).</p>
"""),

    ("bodies", "Bodies and surface pressure", """
<h2>Solid bodies and surface pressure</h2>
<p><b>Layers → Solid bodies</b> fills the regions the fluid never enters (the inside of a cylinder or a
Rankine oval, a half-body …). A source or doublet that the free stream passes <i>through</i> (for example a
doublet whose axis is not along the flow) makes no body.</p>
<p><b>Layers → Surface pressure</b> colours the surfaces of the bodies and the walls with Cp and opens the
<b>Surface pressure</b> panel on the left (it closes again when you untick the layer):</p>
<ul>
<li>the Cp distribution along the surface (by angle θ, arc length s or x); for a cylinder the analytic curve
is drawn dashed for comparison;</li>
<li>for a closed body, lift and drag per unit depth from the pressure integral, next to the Kutta–Joukowski
lift (L' = −ρ V∞ Γ) and d'Alembert's zero drag; with ρ the forces are in N/m;</li>
<li>moving the mouse over the graph marks the same point on the plot; <b>Export CSV…</b> saves the
numbers.</li>
</ul>
<p>The panel opens as wide as you left it last time.</p>
"""),

    ("files", "Files and presets", """
<h2>Files and presets</h2>
<ul>
<li><b>File → New</b> (Ctrl+N), <b>Open…</b> (Ctrl+O), <b>Save</b> (Ctrl+S), <b>Save as…</b>
(Ctrl+Shift+S), <b>Open recent</b>. Dropping a <i>.pflow</i> file on the window opens it too.</li>
<li>A scene file holds the elements, the title, the view and the plot settings, with every number exact:
saved and opened again, the list and the plot are the same. It is plain text (JSON).</li>
<li>Unsaved changes show a * in the title; the program asks before they could be lost.</li>
<li><b>Presets</b>: ready-made scenes. The first group, <i>Verification cases (assignment)</i>, holds the
cases of the assignment. A preset loads as a new, unsaved scene (Undo goes back). Your own presets: save a
scene into the presets folder (Presets → Show presets folder).</li>
<li>If the program ever closes unexpectedly, the next start offers to <b>restore</b> the unsaved scene (a
copy is kept a few seconds after every change).</li>
</ul>
"""),

    ("export", "Export", """
<h2>Export</h2>
<p>The <b>Export</b> button above the plot (or the File menu):</p>
<ul>
<li><b>Figure</b> (Ctrl+E): PNG, SVG or PDF of the plot as you see it, with the axes; resolution 1–4×,
background white / paper / transparent, axes on all four sides, light colours for printing.</li>
<li><b>Animation</b> (Ctrl+Shift+E): GIF or MP4 of Particles or Pulses; length, frame rate and resolution.</li>
<li><b>Data</b> (CSV): the elements, the stagnation points, the streamlines (points), the field on a grid
(u, v, |V|, Cp, φ, ψ) and the surface pressure, for Excel or MATLAB.</li>
</ul>
<p>Without opening the window (a terminal in the program's folder):<br>
<code>python main.py scene.pflow --figure out.png --data out.csv</code> — <code>python main.py --help</code>
lists every option.</p>
"""),

    ("verification", "Verification", """
<h2>Verification</h2>
<p><b>Help → Run verification…</b> checks the program against the theory (108 checks, about 15 s, in the
background):</p>
<ol>
<li><b>Analytic formulas</b>: velocities, flux, circulation, forces, wall images, sector flow — to round-off.</li>
<li><b>The assignment's verification scenes</b>: what the program draws and finds — streamline directions,
stagnation points, the surface r = a, Cp, lift and drag from the pressure integral against Kutta–Joukowski and
d'Alembert, save → open again gives the same list and plot — with each scene's figure.</li>
<li><b>Numerical methods</b>: ψ along the drawn streamlines, Newton's stagnation points, traced surfaces.</li>
</ol>
<p>Select a row to see how it is computed: the theory, what the program does, why its tolerance is what it is,
and the numbers. <b>Open full report</b> shows everything in the browser; the same report from a terminal:
<code>python main.py --verify</code>.</p>
"""),

    ("gpu", "Graphics card (GPU)", """
<h2>Graphics card (GPU)</h2>
<p>The <b>GPU</b> box in the header lets the graphics card draw the plot (OpenGL): smoother and faster, above
all the animations and busy scenes. It is off on the first start; the choice is remembered. Exports are the
same with and without it.</p>
<ul>
<li><b>Ticking or unticking the box restarts the program</b> (a few seconds): a program can choose its
graphics card only when it starts. Everything comes back as it was — the scene, its file name, unsaved
changes (still unsaved), the view, the layers, the animation. Nothing has to be saved first.</li>
<li>Laptops with an NVIDIA card: with the box ticked the program starts on the NVIDIA card. If Windows still
gives it the power-saving card, the program says so once and shows how to choose the card in Windows
(Settings → System → Display → Graphics). A laptop with another fast card (AMD): the program offers to switch
and restarts.</li>
<li>With the card the <b>Plot settings sliders reach further</b>: more streamlines, more particles (as many as
this computer moves in time), faster animations, longer trails and pulses. The bar keeps its length; a short
mark on it shows the limit without the card. Without the card the values above the mark come back to it.</li>
<li>The box is greyed out when the computer has no usable graphics card (point at it to see why).</li>
<li>If the card does not start drawing within a few seconds, the program goes back to drawing with the
processor by itself and says so; nothing is lost. If the program ever closes while the card draws, the next
start begins without it.</li>
</ul>
<h3>The Graphics card panel</h3>
<p>The small arrow beside the box (or View → Panels → Graphics card) opens a panel over the right part of the
window; the same arrow closes it. It works with and without the card: who draws, the frames per second (live)
and how long a frame takes, and the animations' <b>Frame rate</b> (Match screen, 60, 120, 144 — each mode
remembers its own). Its lower part only works with the card: <b>Higher limits in Plot settings</b> (on by
default) and the limits themselves.</p>
"""),

    ("beaver", "The beaver", """
<h2>The beaver</h2>
<p>{beaver}, the pixel beaver on the ruler, is your guide. <b>Click</b> him (or press <b>P</b>) for his menu:
questions &amp; answers, the tour, a fun fact. <b>Drag</b> him onto the plot: in Static mode he taps on the
glass in front of the plot; in Particles he rides the flow (and gets dizzy in a vortex); in Pulses the pulses
knock him along his streamline.</p>
<p><b>The tour</b> (Help → Beaver → Show me around) shows every part of the window and lets you build a
cylinder flow yourself. Enter, Space or → go on, ← goes back, Esc ends it.</p>
<p>View → Beaver switches him off. He never appears in exports.</p>
"""),

    ("keys", "Keyboard shortcuts", """
<h2>Keyboard shortcuts</h2>
<p>You can change them: Edit → Keyboard shortcuts…</p>
{keys}
<h3>Always</h3>
<table>
<tr><td><code>Delete</code></td><td>delete the selected element (in the list or on the plot)</td></tr>
<tr><td><code>Enter</code></td><td>edit the selected element (in the list)</td></tr>
<tr><td><code>Esc</code></td><td>clear the selection / cancel a drag</td></tr>
<tr><td><code>Shift</code> + drag</td><td>Move mode: snap to the grid</td></tr>
<tr><td><code>F1</code></td><td>this guide</td></tr>
</table>
"""),

    ("trouble", "If something goes wrong", """
<h2>If something goes wrong</h2>
<ul>
<li><b>An error window</b>: the program stays open and the scene is kept. Copy details, or send the log file
(Help → Open log folder → the .log file).</li>
<li><b>The first start is slow</b> (15–30 s): the fast engine is prepared for your processor once; later starts
take a few seconds.</li>
<li><b>Panels moved or closed</b>: View → Panels → Reset layout.</li>
<li><b>Nothing to see</b>: Fit (F) shows all elements; check the tick boxes in the Elements list and the Layers.</li>
<li><b>What the program found about your computer</b>: Help → Your computer….</li>
</ul>
"""),
]
