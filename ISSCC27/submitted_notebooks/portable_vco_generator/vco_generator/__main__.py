"""python -m vco_generator --pdk sky130 --f-target 400e6 [--stages 5] [--out results/]"""
import argparse
from .analysis import characterize, save, size_for_frequency
from .netlist import VcoSpec
from .pdk import get_pdk

ap = argparse.ArgumentParser(prog="vco_generator")
ap.add_argument("--pdk", required=True)
ap.add_argument("--f-target", type=float, default=400e6, help="center frequency at mid Vctrl [Hz]")
ap.add_argument("--stages", type=int, default=5)
ap.add_argument("--out", default="results")
ap.add_argument("--mc", type=int, default=0, help="also run N mismatch Monte Carlo samples at mid Vctrl")
a = ap.parse_args()
pdk = get_pdk(a.pdk)
spec = size_for_frequency(pdk, VcoSpec(n_stages=a.stages), a.f_target)
r = characterize(pdk, spec)
save(r, f"{a.out}/{pdk.name}.json")
print(f"{pdk.name}: ws={spec.ws_um} um  f_mid={r['f_mid_hz']/1e6:.1f} MHz  "
      f"Kvco={r['kvco_mid_hz_per_v']/1e6:.0f} MHz/V  tuning={r['tuning_ratio']:.1f}x  "
      f"corners={r['corner_spread_pct']:.0f}%  T={r['temp_coeff_ppm_per_c']:.0f} ppm/C  "
      f"supply={r['supply_sens_pct_per_v']:.1f} %/V")

if a.mc:
    from .analysis import vctrl_mid
    from .montecarlo import monte_carlo
    mc = monte_carlo(pdk, spec, vctrl_mid(pdk), n=a.mc)
    save(mc, f"{a.out}/mc_{pdk.name}.json")
    print(f"  mismatch MC (n={mc['n']}): sigma={mc['sigma_pct']:.2f} %  mean shift={mc['mean_shift_pct']:+.2f} %  within +-5 %: {100*mc['frac_within_5pct']:.0f} %")
