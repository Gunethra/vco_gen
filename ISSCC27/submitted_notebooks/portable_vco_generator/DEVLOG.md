# Dev log: portable_vco_generator (ISSCC27 Code-a-Chip)

Working notes, not part of the submission text. Append as work proceeds.
Solo applicant. Deadline: Oct 31 2026, 11:59 AM PT (aim to open the PR by Oct 29).
Install/removal tracking is separate: see `INSTALL_LOG.md`.

## Decisions
| Date | Decision | Why |
|---|---|---|
| Oct 11 | Focus on the program's *reproducible, notebook-driven open-source design* goal | Past winners treat it as a side effect; no current PR makes it the subject |
| Oct 11 | Project = PDK-agnostic generator, one-variable PDK switch, portability table | Cross-PDK + generator is a niche no past winner / PR (#193-#209) covers |
| Oct 11 | Block = current-starved ring VCO (ring oscillator is its `starve=False` case) | Few device types, comparable FoMs across PDKs, no overlap with winners/PRs |
| Oct 11 | PDKs: sky130 + gf180mcu now, IHP sg13g2 as stretch | IHP open-tool layout flow is the likeliest time sink |
| Oct 11 | Local dev (micromamba), final test on Colab, Colab local-runtime later | FAQ/reviewers assume Colab; local is faster to iterate |
| Oct 11 | Bias circuit: keep the simple one, report supply sensitivity vs `starve_pn` as a documented trade-off (option 2) | Deadline; honest reporting; time better spent on layout |

## What worked
- micromamba 2.9.0 + conda-forge (python 3.11, ngspice 41, numpy/scipy/matplotlib/pandas/pyyaml/jupyterlab)
  then litex-hub (open_pdks sky130A + gf180mcuC 1.0.471, magic 8.3.464, netgen 1.5.272, yosys 0.69), in two steps.
- sky130 and gf180 inverter smoke tests (`smoke/`): sky130 tpHL 26 ps / tpLH 30 ps, Vm 0.87 V; gf180 39/35 ps, Vm 1.60 V.
- Generator (`vco_generator/`): same code, `get_pdk("sky130"|"gf180mcu")`, sweeps in ~10 s (sky130) / ~3 s (gf180).
- Auto-sizing to a target frequency by bisecting the starving-device width; falls back to longer starving L when the width floor is hit (sky130 needed 8x Lmin for 400 MHz).
- Normalised tuning curves (f vs Vctrl/Vdd) of the two PDKs nearly overlap; energy/cycle differs ~7x (sky130 ~150 fJ vs gf180 ~1.0 pJ), mostly supply voltage.

## What failed / was abandoned
| Attempt | Outcome | Fix / lesson |
|---|---|---|
| Single micromamba solve incl. litex-hub `klayout` | Dependency conflict (old Qt 5.9) | Two-step install; KLayout dropped (not on conda-forge) |
| `klayout` from conda-forge | Package does not exist there | Use Magic for DRC; pip `klayout` is optional later |
| gf180 netlist using per-device library sections (`nfet_03v3_t`, `fets_mm`) | `unknown subckt` / undefined `nfet_03v3_noia` | Use `.include design.ngspice` + `.lib sm141064.ngspice typical` (top-level corner section) |
| `np.trapz` | Removed in NumPy 2 | `getattr(np, "trapezoid", None) or np.trapz` |
| Sizer upper bound 40x unit width | PMOS 320 um: "could not find a valid modelname" (sky130 model width bins) | Cap PMOS width at 40 um |
| Wider starving PMOS (`starve_pn` x4) as the new default | sky130 then needed 64x Lmin to reach 400 MHz and sensitivity returned | Reverted default; kept `starve_pn` as a knob |
| `pgrep -f` wait-loops and `netgen -batch quit` in tool calls | Loops that never exit / hung process on stdin | Use `ps`-safe waits; give netgen a script or `< /dev/null` |

## Layout progress
- Oct 11: separate env `.env-layout` (glayout 0.2.0, gdsfactory 7.7.0, klayout 0.28.17, numpy 1.24): glayout pins numpy<=1.24, so it cannot share `.env`.
- glayout ships mapped PDKs for **sky130, gf180 and ihp130** (so IHP is feasible later) and `pdk.drc_magic()`.
- `layout/probe_fet.py`: single NMOS/PMOS (W=1 um, min L). sky130 DRC clean. **The gf180 "DRC passed" from this probe was a FALSE PASS**: glayout's gf180 setup points to `gf180mcuD` but we install `gf180mcuC`, so Magic never loaded the tech and still printed "passed". Caught only when the real tech file was supplied and errors appeared.
  Harmless soft warning from Magic on sky130: "Unknown layer/datatype layer=64 type=44".
- Quirk: `pmos()` does not take `with_dnwell` (only `nmos()` does).
- **Inverter cell (`layout/cells.py`, `layout/check_inverter.py`): DRC clean and LVS "Circuits match uniquely" on both sky130 and gf180mcu** (gf180 via explicit `gf180mcuC` magicrc/netgen setup overrides).
  Route recipe that worked: gates tied on the W side (met route), drains tied on the E side, each source tied to its own bulk tap with `straight_route(source_W -> tie_W_top_met_W, width >= PDK met1 min width)`.
  Pin handling for netgen: put a pin-layer polygon + label-layer label **directly in the top cell** (sub-cell labels become hierarchical names `Unnamed_x/VIN`; labels without a pin polygon give `.subckt` with no ports -> "failed pin matching").
- **Full current-starved stage (`layout/cells.py: stage`, `layout/check_stage.py`): DRC clean + LVS "Circuits match uniquely" on sky130 and gf180mcu.**
  Vertical stack: footer NMOS (VCTRL) / inverter NMOS / inverter PMOS / header PMOS (VB); series nodes via c_routes on W side with separate lanes (`lane_n`, `lane_p`), VIN gate route W, VOUT drain route E. Pins VIN VOUT VDD VSS VCTRL VB.
  Same-named labels on separate tap rings (VSS, VDD) merge nets in Magic, so no extra tie metal was needed for LVS; the ring assembly must still add real rails.
  Images: `layout/out/{sky130,gf180mcu}_stage.png` (render.py). Stage is ~23 um tall.
- gf180 layout limit found: gLayout needs W >= ~0.46 um to place the contact array (device min is 0.22). Generator `wmin_um` for gf180 raised to 0.46 and gf180 results regenerated (ws 0.678 um at 4x Lmin starve length; f_mid 399.5 MHz, supply -14.9 %/V, corners 41%, -3060 ppm/C). Lesson: a sim-only sizer must carry layout-feasibility constraints.
- n-well spacing: two PMOS in separate wells need PDK nwell spacing (sky130 1.27 um, gf180 1.4 um) -> extra gap between inverter PMOS and header PMOS.
- gf180 M2.1: connection-lane width must be >= PDK min (use `cwidth`); pin polygons must lie fully inside metal (shift inward) or they read as narrow drawn metal.
- **Full 5-stage ring + bias branch (`layout/ring.py`, `layout/check_ring.py`): DRC clean + LVS "Circuits match uniquely" on sky130 (104.9 x 40 um) and gf180mcu (112.6 x 44 um)**, sizes read from `results/*.json`.
  Scheme: supplies on met4 rails with met4 drops from tap-ring bars; VCTRL/VB rails on met4 with met5 drops (cross the supply rails); VOUT_k -> VIN_{k+1} as met4 L-links; wrap-around on met5 + met4 above the rails.
  Bugs found on the way: rails started after the bias pin (open net); VCTRL/VB met5 drops 0.5 um from the VIN drop (short); isolated met5 via pads (min-area); diode stub wider than the drain bar (met1.2 spacing); gf180 thick top metal needs width >= 0.44 / spacing 0.46 (glayout rule table says 0.28); via pads 0.25 um from lane (gf180 M3.2a) fixed with longer lanes (1.5 um).
  Same-name labels inside different cells must not be flattened together (VIN would merge across stages), so the ring is written hierarchically; Magic prints harmless "already defined" notices for the repeated cells.
- **Post-layout simulation (`vco_generator/postlayout.py`, `compare_post.py`; `results/extra/post_layout_*.json`)**: Magic flat extraction with parasitic C only (no wire R), 5-stage ring + bias, same Vctrl points as the schematic.
  Frequency vs schematic: sky130 -66% (low Vctrl) to -73% (1.8 V); gf180mcu -57% to -59%. Power within ~+-6%.
  Validation (sky130, Vctrl 1.14 V): extracted netlist with the 86 caps removed = 291.6 MHz (schematic 347.5; -16% from dummy devices/extra junctions), with caps = 102.4 MHz. Total extracted C 203 fF; each stage-output node ~4 fF of wire C, probe node N0 ~10 fF, vs ~4-5 fF intrinsic gate load: wire C of the 19 um met4 links dominates this tiny design. Reducing it = shorter links (tighter floorplan), wider devices, or higher Vctrl range.
  Extraction pitfalls: cells with port labels are not flattened by default (need `flatten RING_flat` before `extract all`, subckt becomes `RING_flat`); gf180 needs `ext2spice scale off` (default output is `.option scale=5n` integer units that the gf180 subckt models misinterpret -> "could not find a valid modelname").
- Still to do (superseded): ring assembly (5 stages + bias branch + rails), post-layout extraction and simulation, then the notebook. (Earlier item: assemble a full stage - done) (inverter + starving devices + routing), LVS with netgen, ring placement, post-layout extraction.

## Layout learnings / failures
| Problem | Cause | Fix |
|---|---|---|
| LVS nets 6 vs 4, bulks floating | sources not tied to bulk taps | route source -> tie |
| LVS: everything one net | gate and drain routes both on the E side shorted | gate W, drain E |
| `Unnamed_x/VIN` net names | label added via sub-cell reference | add label/pin polygon to top cell |
| "failed pin matching", no ports | labels without pin-layer shape | add pin polygon on `*_pin` layer |
| gf180 LVS "report not found" / DRC false pass | glayout hardcodes `gf180mcuD`; installed `gf180mcuC` | pass `magic_drc_file` / `lvs_setup_tcl_file` overrides |
| gf180 DRC M1.1 width < 0.23 um | hard-coded 0.2 um route width | take width from `pdk.get_grule("met1")["min_width"]` |
| glayout reports "Errors found in LVS report" even on a match | wrapper just checks report length > 3 lines | read `Final result:` line of the report instead |
| Primitive `info['netlist']` is a Netlist object (not `netlist_obj`) | gdsfactory 7.7 path | `_nl()` helper |
- glayout's net naming: sky130 glayer "met1" is physically li1 (67/20), "met2" is met1; generic code must use `pdk.get_glayer`.
- `layout/render.py` renders any GDS by layer (gdsfactory's plotter needs layer views that glayout PDKs lack).
- glayout LVS is not implemented for ihp130 (raises NotImplementedError), so IHP could get DRC/layout only.

## Monte Carlo mismatch (Oct 11)
- `vco_generator/montecarlo.py`; mismatch switched on per PDK (`PDK.mismatch`: sky130 = `tt_mm` library section, gf180 = `.param sw_stat_mismatch=1` after the includes). Seeds via `.options seed=N` (both `.options seed` and `.option rndseed` are reproducible; `set rndseed` inside `.control` is NOT, because agauss is evaluated at parse time).
- Mid Vctrl, 100 samples: sky130 sigma(f)/f = 0.91 % (mean shift -0.08 %), gf180mcu 0.39 % (+0.03 %); all samples within +-5 %. Sweep of Vctrl (40 samples): sky130 4.0 % at the lowest point -> 0.9 % at the top, gf180 2.9 % -> 0.24 %: weak-inversion sensitivity at low control voltage. Cause of sky130 being ~2x worse at mid not investigated. Local mismatch only, schematic only. `golden/mc_*.json`, `verify.py --mc`.

## Colab test (Oct 11, official `google-colab-cli` 0.7.4, CPU runtime, project uploaded as a tarball)
- Fresh VM (Python 3.13.16, numpy 2.1.3, pandas 2.2.3): install cell worked first time (micromamba, two-step; sky130A+gf180mcuC ~12 GB env). Notebook then ran clean, 15.8 min (characterisation 12 min, trade-off 2.5 min); `verify.py --from-results --mc`: 54 values, 0 outside tolerance. All numeric outputs identical to the local run (Python 3.11, numpy 2.4.6); only paths, versions and timestamps differ.
- First attempt failed by timeout: the 100-sample Monte Carlo + sweep (~600 sims) did not finish in 2 h on 2 vCPUs (one sky130 sim ~15 s there vs ~1.5-6 s locally) and verify.py re-simulated everything again. Fixes: `RUN_MC` flag (default loads the stored seeded results), `verify.py --from-results`, `RUN_VERIFY_FULL` flag.
- Second attempt failed at kernel start: my own diagnostic `colab exec` calls had put `.env/bin` on the persistent kernel's PATH, so the background job picked the micromamba Python 3.11. Launch jobs with `env -i PATH=...`.
- CLI quirks: `colab download` of an `.ipynb` writes a Python-literal dump, not JSON (parse with `ast.literal_eval`); a `DONE` marker from an earlier run makes a monitor report completion early: delete markers before launching, not after.
- Untested: the `git clone` path (`REPO_URL`), needs the fork pushed.

## Notebook / packaging (Oct 11)
- `portable_vco_generator.ipynb` built with a throwaway script (nbformat) and executed with `jupyter nbconvert --execute` in `.env`: runs clean, includes `verify.py` (48 values, 0 outside tolerance). Install cell untested on a fresh Colab runtime.
- Pinned: `environment.yml` + `environment-eda.txt` (2-step install), `requirements-layout.txt`. `golden/` = reference metrics.
- After gf180 re-sizing (ws 0.678 um, 4x Lmin) the trade-off table changed: gf180 supply sensitivity vs starve_pn = -14.9 / -31.9 / -39.6 %/V (older numbers in the table above were for the pre-0.46 um sizing). Ideal-current-source expectation (-1/Vdd = -30 %/V) is exceeded, so gf180 current also falls with Vdd; not analysed.
- Matplotlib: `vco_generator/plots.py` no longer forces the Agg backend (it broke inline figures).
- Pitfall: a stale `/tmp/*.flag` made a completion monitor fire early; remove the flag before launching the job, not after.

## Learnings
- **Sky130 supply sensitivity is a bias-circuit artifact**, not a PDK property. Measured on the bias branch alone:
  sky130 bias NMOS has Vds of only 0.15-0.33 V (gate ~1.2 V) so it is in triode and the current tracks Vdd (9.4/13.2/16.7 uA for Vdd -10%/nom/+10%);
  gf180's stays saturated (51/57/60 uA). Confirmed from DC numbers; the full physical explanation (inversion level, mirror headroom) is not separately verified.
- First-order current-source limit: f ~ I/(N*C*Vdd) so sensitivity -> -1/Vdd (-56 %/V sky130, -30 %/V gf180). gf180 with wide PMOS reaches -29 %/V.
- Library conventions differ per PDK (include lines, corner names typical vs tt, W/L units: plain um vs `u` suffix); these live in one place (`vco_generator/pdk.py`).
- Min L / Vdd / device names: sky130 0.15 um, 1.8 V; gf180 3.3 V devices 0.28 um (from library files).
- Reproducibility hygiene: pin versions (`environment.lock.txt`), keep everything inside the project folder, never rely on system installs, log every install.

## Supply-sensitivity trade-off (fixed baseline sizing, `results/extra/supply_vs_starve_pn.json`)
| PDK | starve_pn | f_mid [MHz] | supply sens. [%/V] |
|---|---|---|---|
| sky130 | 2.0 (default) | 402 | +55.3 |
| sky130 | 4.0 | 560 | +21.5 |
| sky130 | 8.0 | 717 | +12.1 |
| gf180mcu | 2.5 (default) | 398 | -12.6 |
| gf180mcu | 5.0 | 430 | -24.3 |
| gf180mcu | 10.0 | 459 | -29.1 |
Note f_mid changes with `starve_pn` (not re-sized), so rows are a trade-off sketch, not iso-frequency.

## Open items
- Layout (gLayout or GDSFactory), DRC (Magic), LVS (netgen), post-layout sim: sky130 first, gf180 if time.
- Monte Carlo mismatch; optional jitter via transient noise.
- Notebook: team table, references, tool versions, verify cell against `golden/` values, Apache-2.0 LICENSE, README.
- Colab test on a fresh runtime, then Colab local-runtime check.
- IHP sg13g2 (stretch).
- Examine remaining sky130 sensitivity (+12 %/V at wide PMOS) before claiming a cause.

## References (only what was actually used)
- Program rules: repo `README.md`, `FAQ.md` (install pattern: micromamba + litex-hub), `howtoapply.md` (stale; still ISSCC26), IEEE SSCS Code-a-Chip ISSCC27 page (saved HTML).
- Past winners studied for approach/structure (repo folders `*/accepted_notebooks`, `ISSCC26/submitted_notebooks`): OpenFASoC DLDO and GLayout (generators, PDK-agnostic layout), current-mirror OTA and CML optimization (C/ID sizing), Ron/gm (`VLSI26/accepted_notebooks/Wrøngm`, IHP SG13G2), EEG amplifier (gf180mcu + gLayout).
- PDK files used to get names/corners: `.env/share/pdk/sky130A/libs.tech/ngspice/sky130.lib.spice`,
  `.env/share/pdk/gf180mcuC/libs.tech/ngspice/{design.ngspice,sm141064.ngspice}` (installed via litex-hub `open_pdks.*` packages).
- Layout: glayout 0.2.0 / gdsfactory 7.7.0 (PyPI; project: github.com/ReaLLMASIC/gLayout, which two past winners used); `glayout/pdk/*_mapped`, `glayout/primitives/fet.py` read for the API.
- Tools: ngspice 41, Magic 8.3.464, netgen 1.5.272, yosys 0.69, micromamba 2.9.0 (conda-forge, litex-hub).
- Competing ISSCC27 PRs (`sscs-ose/sscs-ose-code-a-chip.github.io` #193-#209) surveyed for overlap; none does a VCO or cross-PDK flow.
