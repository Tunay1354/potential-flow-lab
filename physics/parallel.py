"""
parallel.py — the processor's cores for the computations (always on, nothing to set).

One pool of worker threads, made the first time it is needed, with one thread less than the computer has
(that one is for the window). Only work that RELEASES Python's interpreter lock runs truly in parallel: the
compiled streamline tracer (kernel.trace_batch, nogil) and large NumPy array arithmetic (the velocity / φ
grids of the field layers, the CSV export).

Results are bit-for-bit the same as with one core: the work is split into independent pieces (seeds,
rows of a grid) whose results are put together in the original order; no sum is reordered.

    PFL_THREADS=1 python main.py        all on one core (to compare, or if something looks wrong)
"""
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor

MAX_WORKERS = 32
_lock = threading.Lock()
_pool: ThreadPoolExecutor | None = None
_inside = threading.local()            # a pool thread itself never waits for the pool (no deadlock)


def cpu_threads() -> int:
    n = getattr(os, "process_cpu_count", os.cpu_count)()
    return max(1, int(n or 1))


def workers() -> int:
    """Threads used for one computation: the computer's threads − 1 (≥ 1, ≤ MAX_WORKERS), or PFL_THREADS."""
    env = os.environ.get("PFL_THREADS", "").strip()
    if env.isdigit() and int(env) >= 1:
        return min(int(env), MAX_WORKERS)
    return max(1, min(cpu_threads() - 1, MAX_WORKERS))


def _mark():
    _inside.flag = True


def pool() -> ThreadPoolExecutor:
    global _pool
    with _lock:
        if _pool is None:
            _pool = ThreadPoolExecutor(max_workers=workers(), thread_name_prefix="pflab-core", initializer=_mark)
        return _pool


def run(tasks: list) -> list:
    """Call every task (a function without arguments) and return their results in order. In parallel when
    there is more than one task and more than one core; the calling thread does the first task itself.
    An exception of a task is raised here (after all tasks have finished)."""
    if len(tasks) <= 1 or workers() <= 1 or getattr(_inside, "flag", False):
        return [t() for t in tasks]
    futures = [pool().submit(t) for t in tasks[1:]]
    first_error = None
    try:
        results = [tasks[0]()]
    except BaseException as exc:                     # noqa: BLE001 - raised after the others are done
        results, first_error = [None], exc
    for f, task in zip(futures, tasks[1:]):
        try:
            # a task no core has started yet (all busy, e.g. with a background computation) is done here at
            # once: a caller never waits in a queue behind other work (an animation frame would stutter)
            results.append(task() if f.cancel() else f.result())
        except BaseException as exc:                 # noqa: BLE001
            results.append(None)
            first_error = first_error or exc
    if first_error is not None:
        raise first_error
    return results


def chunks(n: int, min_size: int, parts: int | None = None) -> list[tuple[int, int]]:
    """[start, stop) ranges splitting range(n) into at most `parts` (default: workers()) pieces of at
    least min_size each, in order."""
    if n <= 0:
        return [(0, 0)]                                  # one empty piece: the callers' empty case stays as it was
    parts = workers() if parts is None else parts
    k = max(1, min(parts, n // max(1, min_size)))
    edges = [round(i * n / k) for i in range(k + 1)]
    return [(edges[i], edges[i + 1]) for i in range(k) if edges[i + 1] > edges[i]]


def shutdown():
    global _pool
    with _lock:
        if _pool is not None:
            _pool.shutdown(wait=False, cancel_futures=True)
            _pool = None
