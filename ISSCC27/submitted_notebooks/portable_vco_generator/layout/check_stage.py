import sys, os, glob, re, shutil
sys.path.insert(0, "layout")
from cells import get_pdk, stage
name = sys.argv[1]; pdk = get_pdk(name); root = os.environ["PDK_ROOT"]
kw, drc_kw = {}, {}
if name == "gf180mcu":
    rc = f"{root}/gf180mcuC/libs.tech/magic/gf180mcuC.magicrc"
    drc_kw = {"magic_drc_file": rc}
    kw = {"magic_drc_file": rc, "lvs_setup_tcl_file": f"{root}/gf180mcuC/libs.tech/netgen/gf180mcuC_setup.tcl"}
P = {"sky130": dict(wn=1.0, wp=2.0, length=0.15, ws_n=0.62, ws_p=1.24, length_s=1.2),
     "gf180mcu": dict(wn=1.0, wp=2.5, length=0.28, ws_n=0.50, ws_p=1.25, length_s=0.56)}[name]
c = stage(pdk, **P); c.name = "STAGE"
c.write_gds(f"layout/out/{name}_stage.gds")
d = pdk.drc_magic(c, "STAGE", output_file="stage_drc.rpt", **drc_kw)
print("RESULT DRC", name, d["result_str"].replace("\n", " | "))
shutil.rmtree("stage_lvs.rpt", ignore_errors=True)
pdk.lvs_netgen(c, "STAGE", output_file_path="stage_lvs.rpt", copy_intermediate_files=True, **kw)
rpt = open(glob.glob("stage_lvs.rpt/lvs/STAGE/STAGE_lvs.rpt")[0]).read()
print("RESULT LVS", name, re.findall(r"Final result: (.*)", rpt)[-1])
