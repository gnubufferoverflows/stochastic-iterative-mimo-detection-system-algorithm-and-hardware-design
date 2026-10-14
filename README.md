# Stochastic Iterative MIMO Detection System

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](src/)
[![Verilog: IEEE 1364-2001](https://img.shields.io/badge/HDL-Verilog-orange.svg)](hdl/)
[![Verification: Triple--Engine](https://img.shields.io/badge/Verification-Triple--Engine-brightgreen.svg)](sim/run_tests.py)
[![IEEE: TCAS-I 2015](https://img.shields.io/badge/IEEE%20TCAS--I-2015-navy.svg)](https://doi.org/10.1109/TCSI.2015.2390558)
[![LLM: Assisted Research](https://img.shields.io/badge/LLM-Assisted%20Research-blueviolet.svg)](#research-disclaimer--llm-attribution)

- **Paper:** Chen, Hu & Sobelman, *Stochastic Iterative MIMO Detection System: Algorithm and Hardware Design*, IEEE TCAS-I  
- **DOI:** [10.1109/TCSI.2015.2390558](https://doi.org/10.1109/TCSI.2015.2390558)

---

> [!IMPORTANT]
> ### Research Disclaimer & LLM Attribution
> Academic PQ/SC research software (LLM-assisted). **Not** tape-out certified.
>
> - **LLM-Assisted Engineering**: TDG, signed SC mul/add, Gibbs warm-up + GsUD, Verilog blocks, FreePDK45, docs.
> - **130 nm Tables III–IV** and **4×4 16-QAM FER** are **REFERENCE ONLY**. Lab evaluates TDG mul SNR + uncoded **2×2 BPSK** SIM (decoder stub = hard MAP).

---

## Overview

**SIM** couples MCMC Gibbs MIMO detection with decoder-driven sample updates (GsUD) and short-stream **TDG** arithmetic.

Lab implements:

- TDG partition mul (exact + stream)
- Signed SC mul (Fig. 2) and Table I sat-add
- Warm-up + GsUD detector loop
- HDL building blocks + FreePDK45

## Quickstart

```bash
pip install -r requirements.txt
python scripts/run_campaign.py
python scripts/generate_plots.py
python sim/run_tests.py
python ../../tools/freepdk45/run_synth.py --project projects/sc-iterative-mimo-detection
```

## Visual Artifacts

### Figure 1 — Multiply SNR

![Fig1](docs/figures/fig1_mul_snr.png)

### Figure 2 — SIM vs ZF BER

![Fig2](docs/figures/fig2_ber.png)

### Figure 3 — FreePDK45 area

![Fig3](docs/figures/fig3_synth.png)

## Verification Results & Benchmarks

| Paper Section / Metric | Topic | Artifacts | Status | Compliance |
| :--- | :--- | :--- | :--- | :---: |
| Table II / Fig. 5 | TDG vs random/DSC mul SNR | campaign JSON | TDG ≫ random L=64 | **MEASURED** |
| Sec. III / Alg. GsUD | Gibbs + decoder update | `gibbs_mimo_detect` | 2×2 BPSK BER | **MEASURED** |
| Fig. 2 / Table I | Signed mul + sat-add | HDL + tests | bit-exact | **PASS** |
| Tables III–IV | 130 nm 128-parallel ASIC | — | not re-run | **REFERENCE ONLY** |
| Fig. 9–11 | 16-QAM FER / iterations | — | not re-run | **REFERENCE ONLY** |
| HDL | mul / sat-add / TDG accum | Icarus | 0 mism / 512 | **PASS** |
| ASIC | FreePDK45 | synth JSON | mul 2.66 / sat 17 / TDG 40 µm² | **MEASURED** |

## Python ↔ RTL

| Module | Checks | mismatches |
| :--- | :--- | ---: |
| `sc_signed_mul` + `sc_sat_add` + `tdg_accum_k5` | 512 shared stim | **0** |

## Results Analysis

1. **TDG** exact trunc mul SNR dominates short Bernoulli XNOR at L=64 (Table II trend).
2. **SIM GsUD** on easy 2×2 BPSK recovers symbols; BER improves with SNR vs ZF baseline in the same campaign.
3. **ASIC:** FreePDK45 areas are lab cells only — not 457K-gate Table III.

## Triple-Engine

Python TDG/SIM → Verilog mul/sat/TDG → Icarus → FreePDK45 Yosys/OpenSTA.

## BibTeX

```bibtex
@article{Chen2015_sim_mimo,
  author  = {Chen, Jienan and Hu, Jianhao and Sobelman, Gerald E.},
  title   = {Stochastic Iterative {MIMO} Detection System: Algorithm and Hardware Design},
  journal = {IEEE Transactions on Circuits and Systems I: Regular Papers},
  year    = {2015},
  volume  = {62},
  number  = {4},
  pages   = {1205--1214},
  doi     = {10.1109/TCSI.2015.2390558}
}
```

## License

[CC BY 4.0](LICENSE)
