"""Per-PDK configuration: the only place that knows PDK-specific names and conventions."""
from dataclasses import dataclass, field
import os
from pathlib import Path


def default_pdk_root() -> Path:
    env = os.environ.get("PDK_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[1] / ".env" / "share" / "pdk"


@dataclass(frozen=True)
class PDK:
    name: str
    vdd: float                 # nominal supply for the chosen device flavour [V]
    lmin_um: float             # minimum drawn length [um]
    wmin_um: float             # minimum drawn width [um]
    nmos: str
    pmos: str
    corners: dict              # generic corner name (tt/ss/ff/sf/fs) -> library section
    includes: tuple            # lines with {root} and {corner} placeholders
    len_fmt: str               # how to print a length/width given in um
    vctrl_lo: float            # lowest useful control voltage [V]
    pn_ratio: float            # PMOS/NMOS width ratio for a balanced inverter
    w_unit_um: float           # default inverter NMOS width [um]
    tstop_ns: float            # default transient length for a 5-stage ring [ns]
    mismatch: str = "suffix"   # how local mismatch is switched on: 'suffix' (corner section + _mm) or 'param'

    def fmt(self, x_um: float) -> str:
        return self.len_fmt.format(x=x_um)

    def header(self, corner: str = "tt", root: Path | None = None, mismatch: bool = False) -> str:
        root = root or default_pdk_root()
        sec = self.corners[corner] + ("_mm" if mismatch and self.mismatch == "suffix" else "")
        txt = "\n".join(l.format(root=root, corner=sec) for l in self.includes)
        return txt + ("\n.param sw_stat_mismatch=1" if mismatch and self.mismatch == "param" else "")


PDKS = {
    "sky130": PDK(
        name="sky130", vdd=1.8, lmin_um=0.15, wmin_um=0.42,
        nmos="sky130_fd_pr__nfet_01v8", pmos="sky130_fd_pr__pfet_01v8",
        corners={"tt": "tt", "ss": "ss", "ff": "ff", "sf": "sf", "fs": "fs"},
        includes=(".lib {root}/sky130A/libs.tech/ngspice/sky130.lib.spice {corner}",),
        len_fmt="{x:.4g}",            # sky130 subckts take plain micrometres
        vctrl_lo=0.65, pn_ratio=2.0, w_unit_um=1.0, tstop_ns=300.0,
    ),
    "gf180mcu": PDK(
        name="gf180mcu", vdd=3.3, lmin_um=0.28, wmin_um=0.46,   # 0.46: smallest width gLayout can contact (device min is 0.22)
        nmos="nfet_03v3", pmos="pfet_03v3",
        corners={"tt": "typical", "ss": "ss", "ff": "ff", "sf": "sf", "fs": "fs"},
        includes=(".include {root}/gf180mcuC/libs.tech/ngspice/design.ngspice",
                  ".lib {root}/gf180mcuC/libs.tech/ngspice/sm141064.ngspice {corner}"),
        len_fmt="{x:.4g}u",           # gf180 subckts take SI-suffixed values
        vctrl_lo=0.85, pn_ratio=2.5, w_unit_um=1.0, tstop_ns=300.0, mismatch="param",
    ),
}


def get_pdk(name: str) -> PDK:
    try:
        return PDKS[name]
    except KeyError:
        raise ValueError(f"unknown PDK {name!r}; choose from {sorted(PDKS)}") from None
