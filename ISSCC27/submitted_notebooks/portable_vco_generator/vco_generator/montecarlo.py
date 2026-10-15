"""Local-mismatch Monte Carlo: same sized design, N seeded ngspice runs with the PDK's mismatch models switched on."""
import os
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from .netlist import VcoSpec
from .pdk import PDK
from .simulate import run_point


def monte_carlo(pdk: PDK, spec: VcoSpec, vctrl: float, n: int = 100, seed0: int = 1, jobs=None) -> dict:
    jobs = jobs or min(8, os.cpu_count() or 1)
    nom = run_point(pdk, spec, vctrl)
    with ThreadPoolExecutor(jobs) as ex:
        pts = list(ex.map(lambda s: run_point(pdk, spec, vctrl, mismatch=True, seed=s), range(seed0, seed0 + n)))
    f = np.array([p.f_hz for p in pts]); pw = np.array([p.p_w for p in pts])
    ok = np.isfinite(f)
    f, pw = f[ok], pw[ok]
    return {"pdk": pdk.name, "vctrl": vctrl, "n": int(ok.sum()), "seed0": seed0, "f_nominal_hz": nom.f_hz,
            "f_mean_hz": float(f.mean()), "f_std_hz": float(f.std(ddof=1)), "sigma_pct": float(100 * f.std(ddof=1) / f.mean()),
            "mean_shift_pct": float(100 * (f.mean() / nom.f_hz - 1)), "f_min_hz": float(f.min()), "f_max_hz": float(f.max()),
            "p_mean_w": float(pw.mean()), "p_sigma_pct": float(100 * pw.std(ddof=1) / pw.mean()),
            "frac_within_5pct": float(np.mean(np.abs(f / nom.f_hz - 1) < 0.05)), "f_hz": f.tolist()}
