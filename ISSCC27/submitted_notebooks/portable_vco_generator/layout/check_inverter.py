import sys, os, glob, re
sys.path.insert(0, "layout")
from cells import get_pdk, inverter
name = sys.argv[1]
pdk = get_pdk(name)
root = os.environ["PDK_ROOT"]
kw, drc_kw = {}, {}
if name == "gf180mcu":     # glayout expects the gf180mcuD variant; we install gf180mcuC
    rc = f"{root}/gf180mcuC/libs.tech/magic/gf180mcuC.magicrc"
    drc_kw = {"magic_drc_file": rc}
    kw = {"magic_drc_file": rc, "lvs_setup_tcl_file": f"{root}/gf180mcuC/libs.tech/netgen/gf180mcuC_setup.tcl"}
L = {"sky130": 0.15, "gf180mcu": 0.28}[name]
c = inverter(pdk, wn=1.0, wp=2.0 if name == "sky130" else 2.5, length=L, src="W", drn="E", gate="W")
c.name = "INVERTER"
c.write_gds(f"layout/out/{name}_inverter.gds")
print("RESULT DRC", name, pdk.drc_magic(c, "INVERTER", **drc_kw)["result_str"].replace("\n", " | "))
pdk.lvs_netgen(c, "INVERTER", output_file_path="inv_lvs.rpt", copy_intermediate_files=True, **kw)
rpt = open(glob.glob("inv_lvs.rpt/lvs/INVERTER/INVERTER_lvs.rpt")[0]).read()
print("RESULT LVS", name, re.findall(r"Final result: (.*)", rpt)[-1])
