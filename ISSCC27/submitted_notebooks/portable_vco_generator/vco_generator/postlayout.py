"""Post-layout flow: Magic parasitic-C extraction of a GDS and ngspice runs on the extracted netlist."""
import os, re, subprocess, tempfile
from pathlib import Path
import numpy as np
from .pdk import PDK, default_pdk_root
from .simulate import Point, _measure, _ngspice

_RC = {"sky130": "sky130A/libs.tech/magic/sky130A.magicrc",
       "gf180mcu": "gf180mcuC/libs.tech/magic/gf180mcuC.magicrc"}


def extract(gds: str, top: str, pdk: PDK, out_spice: str) -> str:
    """GDS -> flat SPICE (subckt `<top>_flat`) with parasitic capacitances, no wire resistance."""
    root = default_pdk_root()
    scale_cmd = "ext2spice scale off\n" if pdk.name == "gf180mcu" else ""   # gf180 models want SI-suffixed w/l/ad/as
    script = f"""drc off
gds read {Path(gds).resolve()}
load {top}
flatten {top}_flat
load {top}_flat
select top cell
extract all
ext2spice cthresh 0
ext2spice format ngspice
{scale_cmd}ext2spice -o {Path(out_spice).resolve()}
exit
"""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "x.tcl").write_text(script)
        subprocess.run(f"magic -rcfile {root / _RC[pdk.name]} -noconsole -dnull < x.tcl", shell=True, cwd=d,
                       check=True, capture_output=True, env=dict(os.environ, PDK_ROOT=str(root)), executable="/bin/bash")
    return str(out_spice)


def top_ports(spice: str, top: str):
    for line in Path(spice).read_text().splitlines():
        if line.lower().startswith(".subckt") and line.split()[1] == top:
            return line.split()[2:]
    raise ValueError(f"no .subckt {top}")


def run_point_post(pdk: PDK, spice: str, top: str, vctrl: float, corner="tt", temp=27.0,
                   vdd=None, tstop_ns=None, probe="N0", retries=3, no_caps=False) -> Point:
    vdd = pdk.vdd if vdd is None else vdd
    tstop = tstop_ns or pdk.tstop_ns
    ports = top_ports(spice, top)
    nets = {"VDD": "vdd", "VSS": "0", "VCTRL": "vctrl", probe: "n0"}
    body = Path(spice).read_text()
    if no_caps:        # validation: same devices, parasitic capacitors removed
        body = "\n".join(l for l in body.splitlines() if not l.startswith("C"))
    for _ in range(retries + 1):
        with tempfile.TemporaryDirectory() as d:
            dat = Path(d) / "out.dat"
            (Path(d) / "pex.spice").write_text(body)
            (Path(d) / "run.sp").write_text(f"""* post-layout {top}
{pdk.header(corner)}
.temp {temp:g}
.include pex.spice
Vdd vdd 0 {vdd:g}
Vctrl vctrl 0 {vctrl:g}
Xdut {' '.join(nets[p] for p in ports)} {top}
.ic v(n0)=0
.control
tran 20p {tstop:g}n
wrdata {dat} v(n0) i(Vdd)
.endc
.end
""")
            r = subprocess.run([_ngspice(), "-b", "run.sp"], cwd=d, capture_output=True, text=True,
                               env=dict(os.environ, PDK_ROOT=str(default_pdk_root())), timeout=1800)
            if not dat.exists():
                raise RuntimeError("ngspice failed:\n" + (r.stdout + r.stderr)[-1500:])
            a = np.loadtxt(dat)
        f, p, n = _measure(a[:, 0], a[:, 1], a[:, 3], vdd)
        if n >= 6 or retries == 0:
            break
        tstop *= 4
    return Point(pdk.name, corner, temp, vdd, vctrl, f, p, p / f if f == f and f > 0 else float("nan"), n)
