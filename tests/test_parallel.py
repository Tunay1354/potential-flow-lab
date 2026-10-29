"""The processor's cores (physics/parallel.py): the work is split into independent pieces and put together in
order — the streamlines and the field grids are bit for bit the same as on one core."""
import numpy as np
import pytest

from physics import Doublet, SectorFlow, Source, SymmetryWall, Uniform, Vortex, parallel


def test_chunks_cover_everything_in_order():
    for n in (0, 1, 2, 7, 64, 1000):
        for parts in (1, 3, 15):
            c = parallel.chunks(n, 3, parts)
            assert c[0][0] == 0 and c[-1][1] == n
            assert all(a < b for a, b in c) or n == 0
            assert all(c[i][1] == c[i + 1][0] for i in range(len(c) - 1))
            assert len(c) <= max(1, parts)
            if n >= 3:
                assert all(b - a >= 3 for a, b in c) or len(c) == 1
    assert parallel.chunks(0, 3) == [(0, 0)]                   # one empty piece: callers keep their empty case


def test_run_keeps_the_order_raises_errors_and_never_waits_for_itself(monkeypatch):
    monkeypatch.setenv("PFL_THREADS", "4")
    assert parallel.workers() == 4
    assert parallel.run([lambda k=k: k * k for k in range(9)]) == [k * k for k in range(9)]

    def boom():
        raise ValueError("x")
    with pytest.raises(ValueError):
        parallel.run([lambda: 1, boom, lambda: 3])
    # a task that itself asks for the cores (nested): runs them in its own thread, no deadlock
    nested = parallel.run([lambda: parallel.run([lambda: 1, lambda: 2]) for _ in range(8)])
    assert nested == [[1, 2]] * 8
    monkeypatch.setenv("PFL_THREADS", "1")
    assert parallel.workers() == 1 and parallel.run([lambda: 5, lambda: 6]) == [5, 6]


def test_workers_leave_one_thread_for_the_window(monkeypatch):
    monkeypatch.delenv("PFL_THREADS", raising=False)
    monkeypatch.setattr(parallel, "cpu_threads", lambda: 16)
    assert parallel.workers() == 15
    monkeypatch.setattr(parallel, "cpu_threads", lambda: 1)
    assert parallel.workers() == 1
    monkeypatch.setattr(parallel, "cpu_threads", lambda: 128)
    assert parallel.workers() == parallel.MAX_WORKERS


SCENES = [
    ([Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0)], ((-4, 4), (-3, 3))),
    ([Uniform(alpha=10.0), Source(m=2.0, x0=-2.5, y0=0.8), Source(m=-2.0, x0=-1.0, y0=0.8), Vortex(Gamma=2.0, x0=1.5, y0=1.0),
      Doublet(mu=0.6, x0=0.5, y0=-0.2, delta=10.0)], ((-4, 4), (-2.6, 2.6))),
    ([SymmetryWall(yw=-1.0), SymmetryWall(yw=1.0, side=1), Uniform(), Source(m=1.0, x0=-1.5, y0=0.3),
      Vortex(Gamma=1.0, x0=1.5, y0=-0.3)], ((-4, 4), (-1.2, 1.2))),
    ([SectorFlow(theta2=60.0), Source(m=1.0, x0=1.0, y0=0.3)], ((-0.5, 3.5), (-0.5, 2.5))),
]


def _lines(els, view):
    from physics.streamlines import StreamlineCache
    r = StreamlineCache(tuple(els), 1.0).update(view, 1.0, force=True)
    return r.lines, list(r.tapers)


@pytest.mark.parametrize("k", range(len(SCENES)))
def test_streamlines_on_several_cores_are_bit_for_bit_those_of_one_core(monkeypatch, k):
    els, view = SCENES[k]
    monkeypatch.setenv("PFL_THREADS", "1")
    a, ta = _lines(els, view)
    monkeypatch.setenv("PFL_THREADS", "4")
    b, tb = _lines(els, view)
    assert len(a) == len(b) > 5 and ta == tb
    assert all(x.shape == y.shape and np.array_equal(x, y, equal_nan=True) for x, y in zip(a, b))


def test_field_grids_on_several_cores_are_bit_for_bit_those_of_one_core(monkeypatch):
    from physics.field import PARALLEL_MIN_POINTS, complex_potential, complex_velocity
    X, Y = np.meshgrid(np.linspace(-4, 4, 301), np.linspace(-3, 3, 201))
    Z = X + 1j * Y
    assert Z.size > PARALLEL_MIN_POINTS
    for els, _view in SCENES:
        monkeypatch.setenv("PFL_THREADS", "1")
        w1, f1 = complex_velocity(els, Z), complex_potential(els, Z)
        monkeypatch.setenv("PFL_THREADS", "4")
        w4, f4 = complex_velocity(els, Z), complex_potential(els, Z)
        assert w4.shape == Z.shape and np.array_equal(w1, w4, equal_nan=True) and np.array_equal(f1, f4, equal_nan=True)


@pytest.mark.parametrize("keep_max", [False, True])
def test_segments_drawn_in_bands_are_the_same_picture(monkeypatch, keep_max):
    """Pulses / particles drawn by several cores (bands of rows) = drawn by one, bit for bit."""
    from physics import kernel
    rng = np.random.default_rng(3)
    n = 4000
    ax, ay = rng.uniform(-5, 405, n), rng.uniform(-5, 305, n)
    bx, by = ax + rng.uniform(-3, 3, n), ay + rng.uniform(-3, 3, n)
    band = rng.integers(-1, 4, n)
    pal = np.array([[200, 30, 30, 0.9], [30, 200, 30, 0.6], [30, 30, 200, 1.0], [90, 90, 90, 0.4]])
    alpha = rng.uniform(0.1, 1.0, n)
    one = np.zeros((300, 400, 4), np.uint8)
    kernel.draw_segments(one, ax, ay, bx, by, band, pal, 1.8, alpha, keep_max)
    monkeypatch.setenv("PFL_THREADS", "4")
    many = np.zeros_like(one)
    kernel.draw_segments_parallel(many, ax, ay, bx, by, band, pal, 1.8, alpha, keep_max)
    assert one.any() and np.array_equal(one, many)


def test_a_task_waiting_in_the_queue_is_done_by_the_caller(monkeypatch):
    """All cores busy with something long: the caller does the waiting tasks itself instead of waiting."""
    import threading
    import time
    monkeypatch.setenv("PFL_THREADS", "2")
    parallel.shutdown()
    release = threading.Event()
    blockers = [parallel.pool().submit(release.wait) for _ in range(2)]     # both pool threads busy
    try:
        t = time.perf_counter()
        out = parallel.run([lambda: 1, lambda: 2, lambda: 3])
        assert out == [1, 2, 3] and time.perf_counter() - t < 1.0
    finally:
        release.set()
        for b in blockers:
            b.result()
        parallel.shutdown()
