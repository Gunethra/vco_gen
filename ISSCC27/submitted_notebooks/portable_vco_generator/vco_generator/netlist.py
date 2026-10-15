"""Current-starved ring VCO netlist generator (PDK-agnostic)."""
from dataclasses import dataclass
from .pdk import PDK


@dataclass(frozen=True)
class VcoSpec:
    n_stages: int = 5          # odd
    l_factor: float = 1.0      # inverter length, multiples of the PDK minimum
    l_starve_factor: float = 2.0   # starving-device length, multiples of minimum
    wn_um: float | None = None     # inverter NMOS width (default: PDK unit)
    ws_um: float | None = None     # starving NMOS footer width (default: wn)
    cload_f: float = 0.0       # extra capacitance per stage [F]
    starve: bool = True        # False -> plain ring oscillator
    starve_pn: float | None = None  # starving PMOS/NMOS width ratio (default: PDK inverter ratio)

    def __post_init__(self):
        if self.n_stages < 3 or self.n_stages % 2 == 0:
            raise ValueError("n_stages must be odd and >= 3")


def build_netlist(pdk: PDK, spec: VcoSpec, vctrl: float, corner: str = "tt",
                  temp: float = 27.0, tstop_ns: float | None = None,
                  vdd: float | None = None, wrdata: str = "out.dat",
                  mismatch: bool = False, seed: int | None = None) -> str:
    vdd = pdk.vdd if vdd is None else vdd
    wn = spec.wn_um or pdk.w_unit_um
    wp = wn * pdk.pn_ratio
    wsn = spec.ws_um or wn
    wsp = wsn * (spec.starve_pn or pdk.pn_ratio)
    li = pdk.lmin_um * spec.l_factor
    ls = pdk.lmin_um * spec.l_starve_factor
    f = pdk.fmt
    tstop = tstop_ns or pdk.tstop_ns
    N = spec.n_stages
    L = [f"* current-starved ring VCO  pdk={pdk.name} corner={corner} N={N} vctrl={vctrl:g}",
         pdk.header(corner, mismatch=mismatch), f".temp {temp:g}",
         *([f".options seed={seed}"] if seed is not None else []),   # seeds the models' agauss(): reproducible Monte Carlo
         f"Vdd vdd 0 {vdd:g}", f"Vctrl vctrl 0 {vctrl:g}"]
    if spec.starve:
        # bias branch: NMOS (gate=vctrl) sinks current from a diode-connected PMOS
        L += [f"XMbn vb vctrl 0 0 {pdk.nmos} L={f(ls)} W={f(wsn)}",
              f"XMbp vb vb vdd vdd {pdk.pmos} L={f(ls)} W={f(wsp)}"]
    for i in range(N):
        a, o = f"n{i}", f"n{(i + 1) % N}"
        if spec.starve:
            p, n = f"p{i}", f"s{i}"
            L += [f"XMhp{i} {p} vb vdd vdd {pdk.pmos} L={f(ls)} W={f(wsp)}",
                  f"XMfn{i} {n} vctrl 0 0 {pdk.nmos} L={f(ls)} W={f(wsn)}"]
        else:
            p, n = "vdd", "0"
        L += [f"XMp{i} {o} {a} {p} vdd {pdk.pmos} L={f(li)} W={f(wp)}",
              f"XMn{i} {o} {a} {n} 0 {pdk.nmos} L={f(li)} W={f(wn)}"]
        if spec.cload_f:
            L.append(f"Cl{i} {o} 0 {spec.cload_f:g}")
    L += [".ic v(n0)=0",
          ".control", f"tran 20p {tstop:g}n", f"wrdata {wrdata} v(n0) i(Vdd)", ".endc", ".end"]
    return "\n".join(L) + "\n"
