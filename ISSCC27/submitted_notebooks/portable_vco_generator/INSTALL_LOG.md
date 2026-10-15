# Local install log (dev only, not part of the submission)

Everything lives inside this folder and is gitignored. Nothing is installed system-wide.

## Locations
| Path | What | Size (approx) |
|---|---|---|
| `.tools/bin/micromamba` | micromamba 2.9.0 binary (from micro.mamba.pm) | 18 MB |
| `.tools/root/` | micromamba package cache (`MAMBA_ROOT_PREFIX`) | ~1 GB+ |
| `.tools/install.log` | install output | small |
| `.env/` | conda environment | several GB |

## Environment contents (channels: litex-hub, conda-forge)
python=3.11, open_pdks.sky130a, open_pdks.gf180mcuc, magic, netgen, ngspice, klayout, yosys,
numpy, scipy, matplotlib, pandas, pyyaml, jupyterlab, ipykernel

## Remove everything
```bash
rm -rf ISSCC27/submitted_notebooks/portable_vco_generator/.env \
       ISSCC27/submitted_notebooks/portable_vco_generator/.tools
```
(Delete `.env` and `.tools` only; the project sources stay.) If a Jupyter kernel was registered, also run
`jupyter kernelspec remove portable_vco` (see entries below).

## Changes outside this folder
(none so far)

## Log
- 2026-10-11: downloaded micromamba to `.tools/bin`; created `.gitignore` here (`.tools/`, `.env/`);
  started `micromamba create -p .env ...` (cache in `.tools/root`).
- 2026-10-11: attempt 1 (single solve incl. litex-hub klayout) FAILED on dependency conflict; nothing installed
  (`.tools/install_attempt1_failed.log`). Retrying in two steps: step 1 conda-forge stack
  (python 3.11, ngspice, klayout, numpy, scipy, matplotlib, pandas, pyyaml, jupyterlab, ipykernel) -> `.tools/install_step1.log`;
  step 2 litex-hub (open_pdks.sky130a, open_pdks.gf180mcuc, magic, netgen, yosys) -> `.tools/install_step2.log`.
- 2026-10-11: attempt 2 step 1 failed: `klayout` is not on conda-forge. Retrying without it (KLayout optional; may add pip `klayout` later and log it).
- 2026-10-11: install attempt 2 SUCCEEDED. Step 1 (conda-forge: python 3.11.17, ngspice 41, numpy, scipy, matplotlib, pandas, pyyaml, jupyterlab, ipykernel)
  + step 2 (litex-hub: open_pdks.sky130a 1.0.471, open_pdks.gf180mcuc 1.0.471, magic 8.3.464, netgen 1.5.272, yosys 0.69).
  Sizes: `.env` ~12-13 GB, `.tools/root` ~3 GB after cleanup. PDKs at `.env/share/pdk/{sky130A,gf180mcuC}` (use `PDK_ROOT=.env/share/pdk`).
  Exact package list: `environment.lock.txt`. Package cache can be cleared separately with `rm -rf .tools/root/pkgs`.
  Note: `netgen -batch quit` waits on stdin; use `netgen -batch lvs ...` or `< /dev/null`.
- 2026-10-11: no installs. Added project sources: `smoke/` (inverter tests), `vco_generator/` (pdk.py, netlist.py, simulate.py).
- 2026-10-11: install attempt 2 SUCCEEDED. Step 1 (conda-forge) + step 2 (litex-hub: open_pdks.sky130a 1.0.471, open_pdks.gf180mcuc 1.0.471, magic, netgen, yosys 0.69).
  Sizes: `.env` 13 GB, `.tools/root` (package cache) 3.0 GB. PDKs at `.env/share/pdk/{sky130A,gf180mcuC}` (use `PDK_ROOT=.env/share/pdk`).
  Exact package list: `environment.lock.txt`. Cache can be cleared separately with `rm -rf .tools/root/pkgs`.
- 2026-10-11: no installs. Added `vco_generator/analysis.py`, `__main__.py`; outputs in `results/*.json`.
- 2026-10-11: no installs. Added `vco_generator/plots.py`, `results/comparison.png`.
- 2026-10-11: no installs. netlist.py: added starve_pn (default 4x pn_ratio); re-ran results/*.json.
- 2026-10-11: no installs. Reverted default starve_pn to PDK inverter ratio (4x default made sky130 need 64x Lmin); regenerated results/*.json. starve_pn kept as a knob.
- 2026-10-11: no installs. Added DEVLOG.md, results/extra/supply_vs_starve_pn.json, analysis.supply_vs_starve_pn().
- 2026-10-11: started separate layout env `.env-layout/` (python 3.11 + pip `glayout` 0.2.0, which pulls gdsfactory<=7.7.0, numpy<=1.24, klayout pip<=0.29, etc.).
  Separate from `.env/` because glayout pins numpy<=1.24 (would downgrade the sim env). Log: `.tools/layout_install.log`.
  Remove: `rm -rf .env-layout` (and `.gitignore` line). Pip cache is kept inside the folder at `.tools/pipcache` (removed with `.tools`).
- 2026-10-11: layout env install SUCCEEDED (glayout 0.2.0, gdsfactory 7.7.0). Sizes in DEVLOG. Package list: `environment-layout.lock.txt`.
- 2026-10-11: no installs. Added `layout/probe_fet.py` and `layout/out/*.gds` (DRC probes).
- 2026-10-11: no installs. Added layout/cells.py (inverter), check_inverter.py, render.py, sweep_sides.py (debug), probe_fet.py. glayout files under .env-layout untouched.
- 2026-10-11: no installs. Added layout/cells.py stage(), check_stage.py; vco_generator/pdk.py gf180 wmin 0.46; results/gf180mcu.json regenerated; layout/out/*stage*.{gds,png}.
- 2026-10-11: no installs. Added layout/ring.py, check_ring.py, bias()/stage pins in layout/cells.py; outputs in layout/out/ (gds, png, work/ reports).
- 2026-10-11: no installs. Added vco_generator/postlayout.py, compare_post.py; layout ring gets N0 probe pin; results/extra/*pex*.spice, post_layout_*.json.
- 2026-10-11: no installs. results/extra/post_layout_{sky130,gf180mcu}.json + *_ring5_pex.spice written.
- 2026-10-11: no installs. Added environment.yml, environment-eda.txt, requirements-layout.txt, verify.py, golden/*.json.
- 2026-10-11: no installs. Added portable_vco_generator.ipynb (built by scratchpad script; executed via jupyter nbconvert with .env).
- 2026-10-11: no installs. Cleaned dev clutter (probe GDS, sweep_sides.py, temp logs); added README.md, LICENSE (Apache-2.0 copy of repo LICENSE); ring5 checks JSON + GDS/PNG are the committed layout results.
- 2026-10-11: no installs. Added vco_generator/montecarlo.py, --mc option, mismatch support in pdk/netlist/simulate; results/mc_*.json.
- 2026-10-11: no installs. Proofread notebook narrative (softened unverified claims, fixed diagram/numbering).
- 2026-10-11: installed `google-colab-cli` 0.7.4 (official, github.com/googlecolab/google-colab-cli) into a venv: `.tools/colab-venv/` (pip cache in `.tools/pipcache`). Binary: `.tools/colab-venv/bin/colab`.
  Outside the folder, created when you log in / start sessions: `~/.config/colab-cli/` (session state) and an OAuth token/config file under `~/` (`colab --help` shows the exact `--client-oauth-config` default path). Remove with `rm -rf ~/.config/colab-cli` plus that token file; revoke access at https://myaccount.google.com/permissions.
- 2026-10-11: Colab test done; VM session 'vcotest' stopped. CLI login state remains in ~/.config/colab-cli (token.json etc.): remove it and revoke access at https://myaccount.google.com/permissions when finished.
