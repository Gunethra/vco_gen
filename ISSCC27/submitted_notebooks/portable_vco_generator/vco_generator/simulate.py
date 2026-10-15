"""Run ngspice and extract metrics (frequency, power) from transient data."""
import os, shutil, subprocess, tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from pathlib import Path
import numpy as np
_trapz = getattr(np, "trapezoid", None) or np.trapz   # numpy 1.x and 2.x
from .netlist import VcoSpec, build_netlist
from .pdk import PDK, default_pdk_root


@dataclass
class Point:
    pdk: str; corner: str; temp: float; vdd: float; vctrl: float
    f_hz: float; p_w: float; e_cycle_j: float; n_cross: int

    def asdict(self): return asdict(self)


def _ngspice() -> str:
    exe = shutil.which("ngspice")
    if not exe:
        raise RuntimeError("ngspice not found on PATH (activate the environment)")
    return exe


def _measure(t, v, i, vdd, settle=0.35):
    mid = vdd / 2
    idx = np.where((v[:-1] < mid) & (v[1:] >= mid))[0]
    tc = t[idx] + (mid - v[idx]) * (t[idx + 1] - t[idx]) / (v[idx + 1] - v[idx])
    tc = tc[tc > settle * t[-1]]
    if len(tc) < 4:
        return float("nan"), float("nan"), len(tc)
    f = (len(tc) - 1) / (tc[-1] - tc[0])
    m = (t >= tc[0]) & (t <= tc[-1])
    p = vdd * float(-_trapz(i[m], t[m]) / (t[m][-1] - t[m][0]))
    return f, p, len(tc)


def run_point(pdk: PDK, spec: VcoSpec, vctrl: float, corner="tt", temp=27.0,
              vdd=None, tstop_ns=None, retries=3, mismatch=False, seed=None) -> Point:
    vdd = pdk.vdd if vdd is None else vdd
    tstop = tstop_ns or pdk.tstop_ns
    env = dict(os.environ, PDK_ROOT=str(default_pdk_root()))
    for _ in range(retries + 1):
        with tempfile.TemporaryDirectory() as d:
            dat = Path(d) / "out.dat"
            (Path(d) / "run.sp").write_text(
                build_netlist(pdk, spec, vctrl, corner, temp, tstop, vdd, str(dat), mismatch=mismatch, seed=seed))
            r = subprocess.run([_ngspice(), "-b", "run.sp"], cwd=d, env=env,
                               capture_output=True, text=True, timeout=600)
            if not dat.exists():
                raise RuntimeError("ngspice failed:\n" + (r.stdout + r.stderr)[-1500:])
            a = np.loadtxt(dat)
        f, p, n = _measure(a[:, 0], a[:, 1], a[:, 3], vdd)
        if n >= 6 or retries == 0:
            break
        tstop *= 4          # slow oscillation: lengthen the run and retry
    e = p / f if f == f and f > 0 else float("nan")
    return Point(pdk.name, corner, temp, vdd, vctrl, f, p, e, n)


def sweep(pdk: PDK, spec: VcoSpec, vctrls, corner="tt", temp=27.0, vdd=None, jobs=None):
    jobs = jobs or min(8, os.cpu_count() or 1)
    with ThreadPoolExecutor(jobs) as ex:
        return list(ex.map(lambda v: run_point(pdk, spec, v, corner, temp, vdd), vctrls))
