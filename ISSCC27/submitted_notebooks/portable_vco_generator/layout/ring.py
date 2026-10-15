"""Ring VCO assembly: bias branch + N current-starved stages, rails on met4, verticals on met5."""
from glayout.backend import Component, cell
from glayout.spice.netlist import Netlist
from cells import TOPMETAL_W, bias, bias_pin_xy, get_pdk, rect, stage, stage_pin_xy, via_at, _nl

W4, W5, WR = 0.4, 0.3, 0.8        # met4 link / met5 vertical / supply-rail widths [um]


def _v(top, pdk, layer, x, y0, y1, w):   # vertical wire
    rect(top, pdk, layer, x - w / 2, x + w / 2, min(y0, y1) - w / 2, max(y0, y1) + w / 2)


def _h(top, pdk, layer, y, x0, x1, w):   # horizontal wire
    rect(top, pdk, layer, min(x0, x1) - w / 2, max(x0, x1) + w / 2, y - w / 2, y + w / 2)


@cell
def ring(pdk, stage_kw: dict, bias_kw: dict, n: int = 5, gap: float = 9.0) -> Component:
    global W5
    W5 = TOPMETAL_W[pdk.name.lower()]
    top = Component()
    st, bs = stage(pdk, **stage_kw), bias(pdk, **bias_kw)
    sp, bp = stage_pin_xy(st, pdk), bias_pin_xy(bs, pdk)
    sw = st.xmax - st.xmin
    # placement: bias first, then n stages (all bottoms aligned at y=0 of their own frames)
    bx = -bs.xmin
    ox = [bx + (bs.xmax - bs.xmin) / 2 + gap + sw / 2 + k * (sw + gap) for k in range(n)]
    bref = top << bs; bref.movex(bx)
    srefs = []
    for x in ox:
        r = top << st; r.movex(x); srefs.append(r)
    ymin, ymax = min(st.ymin, bs.ymin), max(st.ymax, bs.ymax)
    y_vss, y_vc = ymin - 3.0, ymin - 6.0
    y_vdd, y_vb, y_wrap = ymax + 3.0, ymax + 6.0, ymax + 9.0
    xs0 = bx + min(v[0] for v in bp.values()) - 1.0
    xs1 = ox[-1] + sp["VOUT"][0] + 2.0
    for y, w in ((y_vss, WR), (y_vdd, WR), (y_vc, W4), (y_vb, W4)):
        _h(top, pdk, "met4", y, xs0, xs1, w)
    # instances: (x offset, pin map)
    inst = [("B", bx, bp)] + [(f"S{k}", x, sp) for k, x in enumerate(ox)]
    for name, x0, pins in inst:
        # supply drops on met4 (ring bar -> rail)
        for net, y_rail in (("VSS", y_vss), ("VDD", y_vdd)):
            px, py = x0 + pins[net][0], pins[net][1]
            via_at(top, pdk, px, py, "met2", "met4")
            _v(top, pdk, "met4", px, py, y_rail, W4)
        # control / bias drops on met5 (cross the supply rails) ending in a via to the met4 rail
        for net, y_rail in (("VCTRL", y_vc), ("VB", y_vb)):
            px, py = x0 + pins[net][0], pins[net][1]
            via_at(top, pdk, px, py, "met2", "met5")
            _v(top, pdk, "met5", px, py, y_rail, W5)
            via_at(top, pdk, px, y_rail, "met4", "met5")
    # signal links VOUT_k -> VIN_{k+1}
    vin = [(x + sp["VIN"][0], sp["VIN"][1]) for x in ox]
    vout = [(x + sp["VOUT"][0], sp["VOUT"][1]) for x in ox]
    for k in range(n):            # met5 only where a met5 wire attaches (the wrap-around); met4 elsewhere
        via_at(top, pdk, *vin[k], "met2", "met5" if k == 0 else "met4")
        via_at(top, pdk, *vout[k], "met2", "met5" if k == n - 1 else "met4")
    for k in range(n - 1):
        (xo, yo), (xi, yi) = vout[k], vin[k + 1]
        _v(top, pdk, "met4", xo, yo, yi, W4)
        _h(top, pdk, "met4", yi, xo, xi, W4)
    (xo, yo), (xi, yi) = vout[-1], vin[0]                       # wrap-around on met5 + met4 above the rails
    _v(top, pdk, "met5", xo, yo, y_wrap, W5); via_at(top, pdk, xo, y_wrap, "met4", "met5")
    _h(top, pdk, "met4", y_wrap, xo, xi, W4)
    via_at(top, pdk, xi, y_wrap, "met4", "met5"); _v(top, pdk, "met5", xi, y_wrap, yi, W5)
    # pins
    for text, y in (("VSS", y_vss), ("VDD", y_vdd), ("VCTRL", y_vc)):
        h = 0.135
        rect(top, pdk, "met4_pin", xs0, xs0 + 2 * h, y - h, y + h)
        top.add_label(text=text, position=(xs0 + h, y), layer=pdk.get_glayer("met4_label"))
    # observation pin on the first stage's input net (a ring has no other external pin to probe)
    h = 0.135; x, y = vin[0]
    rect(top, pdk, "met5_pin", x - h, x + h, y - h, y + h)
    top.add_label(text="N0", position=(x, y), layer=pdk.get_glayer("met5_label"))
    # reference netlist
    nl = Netlist(circuit_name="RING", nodes=["VDD", "VSS", "VCTRL", "N0"])
    nl.connect_netlist(_nl(bs), [("VCTRL", "VCTRL"), ("VB", "VB"), ("VDD", "VDD"), ("VSS", "VSS")])
    for k in range(n):
        nl.connect_netlist(_nl(st), [("VIN", "N0" if k == 0 else f"n{k}"), ("VOUT", "N0" if (k + 1) % n == 0 else f"n{(k + 1) % n}"), ("VDD", "VDD"),
                                     ("VSS", "VSS"), ("VCTRL", "VCTRL"), ("VB", "VB")])
    top.info["netlist"] = nl
    return top
