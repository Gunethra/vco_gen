import sys, os, glob, re, shutil
sys.path.insert(0, "layout")
from cells import get_pdk
from ring import ring
name = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
pdk = get_pdk(name); root = os.environ["PDK_ROOT"]
kw, drc_kw = {}, {}
if name == "gf180mcu":
    rc = f"{root}/gf180mcuC/libs.tech/magic/gf180mcuC.magicrc"
    drc_kw = {"magic_drc_file": rc}
    kw = {"magic_drc_file": rc, "lvs_setup_tcl_file": f"{root}/gf180mcuC/libs.tech/netgen/gf180mcuC_setup.tcl"}
import json
r = json.load(open(f"{os.environ['VCO_ROOT']}/results/{name}.json"))          # sizes come from the simulated, sized design
ws, pn, lx = r["ws_um"], r["starve_pn"], r["l_starve_factor"]
lmin = {"sky130": 0.15, "gf180mcu": 0.28}[name]
S = dict(wn=1.0, wp={"sky130": 2.0, "gf180mcu": 2.5}[name], length=lmin, ws_n=ws, ws_p=round(ws * pn, 3), length_s=lmin * lx)
B = dict(ws_n=S["ws_n"], ws_p=S["ws_p"], length_s=S["length_s"])
c = ring(pdk, S, B, n=n); c.name = "RING"
OUT = f"{os.environ['VCO_ROOT']}/layout/out"
os.makedirs(OUT, exist_ok=True)
c.write_gds(f"{OUT}/{name}_ring{n}.gds")
print("RESULT bbox", [round(float(v), 1) for v in (c.xmin, c.ymin, c.xmax, c.ymax)], flush=True)
d = pdk.drc_magic(c, "RING", output_file="ring_drc.rpt", **drc_kw)
print("RESULT DRC", name, d["result_str"].replace("\n", " | "), flush=True)
shutil.rmtree("ring_lvs.rpt", ignore_errors=True)
pdk.lvs_netgen(c, "RING", output_file_path="ring_lvs.rpt", copy_intermediate_files=True, **kw)
rpt = open(glob.glob("ring_lvs.rpt/lvs/RING/RING_lvs.rpt")[0]).read()
lvs = re.findall(r"Final result: (.*)", rpt)[-1]
print("RESULT LVS", name, lvs)
import json
drc_rpt = glob.glob("ring_drc.rpt/drc/RING/RING.rpt")
viol = [l.strip() for l in open(drc_rpt[0]) if "<" in l] if drc_rpt else []
json.dump({"pdk": name, "stages": n, "bbox_um": [round(float(v), 2) for v in (c.xmin, c.ymin, c.xmax, c.ymax)],
           "drc_violations": viol, "drc_clean": not viol, "lvs": lvs, "lvs_clean": lvs.startswith("Circuits match uniquely")},
          open(f"{os.environ['VCO_ROOT']}/layout/out/{name}_ring{n}_checks.json", "w"), indent=2)
