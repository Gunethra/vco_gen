"""Target-frequency sizing and the standard characterization suite (same for every PDK)."""
import json, math
from dataclasses import replace
from pathlib import Path
import numpy as np
from .netlist import VcoSpec
from .pdk import PDK
from .simulate import run_point, sweep

CORNERS = ("tt", "ss", "ff", "sf", "fs")
TEMPS = (-40.0, 27.0, 125.0)


def vctrl_mid(pdk: PDK, vdd=None) -> float:
    return 0.5 * (pdk.vctrl_lo + (pdk.vdd if vdd is None else vdd))


def size_for_frequency(pdk: PDK, spec: VcoSpec, f_target: float, tol=0.01, iters=14):
    """Bisect the starving-device width (log scale) so f(vctrl_mid, tt, 27C) hits f_target."""
    vm = vctrl_mid(pdk)
    lo, hi = pdk.wmin_um, 40.0 / (spec.starve_pn or pdk.pn_ratio)   # PMOS width <= 40 um (model bins)
    f = lambda w: run_point(pdk, replace(spec, ws_um=w), vm).f_hz
    flo = f(lo)
    while flo > f_target and spec.l_starve_factor < 16:      # width floor hit: lengthen instead
        spec = replace(spec, l_starve_factor=spec.l_starve_factor * 2)
        flo = f(lo)
    fhi = f(hi)
    if not flo <= f_target <= fhi:
        raise ValueError(f"{pdk.name}: target {f_target/1e6:.0f} MHz outside reachable "
                         f"{flo/1e6:.0f}..{fhi/1e6:.0f} MHz for this topology")
    for _ in range(iters):
        mid = math.sqrt(lo * hi)
        fm = f(mid)
        if abs(fm - f_target) / f_target < tol:
            lo = hi = mid
            break
        lo, hi = (mid, hi) if fm < f_target else (lo, mid)
    return replace(spec, ws_um=round(math.sqrt(lo * hi), 3))


def characterize(pdk: PDK, spec: VcoSpec, npts=12) -> dict:
    vm = vctrl_mid(pdk)
    vs = np.linspace(pdk.vctrl_lo, pdk.vdd, npts)
    curve = sweep(pdk, spec, vs)
    f = np.array([p.f_hz for p in curve])
    k = np.gradient(f, vs)                       # Kvco curve [Hz/V]
    i = int(np.argmin(abs(vs - vm)))
    f_mid = run_point(pdk, spec, vm).f_hz
    corners = {c: run_point(pdk, spec, vm, corner=c).f_hz for c in CORNERS}
    temps = {t: run_point(pdk, spec, vm, temp=t).f_hz for t in TEMPS}
    vdd_lo, vdd_hi = 0.9 * pdk.vdd, 1.1 * pdk.vdd
    f_lo = run_point(pdk, spec, vm, vdd=vdd_lo).f_hz
    f_hi = run_point(pdk, spec, vm, vdd=vdd_hi).f_hz
    pm = run_point(pdk, spec, vm)
    return {
        "pdk": pdk.name, "vdd": pdk.vdd, "n_stages": spec.n_stages,
        "ws_um": spec.ws_um or pdk.w_unit_um, "starve_pn": spec.starve_pn or pdk.pn_ratio, "l_starve_factor": spec.l_starve_factor, "vctrl_mid": vm, "f_mid_hz": f_mid,
        "curve": {"vctrl": vs.tolist(), "f_hz": f.tolist(),
                  "p_w": [p.p_w for p in curve], "e_cycle_j": [p.e_cycle_j for p in curve]},
        "f_min_hz": float(f.min()), "f_max_hz": float(f.max()),
        "tuning_ratio": float(f.max() / f.min()),
        "kvco_mid_hz_per_v": float(k[i]),
        "p_mid_w": pm.p_w, "e_cycle_mid_j": pm.e_cycle_j,
        "corner_f_hz": corners,
        "corner_spread_pct": 100 * (max(corners.values()) - min(corners.values())) / f_mid,
        "temp_f_hz": {str(t): v for t, v in temps.items()},
        "temp_coeff_ppm_per_c": 1e6 * (temps[125.0] - temps[-40.0]) / (f_mid * 165.0),
        "supply_sens_pct_per_v": 100 * (f_hi - f_lo) / f_mid / (vdd_hi - vdd_lo),
    }


def save(result: dict, path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(result, indent=2))


def supply_vs_starve_pn(pdk: PDK, spec: VcoSpec, factors=(1.0, 2.0, 4.0)) -> list:
    """Trade-off table: supply sensitivity vs starving-PMOS width ratio at the baseline sizing."""
    vm, rows = vctrl_mid(pdk), []
    for k in factors:
        s = replace(spec, starve_pn=pdk.pn_ratio * k)
        fm = run_point(pdk, s, vm).f_hz
        lo = run_point(pdk, s, vm, vdd=0.9 * pdk.vdd).f_hz
        hi = run_point(pdk, s, vm, vdd=1.1 * pdk.vdd).f_hz
        rows.append({"starve_pn": s.starve_pn, "f_mid_hz": fm,
                     "supply_sens_pct_per_v": 100 * (hi - lo) / fm / (0.2 * pdk.vdd)})
    return rows
