"""
origin.py — where the fluid at a point comes from (and goes to), the definition of a solid body.

A streamline is followed backwards (or forwards) from the point: it comes from the far field (free stream),
from a source / doublet or a closed loop round one (body fluid: inside a cylinder, a Rankine oval or
half-body), from any other closed loop (e.g. round a free vortex: real flow), or it stops somewhere unknown.
A source / doublet the free stream passes THROUGH makes no body (open_elements). The Solid bodies layer
(bodies.py), the body surfaces (surface.py) and the kinds of stagnation points (stagnation.py) all use this.

Also here: the free stream and the size of the body each element makes in it (body_size, bodies_box), and
whether a doublet's axis is along the flow at it (doublet_alignment, the same test as the warning).
"""
from __future__ import annotations

import numpy as np

from .field import active, complex_velocity, fluid_mask, reference_speed, singular_points
from .images import resolve


def has_free_stream(els) -> bool:
    """Fluid comes from far away: a uniform flow, or a sector flow (corner flow …). Without it there
    are no bodies (all fluid comes out of the sources)."""
    return reference_speed(els) is not None or any(e.TYPE == "sector" and e.V != 0 for e in els)


def _stream_speed(els, p) -> float | None:
    """Speed of the free stream at the point p: |V∞|, or the speed of the sector flow(s) there."""
    v = reference_speed(els)
    if v:
        return v
    far = resolve([e for e in els if e.TYPE == "sector"])
    if not far:
        return None
    for z in (p, p + abs(p) + 1.0):                       # (at a corner vertex the speed is 0)
        with np.errstate(all="ignore"):
            w = abs(complex_velocity(far, np.array([z], complex))[0])
        if np.isfinite(w) and w > 0:
            return float(w)
    return None


def body_size(els, e, p) -> float | None:
    """Size of the body (or ring of turning fluid) an element would make in the free stream at its
    point p: cylinder radius √(μ/V), half-body width m/V, stagnation distance Γ/(2πV)."""
    v = _stream_speed(els, p)
    if not v:
        return None
    if e.TYPE == "doublet":
        return float(np.sqrt(abs(e.mu) / v))
    if e.TYPE == "source":
        return abs(e.m) / v
    if e.TYPE == "vortex":
        return abs(e.Gamma) / (2.0 * np.pi * v)
    return None


def bodies_box(els, margin: float = 4.0):
    """A box round every source, doublet and vortex, `margin` × the size of its body (body_size);
    None without a free stream or such elements."""
    if not els or not has_free_stream(els):
        return None
    box = None
    for e in els:
        for p in (e.singular_points() if e.TYPE in ("doublet", "source", "vortex") else ()):
            size = body_size(els, e, p)
            if not size:
                continue
            r = margin * size
            b = (p.real - r, p.real + r, p.imag - r, p.imag + r)
            box = b if box is None else (min(box[0], b[0]), max(box[1], b[1]), min(box[2], b[2]), max(box[3], b[3]))
    return box


def box_union(a, b):
    return a if b is None else (min(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), max(a[3], b[3]))


def _far_field_box(region, els=()):
    """Where a traced line counts as "from / to the far field": 3× the region, and wide enough round
    every source, doublet and vortex for its body (or ring of turning fluid) to fit inside — else, in
    a view zoomed into part of a body, a line turning inside the body would leave the box and count
    as free stream."""
    x0, x1, y0, y1 = region
    L = max(x1 - x0, y1 - y0)
    return box_union((x0 - L, x1 + L, y0 - L, y1 + L), bodies_box(els))


def make_tracer(els, scale):
    from .streamlines import StreamlineField
    return StreamlineField(els, scale / 80.0)


# where the fluid at a point comes from (the streamline through it, followed backwards)
FAR, LOOP, BODY, STOPPED, OPEN = 0, 1, 2, 3, 4
MASS_TYPES = ("source", "doublet")            # elements that make bodies (a vortex alone does not)


def trace_origin(elements, z, region, scale=None) -> np.ndarray:
    """For every point z, where its streamline comes from, followed BACKWARDS:
        FAR   the far field (a box 3× the region): fluid of the free stream
        BODY  it starts at a source or a doublet, or turns in a closed loop round one: fluid of a
              body (inside a cylinder or a Rankine oval / half-body; with a fast-spinning cylinder
              also the ring of fluid that turns with it)
        OPEN  it starts at a source or a doublet that the free stream passes THROUGH (open_elements:
              a doublet not along the flow at it, a tilted source–sink pair): real flow, no body
        LOOP  any other closed loop (e.g. round a free vortex in a uniform flow): real flow, no body
        STOPPED the line stopped anywhere else (e.g. next to a stagnation point, where the flow is
              too slow to follow): unknown
    This is THE definition of a body (stagnation point kinds, which dividing lines are drawn,
    bodies.py)."""
    return trace_ends(elements, z, region, scale, -1.0)[0]


def trace_ends(elements, z, region, scale=None, sign: float = -1.0):
    """The streamline through every point z followed backwards (sign −1, see trace_origin) or forwards
    (+1: where the fluid GOES; BODY = into a sink or a doublet). Returns (kinds, element): element =
    index (in active(elements)) of the source / doublet the line ends at, −1 if none."""
    els = active(elements)
    out, which, loops = _trace_raw(els, z, region, scale, sign)
    if not ((out == BODY).any()):
        return out, which
    opened = open_elements(els)
    if opened:
        for k in np.nonzero(out == BODY)[0]:
            owners = loops.get(k)                       # closed loop: the mass elements it goes round
            if owners is not None:
                if all(i in opened for i in owners):
                    out[k] = OPEN
            elif which[k] in opened:
                out[k] = OPEN
    return out, which


def _trace_raw(els, z, region, scale, sign):
    """trace_ends without open_elements: (kinds, element, {line: elements a BODY loop goes round})."""
    z = np.atleast_1d(np.asarray(z, complex))
    out = np.full(z.size, STOPPED, dtype=np.int8)
    which = np.full(z.size, -1, dtype=np.int64)
    loops = {}
    if z.size == 0:
        return out, which, loops
    x0, x1, y0, y1 = region
    scale = scale or max(x1 - x0, y1 - y0)
    lines, closed, left, r_sing = _trace_staged(els, z, sign, region, scale)
    out[left] = FAR
    out[~left & closed] = LOOP
    owner = [(i, p) for i, e in enumerate(els) if e.TYPE in MASS_TYPES for p in e.singular_points()]
    if not owner:
        return out, which, loops
    mass = np.array([p for _i, p in owner], dtype=complex)
    for k in np.nonzero(~left)[0]:
        ln = lines[k]
        if closed[k]:
            if len(ln) > 2:
                inside = _encloses(ln, mass)
                if inside.any():
                    out[k] = BODY
                    loops[k] = {owner[j][0] for j in np.nonzero(inside)[0]}
        else:
            end = ln[-1] if len(ln) else z[k]
            d = np.abs(mass - end)
            if np.min(d) < 4.0 * r_sing[k]:              # lines stop r_sing before a singular point
                out[k] = BODY
                which[k] = owner[int(np.argmin(d))][0]
    return out, which, loops


STAGE_GROWTH = 8.0      # staged tracing: each stage's box (and step) this many times the one before
MAX_STAGE_SPAN = 200.0   # the first stage's box at most this many tracing scales wide (~16 000 steps across)


def _trace_staged(els, z, sign, region, scale):
    """free_trace of the points z inside the far-field box of `region` (_far_field_box): (lines, closed,
    left, r_sing of the tracer each line ended with). Normally one trace at `scale`. Zoomed far into a
    scene the far-field box (it holds every body: bodies_box) is thousands of view sizes wide, and a line
    traced across it with the view's tiny step took millions of steps (the Solid bodies layer froze the
    window for seconds at every zoom step). Then the lines are traced in stages: in 3×
    the region at `scale`, those that leave it go on from where they left in a box STAGE_GROWTH× larger
    with a STAGE_GROWTH× larger step, and so on until the far-field box. A closed line is the loop of the
    stage it closed in (it came back to where that stage began). The first stage's box is also kept
    within MAX_STAGE_SPAN scales round the points: probes round a stagnation point (a scale of a few
    units) in a scene whose elements are 10⁵ apart (its region as wide) took millions of steps per line
    and gigabytes (the random test: Surface pressure computing for minutes, then out of memory)."""
    x0, x1, y0, y1 = region
    L = max(x1 - x0, y1 - y0)
    far = _far_field_box(region, els)
    box = (x0 - L, x1 + L, y0 - L, y1 + L)
    if _box_size(box) > MAX_STAGE_SPAN * scale:
        h = 0.5 * MAX_STAGE_SPAN * scale
        box = (max(box[0], z.real.min() - h), min(box[1], z.real.max() + h),
               max(box[2], z.imag.min() - h), min(box[3], z.imag.max() + h))
    n = z.size
    lines = [np.zeros(0, complex) for _ in range(n)]
    closed = np.zeros(n, bool)
    left = np.zeros(n, bool)
    r_sing = np.zeros(n)
    todo, starts, s = np.arange(n), z.copy(), scale
    v_min = None
    while True:
        last = _box_size(far) <= STAGE_GROWTH * _box_size(box) * (1.0 + 1e-12)
        if last:
            box = far
        tracer = make_tracer(els, s)
        if v_min is None:                  # "too slow = stopped" as for one trace across the far-field box
            from .streamlines.level import _stagnation_speed
            v_min = _stagnation_speed(tracer.els, tracer.flows, far) or 0.0
        tracer.v_min = v_min
        got, shut, out = tracer.free_trace(starts, sign, box)
        shut, out = np.asarray(shut, bool), np.asarray(out, bool)
        for j, k in enumerate(todo):
            lines[k] = got[j] if shut[j] else np.concatenate([lines[k], got[j]])
            closed[k], r_sing[k] = shut[j], tracer.r_sing
        go_on = out & ~shut
        if last or not go_on.any():
            left[todo[go_on]] = True
            return lines, closed, left, r_sing
        starts = np.array([got[j][-1] if len(got[j]) else starts[j] for j in np.nonzero(go_on)[0]], complex)
        todo = todo[go_on]
        cx, cy, h = 0.5 * (box[0] + box[1]), 0.5 * (box[2] + box[3]), 0.5 * STAGE_GROWTH * _box_size(box)
        box = (max(cx - h, far[0]), min(cx + h, far[1]), max(cy - h, far[2]), min(cy + h, far[3]))
        s *= STAGE_GROWTH


def _box_size(b):
    return max(b[1] - b[0], b[3] - b[2])


# ---------------------------------------------------------------------- the flow at a singular point
ALIGN_TOL_DEG = 0.5      # doublet axis vs the flow at it: within this the body is (practically) closed —
                         # the free stream through it is ≈ (angle in rad) × the flow the body blocks


def flow_at(flows, sing, p) -> complex | None:
    """Velocity u + i v at the point p made by everything EXCEPT the singular points at p (a doublet,
    a vortex at its center, a source): the mean of w over a small ring round p — the terms
    1/(z − p)^k of those average to zero, the rest is analytic there (mean value property). None if 0."""
    sing = np.asarray(sing, complex)
    near = np.abs(sing - p)
    near = near[near > 1e-9 * (1.0 + abs(p))]
    r = 1e-3 * (min(1.0, float(near.min())) if near.size else 1.0)
    ring = p + r * np.exp(2j * np.pi * (np.arange(32) + 0.5) / 32)
    with np.errstate(all="ignore"):
        w = complex(np.mean(complex_velocity(flows, ring)))
    if not np.isfinite(w) or abs(w) < 1e-12:
        return None
    return complex(np.conj(w))


def doublet_alignment(els, e, flows=None, sing=None):
    """(angle of the flow at the doublet e in degrees, axis − angle in −180 … 180) or None (no flow
    there). The doublet makes a closed body only when its axis (δ, + 180° for μ < 0) is along that flow:
    otherwise part of the free stream goes in at one side and out at the other (as for δ ≠ α)."""
    flows = resolve(els) if flows is None else flows
    sing = singular_points(els) if sing is None else sing
    local = flow_at(flows, sing, e.z0)
    if local is None or e.mu == 0:
        return None
    angle = float(np.degrees(np.angle(local)))
    axis = e.delta + (180.0 if e.mu < 0 else 0.0)
    return angle, (axis - angle + 180.0) % 360.0 - 180.0


def speed_at(flows, sing, p) -> float:
    v = flow_at(flows, sing, p)
    return 0.0 if v is None else abs(v)


# ---------------------------------------------------------------------- free stream through a body?
RING_POINTS = 64                 # open_elements: points round every source / doublet
_OPEN_CACHE: dict = {}


def open_elements(elements) -> frozenset:
    """See _groups: the sources / doublets the free stream passes THROUGH (indices in active(elements))."""
    return _groups(elements)[0]


def _groups(elements):
    """(open, no_outflow): the sources / doublets (indices in active(elements)) the free stream
    passes THROUGH, which therefore make no body; and those of the other groups that give out no more
    than they take in (no_outflow_elements). A real body cannot swallow the free stream: free-stream
    fluid flowing into a sink, a doublet not along the flow at it (δ ≠ α, or a vortex / source beside
    it turns the flow there; doublet_alignment, the same test as the warning in the status bar), a
    source–sink pair across the flow: what looks like a body has the free stream going in at one place
    and out at another.
    Test: streamlines from a small ring round every source / doublet, followed both ways. Elements
    whose fluid reaches each other form a group; a group is open when free-stream fluid flows into
    one of its sinks or a doublet is not aligned, or when its fluid goes off to the far field although
    its sources do not give more than its sinks take in. (A source with more outflow — the Rankine
    half-body — is no such case: its body is open downstream.) Depends on the scene only, not on the
    view: the same answer at every zoom (cached per scene)."""
    els = active(elements)
    if not has_free_stream(els):
        return frozenset(), frozenset()
    import json
    key = tuple(json.dumps(e.to_dict(), sort_keys=True) for e in els)
    hit = _OPEN_CACHE.get(key)
    if hit is not None:
        return hit
    mass = [(i, complex(p)) for i, e in enumerate(els) if e.TYPE in MASS_TYPES for p in e.singular_points()]
    sing = np.array(singular_points(els), dtype=complex)
    parent = {i: i for i, _p in mass}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    takes_far, sends_far = set(), set()
    flows = resolve(els)
    for i, e in enumerate(els):
        # a doublet: open exactly when its axis is not along the flow at it — the same test as the
        # warning in the status bar (validation), so the picture and the message always agree. (Small
        # leaks of an aligned doublet in a non-uniform flow are left as a body: practically closed.)
        if e.TYPE == "doublet":
            al = doublet_alignment(els, e, flows, sing)
            if al is not None and abs(al[1]) > ALIGN_TOL_DEG:
                takes_far.add(i)
    for i, p in mass:
        e = els[i]
        if (e.TYPE == "source" and e.m == 0) or (e.TYPE == "doublet" and e.mu == 0):
            continue
        size = body_size(els, e, p)
        if not size:
            continue
        # well inside the fluid the element owns: 0.3 × the cylinder radius, 0.2 × the distance of a
        # half-body's stagnation point m/(2πV)
        r = 0.3 * size if e.TYPE == "doublet" else 0.2 * size / (2.0 * np.pi)
        others = np.abs(sing - p)
        others = others[others > 1e-9 * (1.0 + abs(p))]
        if others.size:
            r = min(r, 0.3 * float(others.min()))
        ring = p + r * np.exp(2j * np.pi * (np.arange(RING_POINTS) + 0.5) / RING_POINTS)
        ring = ring[fluid_mask(els, ring)]
        if not ring.size:
            continue
        region = (p.real - r, p.real + r, p.imag - r, p.imag + r)
        for sign, far_set in ((-1.0, takes_far), (1.0, sends_far)):
            kinds, ends, _loops = _trace_raw(els, ring, region, 20.0 * r, sign)
            if (kinds == FAR).any() and e.TYPE != "doublet":    # doublets: by their alignment (below)
                far_set.add(i)
            for j in set(ends[ends >= 0].tolist()):
                if j in parent:
                    parent[find(j)] = find(i)
    groups: dict = {}
    for i, _p in mass:
        groups.setdefault(find(i), set()).add(i)
    opened, no_outflow = set(), set()
    for members in groups.values():
        net = sum(els[i].m for i in members if els[i].TYPE == "source")
        scale = sum(abs(els[i].m) for i in members if els[i].TYPE == "source")
        takes = any(i in takes_far and not (els[i].TYPE == "source" and els[i].m > 0) for i in members)
        zero = net <= 1e-9 * (1.0 + scale)
        through = zero and any(i in sends_far for i in members)
        if takes or through:
            opened |= members
        elif zero:
            no_outflow |= members
    out = (frozenset(opened), frozenset(no_outflow))
    if len(_OPEN_CACHE) > 16:
        _OPEN_CACHE.clear()
    _OPEN_CACHE[key] = out
    return out


def no_outflow_elements(elements) -> frozenset:
    """The sources / doublets (indices in active(elements)) of closed groups that give out no more
    than they take in (a doublet, a Rankine oval): their body closes on itself, so fluid that comes
    out of them and goes off to the far field is no body fluid (an aligned doublet in a non-uniform
    flow lets a hair of free stream through; without this it showed as a thin tail)."""
    return _groups(elements)[1]


def _encloses(ring, pts) -> np.ndarray:
    """True for the points inside the closed polyline `ring` (complex), even-odd rule."""
    a, b = ring, np.roll(ring, -1)
    inside = np.zeros(pts.size, bool)
    for k, p in enumerate(pts):
        up = (a.imag > p.imag) != (b.imag > p.imag)
        with np.errstate(divide="ignore", invalid="ignore"):
            x = a.real + (p.imag - a.imag) * (b.real - a.real) / (b.imag - a.imag)
        inside[k] = np.count_nonzero(up & (p.real < x)) % 2 == 1
    return inside
