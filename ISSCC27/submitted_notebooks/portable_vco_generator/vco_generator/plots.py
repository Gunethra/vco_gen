"""Cross-PDK comparison plots from results/*.json (no simulation here)."""
import json
from pathlib import Path
from matplotlib.figure import Figure   # no pyplot: no backend side effects when imported from a notebook

COLORS = {"sky130": "#1f77b4", "gf180mcu": "#d95f02", "ihp_sg13g2": "#2ca02c"}


def compare(results_dir="results", out="results/comparison.png"):
    rs = [d for d in (json.loads(p.read_text()) for p in sorted(Path(results_dir).glob("*.json"))) if "curve" in d]   # skips mc_*.json
    fig = Figure(figsize=(13, 3.8)); ax = fig.subplots(1, 3)
    for r in rs:
        c, cv = COLORS.get(r["pdk"]), r["curve"]
        f = [x / 1e6 for x in cv["f_hz"]]
        ax[0].semilogy(cv["vctrl"], f, "o-", color=c, label=f'{r["pdk"]} ({r["vdd"]} V)')
        ax[1].plot([v / r["vdd"] for v in cv["vctrl"]], f, "o-", color=c, label=r["pdk"])
        ax[2].plot(f, [e * 1e15 for e in cv["e_cycle_j"]], "o-", color=c, label=r["pdk"])
    ax[0].set(xlabel="Vctrl [V]", ylabel="frequency [MHz]", title="Tuning curve")
    ax[1].set(xlabel="Vctrl / Vdd", ylabel="frequency [MHz]", title="Normalised control")
    ax[2].set(xlabel="frequency [MHz]", ylabel="energy / cycle [fJ]", title="Energy per cycle")
    for a in ax:
        a.grid(alpha=0.3); a.legend(frameon=False)
    fig.tight_layout(); fig.savefig(out, dpi=140)
    return out


if __name__ == "__main__":
    print(compare())
