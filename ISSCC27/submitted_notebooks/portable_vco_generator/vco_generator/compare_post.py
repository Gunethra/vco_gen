"""python -m vco_generator.compare_post --pdk sky130 : schematic vs post-layout (parasitic C) sweep."""
import argparse, json, os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
from .netlist import VcoSpec
from .pdk import get_pdk
from .postlayout import extract, run_point_post
from .simulate import sweep

ap = argparse.ArgumentParser()
ap.add_argument("--pdk", required=True)
ap.add_argument("--gds", default=None)
ap.add_argument("--npts", type=int, default=8)
a = ap.parse_args()
pdk = get_pdk(a.pdk)
r = json.load(open(f"results/{pdk.name}.json"))
spec = VcoSpec(ws_um=r["ws_um"], l_starve_factor=r["l_starve_factor"], starve_pn=r["starve_pn"])
gds = a.gds or f"layout/out/{pdk.name}_ring5.gds"
Path("results/extra").mkdir(parents=True, exist_ok=True)
spice = extract(gds, "RING", pdk, f"results/extra/{pdk.name}_ring5_pex.spice")
vs = np.linspace(pdk.vctrl_lo, pdk.vdd, a.npts)
sch = sweep(pdk, spec, vs)
with ThreadPoolExecutor(min(8, os.cpu_count() or 1)) as ex:
    post = list(ex.map(lambda v: run_point_post(pdk, spice, "RING_flat", v), vs))
out = {"pdk": pdk.name, "note": "post-layout = Magic parasitic C only (no wire R); dummy devices included",
       "vctrl": vs.tolist(),
       "schematic": {"f_hz": [p.f_hz for p in sch], "p_w": [p.p_w for p in sch]},
       "post_layout": {"f_hz": [p.f_hz for p in post], "p_w": [p.p_w for p in post]}}
json.dump(out, open(f"results/extra/post_layout_{pdk.name}.json", "w"), indent=2)
for v, s, p in zip(vs, sch, post):
    print(f"vctrl={v:.2f} f_sch={s.f_hz/1e6:8.1f} f_post={p.f_hz/1e6:8.1f} MHz ({100*(p.f_hz/s.f_hz-1):+5.1f}%)  P_sch={s.p_w*1e6:7.1f} P_post={p.p_w*1e6:7.1f} uW")
