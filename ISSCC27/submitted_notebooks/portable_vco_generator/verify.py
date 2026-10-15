"""Re-run the flow and compare against the stored golden values.

    python verify.py                 # schematic characterisation, both PDKs (~2 min)
    python verify.py --from-results  # compare existing results/*.json (seconds) instead of re-simulating
    python verify.py --mc            # also re-run the mismatch Monte Carlo (seeded, ~1 min per PDK)
    python verify.py --post          # also re-extract the committed GDS and re-run post-layout sims
    python verify.py --pdk sky130

Exit code 0 = every metric within tolerance.
"""
import argparse, json, math, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from vco_generator.analysis import characterize, size_for_frequency          # noqa: E402
from vco_generator.netlist import VcoSpec                                      # noqa: E402
from vco_generator.pdk import get_pdk                                          # noqa: E402

TOL = {"default": 0.02, "kvco_mid_hz_per_v": 0.05, "tuning_ratio": 0.10, "corner_spread_pct": 0.05,
       "temp_coeff_ppm_per_c": 0.05, "supply_sens_pct_per_v": 0.10, "e_cycle_mid_j": 0.03, "p_mid_w": 0.03}


def flat(d, prefix=""):
    for k, v in d.items():
        if isinstance(v, dict) and k != "curve":
            yield from flat(v, f"{prefix}{k}.")
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            yield f"{prefix}{k}", float(v)


def compare(name, new, gold, tol=TOL):
    bad, n = [], 0
    g = dict(flat(gold))
    for k, v in flat(new):
        if k not in g:
            continue
        n += 1
        t = tol.get(k.split(".")[0], tol["default"])
        if not math.isclose(v, g[k], rel_tol=t, abs_tol=1e-12):
            bad.append(f"  {name}: {k}: {v:.6g} vs golden {g[k]:.6g} (tol {t:.0%})")
    return n, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdk", choices=["sky130", "gf180mcu"], default=None)
    ap.add_argument("--from-results", action="store_true", help="compare the existing results/*.json (e.g. just written by the notebook) instead of re-simulating")
    ap.add_argument("--mc", action="store_true", help="also re-run the 100-sample mismatch Monte Carlo (~1 min per PDK)")
    ap.add_argument("--post", action="store_true", help="also re-run the post-layout sweep on layout/out/*_ring5.gds")
    a = ap.parse_args()
    failures, checked = [], 0
    for name in ([a.pdk] if a.pdk else ["sky130", "gf180mcu"]):
        pdk, gold = get_pdk(name), json.loads((ROOT / "golden" / f"{name}.json").read_text())
        if a.from_results:
            new = json.loads((ROOT / "results" / f"{name}.json").read_text())
            spec = VcoSpec(n_stages=new["n_stages"], ws_um=new["ws_um"], l_starve_factor=new["l_starve_factor"], starve_pn=new["starve_pn"])
        else:
            spec = size_for_frequency(pdk, VcoSpec(n_stages=gold["n_stages"]), 400e6)
            new = characterize(pdk, spec)
            new["starve_pn"] = spec.starve_pn or pdk.pn_ratio
        n, bad = compare(name, new, gold)
        checked += n; failures += bad
        print(f"[{'FAIL' if bad else ' ok '}] {name}: {n} schematic metrics compared")
        if a.mc:
            from vco_generator.analysis import vctrl_mid
            from vco_generator.montecarlo import monte_carlo
            mg = json.loads((ROOT / "golden" / f"mc_{name}.json").read_text())
            if a.from_results:
                m = json.loads((ROOT / "results" / f"mc_{name}.json").read_text())
            else:
                m = monte_carlo(pdk, spec, vctrl_mid(pdk), n=int(mg["n"]), seed0=int(mg["seed0"]))
            n, bad = compare(f"{name}/mc", {k: m[k] for k in ("f_mean_hz", "sigma_pct", "p_sigma_pct")}, mg,
                             {"default": 0.02, "sigma_pct": 0.20, "p_sigma_pct": 0.20})
            checked += n; failures += bad
            print(f"[{'FAIL' if bad else ' ok '}] {name}: {n} Monte Carlo statistics compared")
        if a.post:
            import numpy as np
            from vco_generator.postlayout import extract, run_point_post
            pg = json.loads((ROOT / "golden" / f"post_layout_{name}.json").read_text())
            spice = extract(str(ROOT / "layout" / "out" / f"{name}_ring5.gds"), "RING", pdk, f"/tmp/{name}_verify_pex.spice")
            f = [run_point_post(pdk, spice, "RING_flat", v).f_hz for v in pg["vctrl"]]
            n, bad = compare(f"{name}/post", {"f": dict(enumerate(f))}, {"f": dict(enumerate(pg["post_layout"]["f_hz"]))}, {"default": 0.03})
            checked += n; failures += bad
            print(f"[{'FAIL' if bad else ' ok '}] {name}: {n} post-layout frequencies compared")
    print(f"\n{checked} values checked, {len(failures)} outside tolerance")
    print("\n".join(failures))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
