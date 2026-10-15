"""Render a GDS to PNG by layer (gdstk + matplotlib). Usage: render.py in.gds out.png"""
import sys, gdstk
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Patch

lib = gdstk.read_gds(sys.argv[1]); top = lib.top_level()[0]
polys = top.get_polygons()
win = [float(v) for v in sys.argv[3].split(",")] if len(sys.argv) > 3 else None   # optional window x0,y0,x1,y1
if win: polys = [p for p in polys if p.points[:,0].max() > win[0] and p.points[:,0].min() < win[2] and p.points[:,1].max() > win[1] and p.points[:,1].min() < win[3]]
layers = sorted({(p.layer, p.datatype) for p in polys})
cmap = plt.get_cmap("tab20")
col = {l: cmap(i % 20) for i, l in enumerate(layers)}
fig, ax = plt.subplots(figsize=(9, 9))
for p in polys:
    ax.add_patch(Polygon(p.points, closed=True, fc=col[(p.layer, p.datatype)], ec="k", lw=0.2, alpha=0.45))
ax.autoscale(); ax.set_aspect("equal")
if win: ax.set_xlim(win[0], win[2]); ax.set_ylim(win[1], win[3])
ax.legend(handles=[Patch(fc=col[l], label=f"{l[0]}/{l[1]}") for l in layers], fontsize=6, ncol=2, loc="upper left", bbox_to_anchor=(1, 1))
fig.savefig(sys.argv[2], dpi=110, bbox_inches="tight")
print("layers:", layers)
