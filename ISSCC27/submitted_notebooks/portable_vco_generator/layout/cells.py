"""gLayout cells for the VCO: inverter first, then the full current-starved stage."""
from glayout.backend import Component, cell
from glayout.pdk.mappedpdk import MappedPDK
from glayout.primitives.fet import nmos, pmos
from glayout.primitives.via_gen import via_stack
import numpy as np
from glayout.routing.c_route import c_route
from glayout.routing.straight_route import straight_route
from glayout.spice.netlist import Netlist
from glayout.backend import rectangle
from glayout.util.comp_utils import align_comp_to_port, evaluate_bbox
from glayout.util.port_utils import rename_ports_by_orientation
from glayout.util.snap_to_grid import component_snap_to_grid


def get_pdk(name: str) -> MappedPDK:
    if name == "sky130":
        from glayout.pdk.sky130_mapped.sky130_mapped import sky130_mapped_pdk as p
    elif name == "gf180mcu":
        from glayout.pdk.gf180_mapped.gf180_mapped import gf180_mapped_pdk as p
    else:
        raise ValueError(name)
    return p


def _nl(c) -> Netlist:
    """Netlist object of a gLayout cell (primitives store it under info['netlist'])."""
    n = c.info["netlist"]
    return n if isinstance(n, Netlist) else n


def ring_bars(comp, pdk, glayer="met2"):
    """Horizontal tap-ring bars (wide, thin rectangles) on `glayer`, sorted bottom to top: (x0, x1, y0, y1)."""
    out = []
    for q in comp.get_polygons(by_spec=tuple(pdk.get_glayer(glayer))):
        q = np.asarray(q); (x0, y0), (x1, y1) = q.min(0), q.max(0)
        if x1 - x0 > 3 and y1 - y0 < 1.2:
            out.append((float(x0), float(x1), float(y0), float(y1)))
    return sorted(out, key=lambda b: b[2])


def rect(comp, pdk, glayer, x0, x1, y0, y1):
    comp.add_polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], layer=pdk.get_glayer(glayer))


def via_at(comp, pdk, cx, cy, lo, hi):
    """Via stack between glayers `lo` and `hi`, centred on (cx, cy)."""
    ref = comp << via_stack(pdk, lo, hi)
    ref.movex(cx - ref.center[0]).movey(cy - ref.center[1])
    return ref


def label_port(pdk: MappedPDK, comp: Component, text: str, port) -> None:
    """Stamp a named pin label on the metal layer of `port` (needed by netgen for pin matching)."""
    name = next(g for g in ("met1", "met2", "met3") if tuple(pdk.get_glayer(g)) == tuple(port.layer))
    # label goes straight into `comp` (a sub-cell label would become a hierarchical name in Magic)
    import math
    h = 0.135
    # port centres sit on the metal edge: shift the pin shape inward so it lies fully on the metal
    # (a pin polygon overhanging the edge is read as drawn metal and trips min-width rules)
    o = math.radians(port.orientation)
    cx = float(port.center[0]) - h * round(math.cos(o))
    cy = float(port.center[1]) - h * round(math.sin(o))
    comp.add_polygon([(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)],
                     layer=pdk.get_glayer(f"{name}_pin"))
    comp.add_label(text=text, position=(cx, cy), layer=pdk.get_glayer(f"{name}_label"))


@cell
def inverter(pdk: MappedPDK, wn: float, wp: float, length: float,
             src: str = "W", drn: str = "E", gate: str = "E") -> Component:
    """CMOS inverter: NMOS below, PMOS above (as in glayout's transmission_gate)."""
    top = Component()
    nfet = nmos(pdk, width=wn, length=length, fingers=1, with_dummy=True,
                with_dnwell=False, with_substrate_tap=False)
    pfet = pmos(pdk, width=wp, length=length, fingers=1, with_dummy=True,
                with_substrate_tap=False)
    n = top << nfet
    p = top << pfet
    p = rename_ports_by_orientation(p.mirror_y())
    p.movey(n.ymax + evaluate_bbox(p)[1] / 2 + pdk.util_max_metal_seperation())
    top << c_route(pdk, n.ports[f"multiplier_0_gate_{gate}"], p.ports[f"multiplier_0_gate_{gate}"])
    top << c_route(pdk, n.ports[f"multiplier_0_drain_{drn}"], p.ports[f"multiplier_0_drain_{drn}"], viaoffset=False)
    # tie each source to its own bulk tap (VSS / VDD), as glayout's FVF does
    for ref in (n, p):
        top << straight_route(pdk, ref.ports[f"multiplier_0_source_{src}"], ref.ports[f"tie_{src}_top_met_{src}"],
                              glayer1="met1", width=max(0.2, pdk.get_grule("met1")["min_width"]), fullbottom=True)
    top.add_ports(n.get_ports_list(), prefix="N_")
    top.add_ports(p.get_ports_list(), prefix="P_")
    comp = component_snap_to_grid(rename_ports_by_orientation(top))
    comp.unlock()
    for text, port in ("VIN", comp.ports[f"N_multiplier_0_gate_{gate}"]), ("VOUT", comp.ports[f"N_multiplier_0_drain_{drn}"]), ("VSS", comp.ports[f"N_tie_{src}_top_met_{src}"]), ("VDD", comp.ports[f"P_tie_{src}_top_met_{src}"]):
        label_port(pdk, comp, text, port)
    nl = Netlist(circuit_name="INVERTER", nodes=["VIN", "VOUT", "VDD", "VSS"])
    nl.connect_netlist(_nl(nfet), [("D", "VOUT"), ("G", "VIN"), ("S", "VSS"), ("B", "VSS"), ("DUM", "VSS")])
    nl.connect_netlist(_nl(pfet), [("D", "VOUT"), ("G", "VIN"), ("S", "VDD"), ("B", "VDD"), ("DUM", "VDD")])
    comp.info["netlist"] = nl
    return comp


def _tie(pdk, top, ref, side="W"):
    """Tie a device's source to its own bulk tap (as in the inverter)."""
    top << straight_route(pdk, ref.ports[f"multiplier_0_source_{side}"], ref.ports[f"tie_{side}_top_met_{side}"],
                          glayer1="met1", width=max(0.2, pdk.get_grule("met1")["min_width"]), fullbottom=True)


@cell
def stage(pdk: MappedPDK, wn: float, wp: float, length: float,
          ws_n: float, ws_p: float, length_s: float,
          lane_gate: float = 1.5, lane_n: float = 2.0, lane_p: float = 2.0, lane_out: float = 1.5) -> Component:
    """Current-starved inverter stage, bottom to top: footer NMOS (gate VCTRL), inverter NMOS,
    inverter PMOS, header PMOS (gate VB).  Pins: VIN VOUT VDD VSS VCTRL VB."""
    top = Component()
    mk_n = lambda w, l: nmos(pdk, width=w, length=l, fingers=1, with_dummy=True, with_dnwell=False, with_substrate_tap=False)
    mk_p = lambda w, l: pmos(pdk, width=w, length=l, fingers=1, with_dummy=True, with_substrate_tap=False)
    fets = {"F": mk_n(ws_n, length_s), "I": mk_n(wn, length), "J": mk_p(wp, length), "H": mk_p(ws_p, length_s)}
    refs, prev = {}, None
    for k in ("F", "I", "J", "H"):
        r = top << fets[k]
        if k in ("J", "H"):
            r = rename_ports_by_orientation(r.mirror_y())
        if prev is not None:
            gap = pdk.util_max_metal_seperation()
            if k == "H":           # two PMOS in separate n-wells: respect well-to-well spacing
                gap = max(gap, pdk.get_grule("nwell", "nwell")["min_separation"] + 0.1)
            r.movey(prev.ymax - r.ymin + gap)
        refs[k], prev = r, r
    F, I, J, H = (refs[k] for k in "FIJH")
    P = lambda r, n: r.ports[f"multiplier_0_{n}"]
    cw = max(0.3, pdk.get_grule("met2")["min_width"])      # connection-lane width (gf180 M2.1 needs >= 0.28)
    top << c_route(pdk, P(I, "gate_W"), P(J, "gate_W"), extension=lane_gate, cwidth=cw)                        # VIN
    top << c_route(pdk, P(I, "drain_E"), P(J, "drain_E"), extension=lane_out, viaoffset=False, cwidth=cw)                          # VOUT
    top << c_route(pdk, P(F, "drain_W"), P(I, "source_W"), extension=lane_n, cwidth=cw)                        # node N
    top << c_route(pdk, P(J, "source_W"), P(H, "drain_W"), extension=lane_p, cwidth=cw)                        # node P
    _tie(pdk, top, F); _tie(pdk, top, H)
    for r in (F, H):   # west stubs so VCTRL / VB can take a via away from the device
        q = P(r, "gate_W")
        rect(top, pdk, "met2", pin_x(pdk) - 0.4, q.center[0], q.center[1] - q.width / 2, q.center[1] + q.width / 2)
    # tie rings of devices sharing a supply are bridged: VSS (F,I) and VDD (J,H)
    bars = ring_bars(top, pdk)
    bx = 2.0
    for lo_top, up_bot in ((bars[1], bars[2]), (bars[5], bars[6])):
        rect(top, pdk, "met2", bx - 0.25, bx + 0.25, lo_top[2] + 0.05, up_bot[3] - 0.05)
    for k, r in refs.items():
        top.add_ports(r.get_ports_list(), prefix=f"{k}_")
    comp = component_snap_to_grid(rename_ports_by_orientation(top))
    comp.unlock()
    pins = [("VIN", comp.ports["I_multiplier_0_gate_W"]), ("VOUT", comp.ports["I_multiplier_0_drain_E"]),
            ("VCTRL", comp.ports["F_multiplier_0_gate_W"]), ("VB", comp.ports["H_multiplier_0_gate_W"]),
            ("VSS", comp.ports["F_tie_W_top_met_W"]), ("VSS", comp.ports["I_tie_W_top_met_W"]),
            ("VDD", comp.ports["H_tie_W_top_met_W"]), ("VDD", comp.ports["J_tie_W_top_met_W"])]
    for text, port in pins:
        label_port(pdk, comp, text, port)
    nl = Netlist(circuit_name="STAGE", nodes=["VIN", "VOUT", "VDD", "VSS", "VCTRL", "VB"])
    nl.connect_netlist(_nl(fets["F"]), [("D", "NN"), ("G", "VCTRL"), ("S", "VSS"), ("B", "VSS"), ("DUM", "VSS")])
    nl.connect_netlist(_nl(fets["I"]), [("D", "VOUT"), ("G", "VIN"), ("S", "NN"), ("B", "VSS"), ("DUM", "VSS")])
    nl.connect_netlist(_nl(fets["J"]), [("D", "VOUT"), ("G", "VIN"), ("S", "NP"), ("B", "VDD"), ("DUM", "VDD")])
    nl.connect_netlist(_nl(fets["H"]), [("D", "NP"), ("G", "VB"), ("S", "VDD"), ("B", "VDD"), ("DUM", "VDD")])
    comp.info["netlist"] = nl
    return comp


# x of the VCTRL / VB via landing in a stage / bias frame, and the top-metal (met5) wire width, per PDK
_PIN_X = {"sky130": -1.6, "gf180": -2.2}
TOPMETAL_W = {"sky130": 0.3, "gf180": 0.5}   # gf180's thick top metal needs >= 0.44 (glayout's grule says 0.28)


def pin_x(pdk):
    return _PIN_X[pdk.name.lower()]


def stage_pin_xy(comp, pdk):
    """Via-landing points (x, y) of the stage's six external nets, in the component's frame."""
    bars = ring_bars(comp, pdk)
    pt = lambda n, dx: (float(comp.ports[n].center[0]) + dx, float(comp.ports[n].center[1]))
    return {"VIN": pt("I_multiplier_0_gate_W", -0.5), "VOUT": pt("I_multiplier_0_drain_E", 0.5),
            "VCTRL": (pin_x(pdk), float(comp.ports["F_multiplier_0_gate_W"].center[1])),
            "VB": (pin_x(pdk), float(comp.ports["H_multiplier_0_gate_W"].center[1])),
            "VSS": (3.0, 0.5 * (bars[0][2] + bars[0][3])), "VDD": (3.0, 0.5 * (bars[-1][2] + bars[-1][3]))}


@cell
def bias(pdk: MappedPDK, ws_n: float, ws_p: float, length_s: float, lane: float = 1.5) -> Component:
    """Bias branch: NMOS (gate VCTRL) sinks the current of a diode-connected PMOS (gate = drain = VB)."""
    top = Component()
    nfet = nmos(pdk, width=ws_n, length=length_s, fingers=1, with_dummy=True, with_dnwell=False, with_substrate_tap=False)
    pfet = pmos(pdk, width=ws_p, length=length_s, fingers=1, with_dummy=True, with_substrate_tap=False)
    n = top << nfet
    p = rename_ports_by_orientation((top << pfet).mirror_y())
    p.movey(n.ymax - p.ymin + max(pdk.util_max_metal_seperation(), pdk.get_grule("nwell", "nwell")["min_separation"] + 0.1))
    cw = max(0.3, pdk.get_grule("met2")["min_width"])
    P = lambda r, nm: r.ports[f"multiplier_0_{nm}"]
    top << c_route(pdk, P(n, "drain_E"), P(p, "drain_E"), extension=lane, viaoffset=False, cwidth=cw)   # VB
    w_d = min(P(p, "gate_W").width, P(p, "drain_W").width)      # a wider stub would crowd the neighbouring source bar
    top << c_route(pdk, P(p, "gate_W"), P(p, "drain_W"), extension=lane, cwidth=cw, width1=w_d, width2=w_d)   # diode
    _tie(pdk, top, n); _tie(pdk, top, p)
    q = P(n, "gate_W")
    rect(top, pdk, "met2", pin_x(pdk) - 0.4, q.center[0], q.center[1] - q.width / 2, q.center[1] + q.width / 2)
    top.add_ports(n.get_ports_list(), prefix="N_")
    top.add_ports(p.get_ports_list(), prefix="P_")
    comp = component_snap_to_grid(rename_ports_by_orientation(top))
    comp.unlock()
    nl = Netlist(circuit_name="BIAS", nodes=["VCTRL", "VB", "VDD", "VSS"])
    nl.connect_netlist(_nl(nfet), [("D", "VB"), ("G", "VCTRL"), ("S", "VSS"), ("B", "VSS"), ("DUM", "VSS")])
    nl.connect_netlist(_nl(pfet), [("D", "VB"), ("G", "VB"), ("S", "VDD"), ("B", "VDD"), ("DUM", "VDD")])
    comp.info["netlist"] = nl
    return comp


def bias_pin_xy(comp, pdk):
    bars = ring_bars(comp, pdk)
    g = comp.ports["N_multiplier_0_gate_W"]; d = comp.ports["P_multiplier_0_drain_E"]
    return {"VCTRL": (pin_x(pdk), float(g.center[1])), "VB": (float(d.center[0]) + 0.5, float(d.center[1])),
            "VSS": (3.0, 0.5 * (bars[0][2] + bars[0][3])), "VDD": (3.0, 0.5 * (bars[-1][2] + bars[-1][3]))}
