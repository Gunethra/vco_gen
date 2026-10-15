# portable_vco_generator

IEEE SSCS Code-a-Chip, ISSCC 2027 submission. **One Python generator, one switch (`sky130` / `gf180mcu`), a current-starved ring VCO from sizing to layout and post-layout simulation, with a verification cell for reproducibility.**

Main deliverable: [`portable_vco_generator.ipynb`](portable_vco_generator.ipynb) (outputs included).

## What it does
1. Generates a current-starved ring VCO netlist for a PDK, sizes it to a target frequency, and characterises it (tuning curve, Kvco, power, corners, temperature, supply).
2. Builds the layout of the 5-stage ring + bias branch with [gLayout](https://github.com/ReaLLMASIC/gLayout); Magic DRC clean and netgen LVS matched on both PDKs.
3. Extracts parasitic capacitance and re-simulates (post-layout).
4. Reports exactly what had to change between PDKs (`pdk.py` is the only PDK-specific file for simulation).

## Headline results (400 MHz at mid-range Vctrl, 5 stages)
| | sky130 (1.8 V) | gf180mcu (3.3 V) |
|---|---|---|
| Kvco at mid | 682 MHz/V | 380 MHz/V |
| Power / energy per cycle | 60 uW / 149 fJ | 403 uW / 1.0 pJ |
| Layout (ring + bias) | 105 x 40 um, DRC clean, LVS match | 113 x 44 um, DRC clean, LVS match |
| Mismatch Monte Carlo, sigma(f)/f at mid Vctrl (100 samples) | 0.91 % | 0.39 % |
| Post-layout frequency vs schematic | -66 % ... -73 % | -57 % ... -59 % |

The post-layout slowdown is parasitic capacitance of the inter-stage wiring (wire resistance is not extracted). Supply sensitivity is dominated by a simple bias circuit, not by the PDK; see section 5 of the notebook and `DEVLOG.md`.

## Run it
* **Colab / any Linux machine:** open the notebook and run all cells. It installs micromamba, the simulation environment (`environment.yml` + `environment-eda.txt`) and, if needed, the layout environment (`requirements-layout.txt`) inside the project folder. First install takes several minutes (the PDKs are large). Set `REPO_URL` in the first code cell to your fork when running on Colab.
* **Verify:** `python verify.py` re-runs both PDKs and checks 48 metrics against `golden/` (`--mc` adds the Monte Carlo statistics, `--post` the post-layout frequencies). Exit code 0 = reproduced.
* **Command line:** `python -m vco_generator --pdk sky130 --f-target 400e6` writes `results/<pdk>.json`; `python -m vco_generator.compare_post --pdk sky130` runs the post-layout comparison.

## Layout of this folder
| Path | Content |
|---|---|
| `vco_generator/` | generator (`pdk.py`, `netlist.py`, `simulate.py`, `analysis.py`, `postlayout.py`, `plots.py`) |
| `layout/` | gLayout cells (`cells.py`, `ring.py`), DRC/LVS drivers (`check_*.py`), GDS renderer; `layout/out/` holds the GDS, PNGs and DRC/LVS summaries |
| `results/`, `golden/` | current results and the reference values used by `verify.py` |
| `smoke/` | the first inverter smoke tests in each PDK |
| `DEVLOG.md` | decisions, failures and their fixes, learnings |
| `INSTALL_LOG.md` | what was installed during development and how to remove it |

## Limitations (stated plainly)
* Simple, non-cascoded bias: supply sensitivity is poor on sky130 (+55 %/V) and mildly negative on gf180 (-15 %/V).
* Post-layout simulation uses extracted capacitance only (no wire resistance). Monte Carlo covers local mismatch of the schematic only (not global process variation, not post-layout).
* The ring is not floorplan-optimised (19 um stage pitch with long links), which is why parasitics dominate.
* IHP SG13G2 is not implemented (gLayout ships an `ihp130` PDK, but its LVS is not implemented).
* Tested on a fresh Colab CPU runtime (Python 3.13) with the uploaded folder: install cell, all simulation cells and `verify.py` run clean and every numeric output is identical to a local run (Python 3.11). The `git clone` path (`REPO_URL`) needs your fork pushed and was not exercised.
* On a free 2-vCPU Colab VM the default run takes about 30 minutes (install ~15 min, notebook ~16 min). Recomputing the Monte Carlo (`RUN_MC`) or the layout (`RUN_LAYOUT`) takes hours there.

License: Apache-2.0.
