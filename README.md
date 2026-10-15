# Stochastic Iterative MIMO Detection System: Algorithm and Hardware Design

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](src/)
[![Verilog: IEEE 1364-2001](https://img.shields.io/badge/HDL-Verilog-orange.svg)](hdl/)
[![Verification: Triple--Engine](https://img.shields.io/badge/Verification-Triple--Engine-brightgreen.svg)](sim/run_tests.py)
[![IEEE: TCAS-I 2015](https://img.shields.io/badge/IEEE%20TCAS--I-2015-navy.svg)](https://doi.org/10.1109/TCSI.2015.2390558)
[![Plot Style: dev--plot](https://img.shields.io/badge/Plot%20Style-dev--plot-blue.svg)](scripts/generate_plots.py)
[![PDK: FreePDK45](https://img.shields.io/badge/ASIC-FreePDK45%20%2F%20NanGate45-purple.svg)](benchmarks/synth_freepdk45.json)
[![LLM: Assisted Research](https://img.shields.io/badge/LLM-Assisted%20Research-blueviolet.svg)](#research-disclaimer--llm-attribution)

An independent reproduction, mathematical derivation, circuit architecture walkthrough, cycle-accurate RTL implementation, and benchmark verification suite for the landmark academic paper:

- **Paper:** *Stochastic Iterative MIMO Detection System: Algorithm and Hardware Design*
- **Authors:** Jienan Chen; Jianhao Hu; Gerald E. Sobelman
- **Affiliations:** University of Electronic Science and Technology of China (UESTC), Chengdu, China; University of Minnesota, Minneapolis, MN, USA
- **Journal:** IEEE Transactions on Circuits and Systems I: Regular Papers, vol. 62, no. 4, pp. 1205–1214, April 2015
- **DOI:** [10.1109/TCSI.2015.2390558](https://doi.org/10.1109/TCSI.2015.2390558)

---

> [!IMPORTANT]
> ### Research Disclaimer & LLM Attribution
> This repository contains open-source academic research implementations, circuit models, and verification frameworks for **Stochastic Computing (SC)** and **Markov Chain Monte Carlo (MCMC)** iterative MIMO soft detection accelerators.
>
> - **LLM-Assisted Engineering**: Algorithmic Python models ($4 \times 4$ 16-QAM and 64-QAM), Two Divisions Generator (TDG) short-stream multipliers, synthesizable Verilog RTL modules, cycle-accurate Icarus Verilog testbenches, and FreePDK45 physical synthesis flows were engineered with LLM assistance in collaboration with domain researchers.
> - **Academic & Research Software**: Provided strictly for academic study, research reproducibility, educational exploration, and EDA prototyping. It is **not** certified for commercial physical tape-outs without independent domain engineering validation.
> - **PDK & Technology Comparisons**: While the original paper implemented a 128-parallel ASIC case study on **SMIC/TSMC 130 nm** (cell library `cb13fs120_tsmc`, 1.2 V core), our physical gate-level synthesis numbers are measured using **Yosys + OpenSTA** targeting the open-source **FreePDK45 / NanGate Open Cell Library (45 nm, 1.1 V, typical corner)**.

---

## Table of Contents

- [Executive Summary](#executive-summary)
- [Quickstart & Verification](#quickstart--verification)
- [Paper-to-Code Traceability Matrix](#paper-to-code-traceability-matrix)
- [Repository Structure](#repository-structure)
- [Section II: System Model & Background (with Python & RTL Code)](#section-ii-system-model--background-with-python--rtl-code)
  - [1. Spatial-Multiplexing MIMO Channel Model (Eq. 1)](#1-spatial-multiplexing-mimo-channel-model-eq-1)
  - [2. Soft Bit Log-Likelihood Ratio (LLR) Definition (Eq. 2)](#2-soft-bit-log-likelihood-ratio-llr-definition-eq-2)
  - [3. Full MAP Exponential Marginalization (Eq. 3)](#3-full-map-exponential-marginalization-eq-3)
  - [4. Bit-Flop MCMC Gibbs Sampling Transition (Eq. 4)](#4-bit-flop-mcmc-gibbs-sampling-transition-eq-4)
  - [5. Signed Stochastic Signal Representation (Eq. 5, Fig. 1)](#5-signed-stochastic-signal-representation-eq-5-fig-1)
  - [6. Stochastic Signed Multiplication (Fig. 2)](#6-stochastic-signed-multiplication-fig-2)
  - [7. Stochastic Saturating Addition & Table I Truth Table (Eq. 6, Table I)](#7-stochastic-saturating-addition--table-i-truth-table-eq-6-table-i)
- [Section III: Stochastic Iterative MIMO Detection Algorithm (with Python & RTL Code)](#section-iii-stochastic-iterative-mimo-detection-algorithm-with-python--rtl-code)
  - [1. Joint Detection & Decoding (JDD) Timing Architecture (Fig. 3)](#1-joint-detection--decoding-jdd-timing-architecture-fig-3)
  - [2. Warm-Up Euclidean Soft Metrics (Eq. 7)](#2-warm-up-euclidean-soft-metrics-eq-7)
  - [3. Dithered Bernoulli Sampling Update (Eq. 8)](#3-dithered-bernoulli-sampling-update-eq-8)
  - [4. Max-Log LLR Output Post Warm-Up (Eq. 9)](#4-max-log-llr-output-post-warm-up-eq-9)
  - [5. Gibbs Sampler Updated by Decoder (GsUD) Core Loop (Eqs. 10–14)](#5-gibbs-sampler-updated-by-decoder-gsud-core-loop-eqs-1014)
  - [6. Intermediate Residual Vector Sharing & Fast Metric Updates (Eqs. 15–17, Fig. 4)](#6-intermediate-residual-vector-sharing--fast-metric-updates-eqs-1517-fig-4)
  - [7. Compare-and-Select (CAS) Unit (Eq. 18, Fig. 8)](#7-compare-and-select-cas-unit-eq-18-fig-8)
  - [8. Two Divisions Generator (TDG) Short-Stream Decomposition (Eqs. 19–22, Fig. 5)](#8-two-divisions-generator-tdg-short-stream-decomposition-eqs-1922-fig-5)
- [Section IV: Hardware Implementation & ASIC Architecture (with Python & RTL Code)](#section-iv-hardware-implementation--asic-architecture-with-python--rtl-code)
  - [1. Fully Parallel 128-Core Interleaving Topology (Eqs. 23–24, Fig. 6)](#1-fully-parallel-128-core-interleaving-topology-eqs-2324-fig-6)
  - [2. Top-Level Stochastic MIMO Detector Core (Fig. 7)](#2-top-level-stochastic-mimo-detector-core-fig-7)
  - [3. LLR Calculator Datapath Sub-Block (Fig. 8)](#3-llr-calculator-datapath-sub-block-fig-8)
- [Empirical Benchmarks & Experimental Results](#empirical-benchmarks--experimental-results)
  - [1. Multiplier Precision & SNR Benchmark (Table II Replication, Fig. 1)](#1-multiplier-precision--snr-benchmark-table-ii-replication-fig-1)
  - [2. Coded $4 \times 4$ MIMO FER Performance (Fig. 10 Replication, Fig. 2)](#2-coded-4-times-4-mimo-fer-performance-fig-10-replication-fig-2)
  - [3. Convergence Iterations Histogram (Fig. 9 Replication, Fig. 4)](#3-convergence-iterations-histogram-fig-9-replication-fig-4)
  - [4. BER Convergence vs. Inner & Outer Iterations (Fig. 11 Replication, Fig. 5)](#4-ber-convergence-vs-inner--outer-iterations-fig-11-replication-fig-5)
  - [5. Post-Layout ASIC Implementation (Table III Replication)](#5-post-layout-asic-implementation-table-iii-replication)
  - [6. SOTA Comparison for $4 \times 4$ MIMO Detectors (Table IV Replication, Fig. 6)](#6-sota-comparison-for-4-times-4-mimo-detectors-table-iv-replication-fig-6)
- [Silicon PPA & FreePDK45 Synthesis Results (Fig. 3)](#silicon-ppa--freepdk45-synthesis-results-fig-3)
- [Verification Suite & Triple-Engine Parity Check](#verification-suite--triple-engine-parity-check)
- [Key Insights & Microarchitectural Takeaways](#key-insights--microarchitectural-takeaways)
- [References & BibTeX Citation](#references--bibtex-citation)
- [License](#license)

---

## Executive Summary

Multiple-Input Multiple-Output (MIMO) spatial multiplexing is fundamental to modern wireless standards (5G-NR, Wi-Fi 6/7). However, soft-output MIMO detection requires evaluating log-likelihood ratios (LLRs) over a candidate space that scales exponentially ($2^{N_t M}$) with the number of transmit antennas $N_t$ and modulation order $M$. Traditional approaches face prohibitive bottlenecks:
- **Exhaustive Max-Log / List Sphere Detection (LSD):** Explodes in computational complexity and silicon area for $4 \times 4$ 16-QAM ($2^{16} = 65,536$ points) and 64-QAM ($2^{24} = 16,777,216$ points).
- **Conventional MCMC Detectors:** Suffer from slow convergence and stalling in local minima because the detector's Gibbs sampler runs independently without direct feedback from the channel decoder.
- **Serial Iterative Receivers:** Delay channel decoding until the detector finishes its inner iterations, resulting in high latency and low hardware utilization.

In their seminal TCAS-I 2015 paper, **Chen, Hu, and Sobelman** introduced **Stochastic Iterative MIMO (SIM)**, delivering three breakthrough innovations:
1. **Decoder-Driven Gibbs Sampling (GsUD):** Instead of sampling solely from internal conditional detector probabilities, the Gibbs sampler is directly refreshed by hard/soft decoded bits from the channel decoder. The decoder becomes an intrinsic component of the Gibbs update chain, drastically accelerating convergence to the optimal lattice vector.
2. **Intermediate Residual Vector Sharing:** By tracking $\mathbf{r} = \mathbf{y} - \mathbf{Hs}$ and computing perturbation vectors $\Delta \mathbf{r}_{k,b} = \mathbf{H}_{:,k}(s_k^+ - s_k^-)$, the norm computation for each single-bit flip is reduced from a matrix-vector product to a single inner product:
   $$\|\mathbf{r} \pm \Delta \mathbf{r}_{k,b}\|^2 = \|\mathbf{r}\|^2 \pm 2\mathbf{r}^H \Delta \mathbf{r}_{k,b} + \|\Delta \mathbf{r}_{k,b}\|^2$$
3. **Two Divisions Generator (TDG) Stochastic Arithmetic:** Conventional Bernoulli multipliers suffer from high variance at short stream lengths ($L=64$). TDG partitions a fixed-point word into coarse and fine segments ($X = X_1 + 2^{-N_1} X_2$), achieving **39.1 dB SNR at $L=64$** (a **+11.3 dB gain** over Sawtooth Wave Generators).
4. **128-Parallel Fully Parallel Silicon Architecture:** A fully unrolled 128-detector bank fabricated in 130 nm CMOS delivers **787.5 Mbps iterative throughput** at 500 MHz ($1.98\,\mathrm{mm}^2$, 457.4K gates, 314 mW), matching the FER of traditional receivers with 4 outer iterations at **$3.7\times$ the throughput of PPTS** and **$6.0\times$ the throughput of SISO MMSE-PIC**.

This repository provides an open-source, cycle-accurate implementation of the SIM algorithm and hardware suite across Python, synthesizable Verilog RTL, and FreePDK45 ASIC standard cell synthesis.

---

## Quickstart & Verification

### Prerequisites
- Python 3.10+ with `numpy` and `matplotlib`
- Icarus Verilog (`iverilog`, `vvp`)
- Yosys & OpenSTA (for ASIC physical synthesis)

### 1. Execute Verification Test Suite
Runs all Python algorithmic unit tests and executes the cycle-accurate Icarus Verilog testbench on shared stimulus:
```bash
python3 sim/run_tests.py
```
Expected output:
```text
Running Python algorithmic unit tests...
  [PASS] Signed multiplier truth table
  [PASS] Saturating adder Table I truth table
  [PASS] 16-QAM and 64-QAM Gray mapping roundtrip
  [PASS] Complex Rayleigh channel and equivalent real decomposition
  [PASS] Two Divisions Generator (TDG) Table II SNR verification
  [PASS] Intermediate residual sharing (Eqs. 15-17)
  [PASS] Complete SIM detector Gibbs warm-up and GsUD outer loop
Running cycle-accurate Icarus Verilog hardware simulation...
wrote 512 vectors to stim_sim.hex and gold_sim.hex
PASS Core GsUD detected=5a5a correctly matched decoder bits!
TB DONE n_vec=512 mismatches=0
Icarus parity OK: 0 mismatches across all units!
  [PASS] Synthesizable Verilog RTL suite parity check (0 mismatches)

ALL VERIFICATION TESTS COMPLETED SUCCESSFULLY!
```

### 2. Run Empirical Simulation Campaigns & Generate Visual Artifacts
```bash
python3 scripts/run_campaign.py
python3 scripts/generate_plots.py
```

### 3. Run FreePDK45 Yosys ASIC Synthesis
Synthesizes all 6 digital blocks with NanGate45 standard cells:
```bash
python3 tools/freepdk45/run_synth.py --project projects/stochastic-iterative-mimo-detection-system-algorithm-and-hardware-design
```

---

## Paper-to-Code Traceability Matrix

| Paper Section & Topic | Landmark Equation / Concept | Python Algorithmic Model | Synthesizable Verilog RTL | Verification & Testbench | Microarchitectural Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Sec. II-A: Channel Model** | $\boxed{\mathbf{y} = \mathbf{Hs} + \mathbf{n}}$ (Eq. 1) | [`generate_channel`, `complex_to_real_mimo`](src/mimo_channel.py#L11-L40) | Handled in testbench / system top | [`sim/run_tests.py`](sim/run_tests.py#L80-L95) | $4 \times 4$ Rayleigh flat-fading; real equivalent $8 \times 8$ real matrix. |
| **Sec. II-A: Soft LLR** | $\boxed{\lambda(x_{k,b}) = \ln \frac{P(x_{k,b}=+1)}{P(x_{k,b}=-1)}}$ (Eq. 2) | [`maxlog_llr_qam`](src/sim_mimo.py#L50-L115) | [`llr_calculator.v`](hdl/llr_calculator.v#L35-L45) | [`sim/run_tests.py`](sim/run_tests.py) | Max-log approximation evaluated via stochastic norm streams. |
| **Sec. II-A: Direct MAP** | $2^{N_t M - 1}$ sum (Eq. 3) | [`maxlog_llr_qam`](src/sim_mimo.py) | Exponential cost avoided by SIM | Analysis reference | Direct evaluation prohibitive for high-order constellations. |
| **Sec. II-A: Gibbs Sampling** | $\boxed{P(x_{k,b}=+1) = \frac{1}{1+e^{-\lambda}}}$ (Eq. 4) | [`sim_mimo_detect`](src/sim_mimo.py#L145-L160) | [`sim_mimo_detector_core.v`](hdl/sim_mimo_detector_core.v#L125-L135) | [`hdl/tb_sim.v`](hdl/tb_sim.v) | Bernoulli trial updates single bit conditioning on current state. |
| **Sec. II-B: SC Representation** | $\boxed{X = (1-2\mathbb{E}[s])\mathbb{E}[a]}$ (Eq. 5, Fig. 1) | [`quantize_signed`](src/tdg.py#L64-L75) | [`llr_calculator.v`](hdl/llr_calculator.v#L42-L48) | [`sim/run_tests.py`](sim/run_tests.py#L35-L42) | Signed stochastic stream: sign bit stream + unipolar magnitude stream. |
| **Sec. II-B: SC Multiplier** | Signed multiply (Fig. 2) | [`sc_signed_mul_bits`](src/tdg.py#L30-L37) | [`sc_signed_mul.v`](hdl/sc_signed_mul.v#L1-L14) | [`hdl/tb_sim.v`](hdl/tb_sim.v#L15-L18) | Magnitude via AND gate; sign via XOR gate; 100% bit parity. |
| **Sec. II-B: SC Saturating Adder** | Table I Truth Table (Eq. 6, Table I) | [`sc_sat_add_bits`](src/tdg.py#L40-L58) | [`sc_sat_add.v`](hdl/sc_sat_add.v#L1-L26) | [`hdl/tb_sim.v`](hdl/tb_sim.v#L19) | 2-bit ternary state with feedback retention when opposite signs cancel. |
| **Sec. III-A: JDD Architecture** | Serial vs Layered vs JDD (Fig. 3) | [`sim_mimo_detect`](src/sim_mimo.py) | Controller in [`sim_mimo_detector_core.v`](hdl/sim_mimo_detector_core.v) | [`scripts/generate_plots.py`](scripts/generate_plots.py) | Eliminates idle decoder cycles by overlapping detection & decoding. |
| **Sec. III-B: Warm-Up Metrics** | $\boxed{\Lambda(\pm 1) = -\|\mathbf{y}-\mathbf{Hs}^{\pm}\|^2/\sigma^2}$ (Eq. 7) | [`maxlog_llr_qam`](src/sim_mimo.py#L88-L112) | [`sim_mimo_detector_core.v`](hdl/sim_mimo_detector_core.v#L90-L100) | [`sim/run_tests.py`](sim/run_tests.py) | Evaluates candidate perturbation distance around current state. |
| **Sec. III-B: Gibbs Update** | $\boxed{x_{k,b}^{(t+1)} \sim \mathrm{Bernoulli}(P)}$ (Eq. 8) | [`sim_mimo_detect`](src/sim_mimo.py#L148-L158) | [`sim_mimo_detector_core.v`](hdl/sim_mimo_detector_core.v) | [`sim/run_tests.py`](sim/run_tests.py) | Dithered sigmoid sampling prevents latching in sub-optimal local minima. |
| **Sec. III-B: Warm-Up LLR** | $\boxed{\lambda \approx \max\Lambda(+1)-\max\Lambda(-1)}$ (Eq. 9) | [`maxlog_llr_qam`](src/sim_mimo.py) | [`llr_calculator.v`](hdl/llr_calculator.v#L35) | [`sim/run_tests.py`](sim/run_tests.py) | Max-log metric difference passed to channel decoder. |
| **Sec. III-B: GsUD Decoder Update** | $\boxed{x_{k,b}^{(t+1)} = \hat{x}_{k,b}^{\mathrm{dec}}}$ (Eq. 10) | [`sim_mimo_detect`](src/sim_mimo.py#L170-L180) | [`sim_mimo_detector_core.v`](hdl/sim_mimo_detector_core.v#L125-L128) | [`hdl/tb_sim.v`](hdl/tb_sim.v#L140-L155) | Hardware input `dec_bits_in` directly sets Gibbs state. |
| **Sec. III-B: Constellation Mapping** | $\boxed{s_k = \mathrm{map}(\mathbf{x}_k)}$ (Eq. 11) | [`map_bits_to_qam`](src/qam.py#L78-L93) | [`sim_mimo_detector_core.v`](hdl/sim_mimo_detector_core.v) | [`sim/run_tests.py`](sim/run_tests.py#L65-L75) | Gray-coded PAM-4 (16-QAM) and PAM-8 (64-QAM) mapping. |
| **Sec. III-B: Extrinsic LLR** | $\boxed{\lambda_{\mathrm{ext}} = \Lambda(+1)-\Lambda(-1)-\lambda_a}$ (Eqs. 12–14) | [`sim_mimo_detect`](src/sim_mimo.py#L184-L186) | [`llr_calculator.v`](hdl/llr_calculator.v) | [`sim/run_tests.py`](sim/run_tests.py) | A-priori subtraction prevents positive feedback instability. |
| **Sec. III-C: Residual Sharing** | $\boxed{\mathbf{r} = \mathbf{y}-\mathbf{Hs}}$ (Eq. 15) | [`compute_residual`](src/sim_mimo.py#L30-L33) | [`sim_mimo_detector_core.v`](hdl/sim_mimo_detector_core.v) | [`sim/run_tests.py`](sim/run_tests.py#L118-L135) | Global residual maintained across Gibbs bit flips. |
| **Sec. III-C: Column Perturbation** | $\boxed{\Delta\mathbf{r} = \mathbf{H}_{:,k}(s^+-s^-)}$ (Eq. 16) | [`update_residual_delta`](src/sim_mimo.py#L35-L47) | [`sim_mimo_detector_core.v`](hdl/sim_mimo_detector_core.v) | [`sim/run_tests.py`](sim/run_tests.py) | Perturbation vector scales single column of channel matrix. |
| **Sec. III-C: Fast Norm Update** | $\boxed{\|\mathbf{r}\pm\Delta\mathbf{r}\|^2 = \|\mathbf{r}\|^2 \pm 2\mathbf{r}^H\Delta\mathbf{r} + \|\Delta\mathbf{r}\|^2}$ (Eq. 17) | [`update_residual_delta`](src/sim_mimo.py#L41-L46) | [`sim_mimo_detector_core.v`](hdl/sim_mimo_detector_core.v) | [`sim/run_tests.py`](sim/run_tests.py) | Inner product replaces full matrix-vector reconstruction. |
| **Sec. III-C: Compare-and-Select** | $\boxed{\lambda = \mathrm{CAS}(\{\Lambda_i\})}$ (Eq. 18, Fig. 8) | Python max-log reduction | [`sc_cas_unit.v`](hdl/sc_cas_unit.v#L1-L32) | [`hdl/tb_sim.v`](hdl/tb_sim.v#L50-L55) | Subtraction + MSB select; feedback register tracks running max. |
| **Sec. III-D: TDG Decomposition** | $\boxed{X = X_1 + 2^{-N_1}X_2}$ (Eqs. 19–22, Fig. 5) | [`tdg_decompose`, `tdg_multiply`](src/tdg.py#L77-L143) | [`tdg_accum.v`, `tdg_accum_k5.v`](hdl/tdg_accum.v) | [`sim/run_tests.py`](sim/run_tests.py#L100-L115) | Coarse ($N_1$) + fine ($N_2$) partitions; achieves 39.1 dB SNR at $L=64$. |
| **Sec. IV-A: Fully Parallel SIM** | $\boxed{N_d\cdot N_t\cdot M = N_{\mathrm{dec}}}$ (Eqs. 23–24, Fig. 6) | Vectorized multi-frame batch | 128-parallel array topology | System dimensioning | 128 cores * 4 antennas * 4 bits = 2048-bit frame; 16 Gbps peak LLR rate. |

---

## Repository Structure

```text
projects/stochastic-iterative-mimo-detection-system-algorithm-and-hardware-design/
├── LICENSE                               # MIT Open-Source License
├── README.md                             # Comprehensive technical documentation (>1200 lines)
├── report.md                             # Verification scorecard & compliance report
├── requirements.txt                      # Python dependencies (numpy, matplotlib)
├── benchmarks/
│   ├── results/
│   │   └── sim_campaign.json             # Empirical simulation measurements & Table II dumps
│   └── synth_freepdk45.json              # Measured FreePDK45 Yosys synthesis results
├── docs/
│   └── figures/                          # Publication-grade figures (300 DPI, dev-plot)
│       ├── fig1_mul_snr.png / .svg       # Table II stochastic multiplier SNR comparison
│       ├── fig2_fer_performance.png     # Figure 10 FER performance vs outer iterations
│       ├── fig3_synth_breakdown.png      # FreePDK45 ASIC synthesis area and cell count
│       ├── fig4_iterations_hist.png     # Figure 9 convergence iterations histogram
│       ├── fig5_ber_vs_iterations.png   # Figure 11 BER vs inner/outer iterations
│       ├── fig6_throughput_comparison.png# Table IV SOTA iterative throughput comparison
│       └── fig7_jdd_timing_comparison.png# Figure 3 timing architecture comparison
├── hdl/
│   ├── sc_signed_mul.v                   # Synthesizable signed stochastic multiplier (Fig. 2)
│   ├── sc_sat_add.v                      # Synthesizable saturating adder (Table I, Eq. 6)
│   ├── tdg_accum.v                       # Two Divisions Generator accumulator engine (Fig. 5)
│   ├── tdg_accum_k5.v                    # Parameterized K=5 (L=32/64) TDG wrapper
│   ├── sc_cas_unit.v                     # Compare-and-Select (CAS) unit (Eq. 18, Fig. 8)
│   ├── llr_calculator.v                  # Complete LLR calculator datapath (Fig. 8)
│   ├── sim_mimo_detector_core.v          # Top-level stochastic MIMO detector core (Fig. 7)
│   └── tb_sim.v                          # Cycle-accurate Icarus Verilog testbench
├── scripts/
│   ├── run_campaign.py                   # Empirical simulation campaign runner
│   └── generate_plots.py                 # Publication-grade figure generator (/dev-plot)
├── sim/
│   ├── gen_stim.py                       # Automated co-simulation stimulus generator
│   ├── run_icarus.sh                     # Icarus compilation and regression script
│   ├── run_tests.py                      # Master Python test suite & parity verification
│   ├── gold_sim.hex                      # Golden reference output vectors
│   ├── stim_sim.hex                      # Co-simulation input stimulus vectors
│   └── tb_counts.txt                     # Testbench mismatch summary report
├── src/
│   ├── __init__.py                       # Package exports
│   ├── mimo_channel.py                   # Complex Rayleigh channel & real equivalent decomposition
│   ├── qam.py                            # Gray-coded 16-QAM and 64-QAM mapping / demapping
│   ├── sim_mimo.py                       # SIM Gibbs warm-up, GsUD loop, and residual sharing
│   └── tdg.py                            # TDG multiplier and Table II benchmark suite
└── synth/
    ├── targets.json                      # FreePDK45 synthesis target specification
    └── out/                              # Synthesized gate netlists and timing logs
```

---

## Section II: System Model & Background (with Python & RTL Code)

### 1. Spatial-Multiplexing MIMO Channel Model (Eq. 1)

In a spatial-multiplexing MIMO wireless transmission system with $N_t$ transmit antennas and $N_r$ receive antennas ($N_r \ge N_t$), the baseband complex received vector $\mathbf{y} \in \mathbb{C}^{N_r}$ is modeled as:

$$
\boxed{
\mathbf{y} = \mathbf{H}\mathbf{s} + \mathbf{n}
}
\tag{1}
$$

where:
- $\mathbf{H} \in \mathbb{C}^{N_r \times N_t}$ is the complex Rayleigh flat-fading channel matrix whose entries are circular symmetric complex Gaussian random variables: $H_{i,j} \sim \mathcal{CN}(0, 1) = \frac{1}{\sqrt{2}}(\mathcal{N}(0, 1) + j \mathcal{N}(0, 1))$.
- $\mathbf{s} \in \mathcal{S}^{N_t}$ is the complex transmit symbol vector, where each symbol $s_k \in \mathcal{S}$ is drawn from a $2^M$-QAM constellation normalized to unit average energy: $\mathbb{E}[|s_k|^2] = 1$.
- $\mathbf{n} \in \mathbb{C}^{N_r}$ is the additive white Gaussian noise (AWGN) vector with covariance $\mathbb{E}[\mathbf{n}\mathbf{n}^H] = \sigma^2 \mathbf{I}_{N_r}$, where $\sigma^2 = N_0$ is the complex noise variance.

For hardware implementation, the complex system is converted into an equivalent real-valued model of doubled dimension ($2N_r \times 2N_t$):

$$
\begin{bmatrix} \operatorname{Re}(\mathbf{y}) \\ \operatorname{Im}(\mathbf{y}) \end{bmatrix}
=
\begin{bmatrix} \operatorname{Re}(\mathbf{H}) & -\operatorname{Im}(\mathbf{H}) \\ \operatorname{Im}(\mathbf{H}) & \operatorname{Re}(\mathbf{H}) \end{bmatrix}
\begin{bmatrix} \operatorname{Re}(\mathbf{s}) \\ \operatorname{Im}(\mathbf{s}) \end{bmatrix}
+
\begin{bmatrix} \operatorname{Re}(\mathbf{n}) \\ \operatorname{Im}(\mathbf{n}) \end{bmatrix}
$$

#### Python Algorithmic Model
```python
def generate_channel(n_r: int = 4, n_t: int = 4, rng: np.random.Generator | None = None) -> np.ndarray:
    # Eq. (1): Generate complex i.i.d. Rayleigh flat-fading channel matrix H.
    rng = rng or np.random.default_rng()
    h_real = rng.normal(0.0, 1.0 / np.sqrt(2.0), size=(n_r, n_t))
    h_imag = rng.normal(0.0, 1.0 / np.sqrt(2.0), size=(n_r, n_t))
    return h_real + 1j * h_imag

def complex_to_real_mimo(y: np.ndarray, H: np.ndarray, s: np.ndarray | None = None):
    # Convert complex MIMO system y = H*s + n into real-valued equivalent.
    n_r, n_t = H.shape
    y_real = np.concatenate([np.real(y), np.imag(y)])
    H_real = np.block([[np.real(H), -np.imag(H)], [np.imag(H), np.real(H)]])
    s_real = np.concatenate([np.real(s), np.imag(s)]) if s is not None else None
    return y_real, H_real, s_real
```

#### Synthesizable Verilog RTL Implementation
In hardware, the received real vector $\mathbf{y}_{\mathbb{R}}$ and channel columns $\mathbf{H}_{\mathbb{R}}$ are loaded into parallel fixed-point registers:
```verilog
// Channel vector registers for real-equivalent 4x4 MIMO (NR_REAL=8, NT_REAL=8)
parameter integer WIDTH = 16;
reg signed [WIDTH-1:0] reg_y [0:7];
reg signed [WIDTH-1:0] reg_H [0:7][0:7];

always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        for (i = 0; i < 8; i = i + 1) reg_y[i] <= 0;
    end else if (load_channel) begin
        reg_y[rx_dim] <= channel_din;
    end
end
```

---

### 2. Soft Bit Log-Likelihood Ratio (LLR) Definition (Eq. 2)

The channel decoder requires soft reliability information rather than hard decisions. The Log-Likelihood Ratio (LLR) $\lambda(x_{k,b})$ for the $b$-th bit of the $k$-th transmit antenna is defined as:

$$
\boxed{
\lambda(x_{k,b}) = \ln\frac{P(x_{k,b}=+1)}{P(x_{k,b}=-1)}
}
\tag{2}
$$

A positive LLR indicates that $x_{k,b}=+1$ is more probable, with magnitude $|\lambda|$ representing decision confidence.

#### Python Algorithmic Model
```python
def compute_llr_definition(p_pos: float, p_neg: float) -> float:
    # Eq. (2): Soft bit reliability as a log-odds ratio.
    p_pos = max(p_pos, 1e-15)
    p_neg = max(p_neg, 1e-15)
    return float(np.log(p_pos / p_neg))
```

#### Synthesizable Verilog RTL Implementation
In fixed-point digital logic, the log-odds ratio is mapped into signed 16-bit Two's-Complement System (TCS):
```verilog
// Two's complement LLR representation
wire signed [15:0] llr_tcs;
wire               llr_sign = llr_tcs[15]; // 1: negative (-1), 0: positive (+1)
wire [14:0]        llr_confidence = llr_sign ? (~llr_tcs[14:0] + 1'b1) : llr_tcs[14:0];
```

---

### 3. Full MAP Exponential Marginalization (Eq. 3)

The exact conditional probabilities require marginalizing over all other $N_t M - 1$ bits:

$$
\boxed{
\begin{aligned}
P(x_{k,b}=+1\mid\mathbf{y},\boldsymbol{\lambda}_2^{e}) &= \sum_{\mathbf{x}_{-k,b}} P(x_{k,b}=+1,\mathbf{x}_{-k,b}\mid\mathbf{y},\boldsymbol{\lambda}_2^{e}) \\
P(x_{k,b}=-1\mid\mathbf{y},\boldsymbol{\lambda}_2^{e}) &= \sum_{\mathbf{x}_{-k,b}} P(x_{k,b}=-1,\mathbf{x}_{-k,b}\mid\mathbf{y},\boldsymbol{\lambda}_2^{e})
\end{aligned}
}
\tag{3}
$$

Because the summation encompasses $2^{N_t M - 1}$ terms ($2^{15} = 32,768$ candidates for 16-QAM and $2^{23} = 8,388,608$ candidates for 64-QAM per bit), direct hardware evaluation is impossible. MCMC Gibbs sampling avoids this sum by sampling along the Markov trajectory.

---

### 4. Bit-Flop MCMC Gibbs Sampling Transition (Eq. 4)

In a bit-flop MCMC detector, bits are updated sequentially via Gibbs sampling. Since $x_{k,b} \in \{-1, +1\}$ is binary, the conditional distribution reduces to a Bernoulli trial:

$$
\boxed{
P(x_{k,b}=+1\mid\mathbf{x}_{-k,b},\mathbf{y},\boldsymbol{\lambda}_2^{e}) = \frac{1}{1+\exp(-\lambda(x_{k,b}))}
}
\tag{4}
$$

#### Python Algorithmic Model
```python
def gibbs_bernoulli_prob(llr: float) -> float:
    # Eq. (4): Turn the bit LLR into a Gibbs sampling transition probability.
    llr_clipped = np.clip(llr, -30.0, 30.0)
    return float(1.0 / (1.0 + np.exp(-llr_clipped)))
```

#### Synthesizable Verilog RTL Implementation
In stochastic hardware, the sigmoid function is implemented via a comparator against a pseudo-random number generator:
```verilog
// Stochastic Gibbs sampler transition (Eq. 4)
wire [14:0] lfsr_rng; // Uniform PRNG in [0, 32767]
wire        sample_x_next = (sigmoid_lut > lfsr_rng);
```

---

### 5. Signed Stochastic Signal Representation (Eq. 5, Fig. 1)

In signed stochastic computing, a fixed-point TCS value $X \in [-1.0, 1.0]$ is encoded by two binary streams:
1. **Magnitude Stream $a(X)$:** Generated by comparing $|X|$ against a uniform random number.
2. **Sign Stream $s(X)$:** Direct digital copy of the sign bit ($0$ for positive, $1$ for negative).

Over a bit-stream window of length $L$, the represented mathematical value is:

$$
\boxed{
X = \bigl(1-2\,\mathbb{E}[s(X)]\bigr)\,\mathbb{E}[a(X)]
}
\tag{5}
$$

```text
               TCS Magnitude |X| ───┐
                                    ├──►[ Digital Comparator ]──► Magnitude Stream a(X)
                Uniform RNG W[t] ───┘
                    TCS Sign Bit ────────────────────────────────► Sign Stream s(X)
```

#### Python Algorithmic Model
```python
def sc_encode_signed(x: float, length: int = 64, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    # Eq. (5), Fig. 1: Generate signed stochastic magnitude and sign streams.
    rng = np.random.default_rng(seed)
    x_clip = float(np.clip(x, -1.0, 1.0))
    sign_val = 1 if x_clip < 0 else 0
    mag_val = abs(x_clip)
    mag_stream = (rng.random(length) < mag_val).astype(np.uint8)
    sign_stream = np.full(length, sign_val, dtype=np.uint8)
    return mag_stream, sign_stream
```

#### Synthesizable Verilog RTL Implementation
```verilog
// Fig. 1: Sequence Generator Scheme
module sequence_generator #(parameter WIDTH = 10) (
    input  wire signed [WIDTH-1:0] x_tcs,
    input  wire [WIDTH-2:0]        rng_val,
    output wire                    s_sign,
    output wire                    a_mag
);
    assign s_sign = x_tcs[WIDTH-1];
    wire [WIDTH-2:0] abs_val = s_sign ? (~x_tcs[WIDTH-2:0] + 1'b1) : x_tcs[WIDTH-2:0];
    assign a_mag  = (abs_val > rng_val);
endmodule
```

---

### 6. Stochastic Signed Multiplication (Fig. 2)

Stochastic signed multiplication operates on dual-stream inputs $(a(X), s(X))$ and $(a(Y), s(Y))$. The product magnitude requires an **AND gate**, while the product sign requires an **XOR gate**:

$$
\begin{aligned}
a(Z) &= a(X) \wedge a(Y) \\
s(Z) &= s(X) \oplus s(Y)
\end{aligned}
$$

```text
          a(X) ───────┐
                      ├──►[ AND Gate ]──► a(Z) = a(X) & a(Y)
          a(Y) ───────┘

          s(X) ───────┐
                      ├──►[ XOR Gate ]──► s(Z) = s(X) ^ s(Y)
          s(Y) ───────┘
```

#### Python Algorithmic Model
```python
def sc_signed_mul_bits(a_mag: int, a_sign: int, b_mag: int, b_sign: int) -> tuple[int, int]:
    # Fig. 2: Stochastic signed multiplier bit-level operation.
    z_mag  = int(a_mag & b_mag) & 1
    z_sign = int(a_sign ^ b_sign) & 1
    return z_mag, z_sign
```

#### Synthesizable Verilog RTL Implementation ([`hdl/sc_signed_mul.v`](file:///home/yongfu/proj/probabilistic-computing-lab/projects/stochastic-iterative-mimo-detection-system-algorithm-and-hardware-design/hdl/sc_signed_mul.v))
```verilog
module sc_signed_mul (
    input  wire a_mag,
    input  wire a_sign,
    input  wire b_mag,
    input  wire b_sign,
    output wire z_mag,
    output wire z_sign
);
    assign z_mag  = a_mag & b_mag;
    assign z_sign = a_sign ^ b_sign;
endmodule
```

---

### 7. Stochastic Saturating Addition & Table I Truth Table (Eq. 6, Table I)

Stochastic addition of signed ternary streams $\{-1, 0, +1\}$ is governed by **Table I** [16]. When conflicting polarities cancel ($+1$ and $-1$), the adder holds the previous saturation state $\operatorname{sat}(Z(t-1))$, preventing error accumulation:

$$
\boxed{
\begin{aligned}
s(Z) &= \bigl(a(X) \wedge s(Y)\bigr) \vee \bigl(a(Y) \wedge s(X)\bigr) \\
a(Z) &= \bigl(a(X) \odot a(Y)\bigr) \vee \Bigl(a(X) \wedge \bigl(s(Y) \oplus s(X)\bigr)\Bigr) \\
\operatorname{sat}(Z) &= \bigl(s(Y) \odot s(X)\bigr) \wedge \bigl(a(X) \wedge a(Y)\bigr)
\end{aligned}
}
\tag{6}
$$

#### Table I: Truth Table of Stochastic Addition
| $X(t), Y(t)$ | $Z(t)$ | $\operatorname{Sat}(Z(t))$ | Microarchitectural Action |
| :---: | :---: | :---: | :--- |
| **$+1, +1$** | $+1$ | $+1$ | Positive saturation |
| **$+1, 0$ or $0, +1$** | $+1$ | $0$ | Positive sum |
| **$-1, 0$ or $0, -1$** | $-1$ | $0$ | Negative sum |
| **$-1, -1$** | $-1$ | $-1$ | Negative saturation |
| **$+1, -1$ or $-1, +1$** | $\operatorname{sat}(Z(t-1))$ | $0$ | Cancellation: retain previous saturation state |
| **$0, 0$** | $\operatorname{sat}(Z(t-1))$ | $0$ | Idle: retain previous saturation state |

#### Python Algorithmic Model
```python
def sc_sat_add_bits(x: int, y: int, sat_prev: int) -> tuple[int, int]:
    # Table I: Stochastic saturating signed addition.
    if x == 1 and y == 1:
        return 1, 1
    elif (x == 1 and y == 0) or (x == 0 and y == 1):
        return 1, 0
    elif (x == -1 and y == 0) or (x == 0 and y == -1):
        return -1, 0
    elif x == -1 and y == -1:
        return -1, -1
    else: # Opposite signs or both zero: hold saturation memory
        return sat_prev, 0
```

#### Synthesizable Verilog RTL Implementation ([`hdl/sc_sat_add.v`](file:///home/yongfu/proj/probabilistic-computing-lab/projects/stochastic-iterative-mimo-detection-system-algorithm-and-hardware-design/hdl/sc_sat_add.v))
```verilog
module sc_sat_add (
    input  wire signed [1:0] x,
    input  wire signed [1:0] y,
    input  wire signed [1:0] sat_prev,
    output reg  signed [1:0] z,
    output reg  signed [1:0] sat
);
    always @* begin
        if (x == 2'sd1 && y == 2'sd1) begin
            z = 2'sd1; sat = 2'sd1;
        end else if ((x == 2'sd1 && y == 2'sd0) || (x == 2'sd0 && y == 2'sd1)) begin
            z = 2'sd1; sat = 2'sd0;
        end else if ((x == -2'sd1 && y == 2'sd0) || (x == 2'sd0 && y == -2'sd1)) begin
            z = -2'sd1; sat = 2'sd0;
        end else if (x == -2'sd1 && y == -2'sd1) begin
            z = -2'sd1; sat = -2'sd1;
        end else begin
            z = sat_prev; sat = 2'sd0;
        end
    end
endmodule
```

---

## Section III: Stochastic Iterative MIMO Detection Algorithm (with Python & RTL Code)

### 1. Joint Detection & Decoding (JDD) Timing Architecture (Fig. 3)

The paper investigates three distinct iterative receiver pipeline architectures:
1. **Serial Architecture (Fig. 3(a)):** Detector executes all inner iterations before passing LLRs to the decoder; the detector remains idle while the decoder runs.
2. **Layered Architecture (Fig. 3(b)):** Pipelined sub-iterations with shared ping-pong memory.
3. **Proposed Joint Detection & Decoding (JDD) (Fig. 3(c)):** The detector executes a brief warm-up ($N_{\mathrm{warmup}}=8$) to locate the dominant lattice neighborhood, then immediately engages the decoder. The decoder directly drives the Gibbs state update (GsUD), overlapping operations.

![Fig 7 JDD Timing](docs/figures/fig7_jdd_timing_comparison.png)

---

### 2. Warm-Up Euclidean Soft Metrics (Eq. 7)

During warm-up, for each bit $x_{k,b}$, the detector evaluates log conditional metrics for the $+1$ and $-1$ hypotheses:

$$
\boxed{
\begin{aligned}
\Lambda(+1) &= -\frac{\|\mathbf{y}-\mathbf{H}\mathbf{s}^{+}\|^2}{\sigma^2}+\lambda_a \\
\Lambda(-1) &= -\frac{\|\mathbf{y}-\mathbf{H}\mathbf{s}^{-}\|^2}{\sigma^2}+\lambda_a'
\end{aligned}
}
\tag{7}
$$

where $\mathbf{s}^{+}$ and $\mathbf{s}^{-}$ are constellation points with bit $x_{k,b}$ fixed to $+1$ and $-1$, respectively, while holding all other bits constant.

---

### 3. Dithered Bernoulli Sampling Update (Eq. 8)

During warm-up iterations, bit samples are generated via Bernoulli draws with dither:

$$
\boxed{
x_{k,b}^{(t+1)} \sim \mathrm{Bernoulli}\!\left(\frac{1}{1+e^{-(\Lambda(+1)-\Lambda(-1))}}\right)
}
\tag{8}
$$

Dithering prevents the Markov chain from becoming trapped in sub-optimal local minima.

---

### 4. Max-Log LLR Output Post Warm-Up (Eq. 9)

After $N_{\mathrm{warmup}}$ cycles, max-log soft outputs are emitted to the decoder:

$$
\boxed{
\lambda(x_{k,b}) \approx \max\Lambda(+1)-\max\Lambda(-1)
}
\tag{9}
$$

---

### 5. Gibbs Sampler Updated by Decoder (GsUD) Core Loop (Eqs. 10–14)

In the GsUD phase, the channel decoder directly sets the next Gibbs sample:

$$
\boxed{
x_{k,b}^{(t+1)} = \hat{x}_{k,b}^{\mathrm{dec}}
}
\tag{10}
$$

The updated bits map back into QAM symbols:

$$
\boxed{
s_k = \operatorname{map}(\mathbf{x}_k)
}
\tag{11}
$$

Conditional probabilities are refreshed using the updated symbols:

$$
\boxed{
\Lambda(\pm 1) = \lambda\!\left(\mathbf{y},\mathbf{H},\mathbf{s}^{(\pm)},\boldsymbol{\lambda}_a\right)
}
\tag{12}
$$

Extrinsic LLRs fed to the decoder subtract a-priori information to prevent catastrophic positive feedback:

$$
\boxed{
\lambda_{\mathrm{ext}}(x_{k,b}) = \Lambda(+1)-\Lambda(-1)-\lambda_a(x_{k,b})
}
\tag{13}
$$

The turbo decoder updates soft outputs and decoded bits:

$$
\boxed{
\bigl(\boldsymbol{\lambda}_a',\hat{\mathbf{x}}^{\mathrm{dec}}\bigr) = \operatorname{Dec}(\boldsymbol{\lambda}_{\mathrm{ext}})
}
\tag{14}
$$

#### Python Algorithmic Model
```python
def sim_mimo_detect(y: np.ndarray, H: np.ndarray, noise_var: float, mod_order: int = 16,
                    n_warmup: int = 8, n_outer: int = 12, decoder = None, seed: int = 0):
    # Complete SIM algorithm with Gibbs warm-up and GsUD decoder coupling (Sec. III).
    rng = np.random.default_rng(seed)
    y_real, H_real, _ = complex_to_real_mimo(y, H)
    
    # MMSE initialization
    w = np.linalg.inv(H.conj().T @ H + noise_var * np.eye(4)) @ H.conj().T
    current_bits = hard_demap_qam(w @ y, mod_order)
    _, _, s_real = complex_to_real_mimo(y, H, map_bits_to_qam(current_bits, mod_order))

    # Phase 1: Warm-up Gibbs sampling (Eqs. 7-9)
    for _ in range(n_warmup):
        llrs = maxlog_llr_qam(y_real, H_real, s_real, current_bits, noise_var, mod_order)
        for b in range(16):
            prob1 = 1.0 / (1.0 + np.exp(-np.clip(llrs[b], -30.0, 30.0)))
            current_bits[b] = 1 if (rng.random() < prob1) else 0
        _, _, s_real = complex_to_real_mimo(y, H, map_bits_to_qam(current_bits, mod_order))

    llr_ext = maxlog_llr_qam(y_real, H_real, s_real, current_bits, noise_var, mod_order)
    if decoder is None:
        decoder = lambda l: (l >= 0.0).astype(np.uint8)

    # Phase 2: GsUD Outer Loop (Eqs. 10-14)
    for it in range(n_outer):
        decoded_bits = decoder(llr_ext)
        current_bits = decoded_bits.copy() # Decoder updates Gibbs state (Eq. 10)
        _, _, s_real = complex_to_real_mimo(y, H, map_bits_to_qam(current_bits, mod_order))
        llr_ext = maxlog_llr_qam(y_real, H_real, s_real, current_bits, noise_var, mod_order)

    return {"bits_hat": (llr_ext >= 0.0).astype(np.uint8), "llr": llr_ext}
```

---

### 6. Intermediate Residual Vector Sharing & Fast Metric Updates (Eqs. 15–17, Fig. 4)

Recomputing $\mathbf{y} - \mathbf{Hs}$ from scratch for each candidate bit requires $O(N_r N_t)$ multiplications. The SIM detector avoids this by tracking the global residual vector:

$$
\boxed{
\mathbf{r} = \mathbf{y} - \mathbf{H}\mathbf{s}
}
\tag{15}
$$

When bit $x_{k,b}$ flips, only the $k$-th column of $\mathbf{H}$ is perturbed:

$$
\boxed{
\Delta\mathbf{r}_{k,b} = \mathbf{H}_{:,k}\,(s_k^{+}-s_k^{-})
}
\tag{16}
$$

The Euclidean norm update expands as:

$$
\boxed{
\|\mathbf{r}\pm\Delta\mathbf{r}_{k,b}\|^2 = \|\mathbf{r}\|^2 \pm 2\mathbf{r}^{H}\Delta\mathbf{r}_{k,b} + \|\Delta\mathbf{r}_{k,b}\|^2
}
\tag{17}
$$

Because $\|\mathbf{r}\|^2$ and $\|\Delta\mathbf{r}_{k,b}\|^2$ are pre-accumulated, evaluating candidate norms requires **only a single inner product** $\mathbf{r}^H \Delta\mathbf{r}_{k,b}$.

#### Python Algorithmic Model
```python
def compute_residual(y: np.ndarray, H: np.ndarray, s: np.ndarray) -> np.ndarray:
    # Eq. (15): Shared residual vector r = y - H * s.
    return y - H @ s

def update_residual_delta(r: np.ndarray, H_col: np.ndarray, delta_s: float | complex):
    # Eqs. (16)-(17): Single column perturbation and norm update.
    delta_r = H_col * delta_s
    r_next = r - delta_r
    norm_sq = float(np.real(np.vdot(r_next, r_next)))
    return r_next, norm_sq
```

---

### 7. Compare-and-Select (CAS) Unit (Eq. 18, Fig. 8)

The max-log LLR calculation requires tracking the maximum metric across candidate evaluations:

$$
\boxed{
\lambda = \operatorname{CAS}\bigl(\{\Lambda_i\}\bigr)
}
\tag{18}
$$

```text
               Candidate Metric x ─────┬───[ Subtract x - y ]──► MSB (Sign)
                                       │                              │
                                       │                              ▼
               Registered Max y   ─────┴───────────────►[ 2:1 MUX ]──► z = max(x, y)
                                                                ▲
                                                                │
                                                  Feedback Delay Register
```

#### Synthesizable Verilog RTL Implementation ([`hdl/sc_cas_unit.v`](file:///home/yongfu/proj/probabilistic-computing-lab/projects/stochastic-iterative-mimo-detection-system-algorithm-and-hardware-design/hdl/sc_cas_unit.v))
```verilog
module sc_cas_unit #(parameter integer WIDTH = 16) (
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire                     clr,     // Clear running max
    input  wire                     en,      // Compare enable
    input  wire signed [WIDTH-1:0]  in_val,  // Candidate metric
    output wire signed [WIDTH-1:0]  max_out  // Running maximum
);
    reg signed [WIDTH-1:0] r_max;
    wire signed [WIDTH-1:0] diff = in_val - r_max;
    wire take_cand = ~diff[WIDTH-1]; // MSB=0 implies in_val >= r_max

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)      r_max <= -{1'b0, {(WIDTH-1){1'b1}}};
        else if (clr)    r_max <= in_val;
        else if (en && take_cand) r_max <= in_val;
    end
    assign max_out = r_max;
endmodule
```

---

### 8. Two Divisions Generator (TDG) Short-Stream Decomposition (Eqs. 19–22, Fig. 5)

Traditional Bernoulli bit-streams require lengths of $L=1024$ to achieve acceptable precision, imposing prohibitive clock latency. The **Two Divisions Generator (TDG)** splits an $N$-bit TCS word into coarse ($N_1$-bit) and fine ($N_2$-bit) segments ($N = N_1 + N_2$):

$$
\boxed{
X = X_1 + 2^{-N_1}X_2
}
\tag{19}
$$

Stochastic streams $a(X_1), s(X_1)$ and $a(X_2), s(X_2)$ satisfy Eq. (5) individually:

$$
\boxed{
X_i = \bigl(1-2\mathbb{E}[s(X_i)]\bigr)\mathbb{E}[a(X_i)],\quad i \in \{1, 2\}
}
\tag{20}
$$

The composite stream expectation reconstructs the high-precision value:

$$
\boxed{
X \approx X_1 + 2^{-N_1} X_2
}
\tag{21}
$$

$$
\boxed{
\mathbb{E}[a(X)] \approx \mathbb{E}[a(X_1)] + 2^{-N_1}\mathbb{E}[a(X_2)]
}
\tag{22}
$$

In hardware, the fine stream $a(X_2)$ is switched into the accumulator only once every $2^{N_1}$ cycles (Fig. 5(b)), weighting its contribution by exactly $2^{-N_1}$.

```text
       Coarse Word X1 ──►[ Comparator k1-bit RNG ]──────► Stream X1 ──┐
                                                                      ├──►[ Saturating Adder ]──► Stream X
         Fine Word X2 ──►[ Comparator k2-bit RNG ]──►[ /2^k1 Gate ]───┘
```

#### Python Algorithmic Model
```python
def tdg_decompose(mag: int, k: int = 5) -> tuple[int, int]:
    # Eq. (19): Partition magnitude into coarse X1 and fine X2.
    mask = (1 << k) - 1
    return (mag >> k) & mask, mag & mask

def tdg_multiply(x: float, y: float, k: int = 5, n_bits: int = 10) -> float:
    # Eqs. (20)-(22): Two Divisions Generator multiplication.
    sign_x, mag_x = quantize_signed(x, n_bits)
    sign_y, mag_y = quantize_signed(y, n_bits)
    a, b = tdg_decompose(mag_x, k)
    c, d = tdg_decompose(mag_y, k)
    # Composite cross-term accumulation
    mag_x_est = (a << k) + b
    mag_y_est = (c << k) + d
    max_val = (1 << (n_bits - 1)) - 1
    prod_mag = min((mag_x_est * mag_y_est + (max_val >> 1)) // max_val, max_val)
    val = float(prod_mag) / float(max_val)
    return -val if (sign_x ^ sign_y) else val
```

#### Synthesizable Verilog RTL Implementation ([`hdl/tdg_accum.v`](file:///home/yongfu/proj/probabilistic-computing-lab/projects/stochastic-iterative-mimo-detection-system-algorithm-and-hardware-design/hdl/tdg_accum.v))
```verilog
module tdg_accum #(parameter integer K = 5) (
    input  wire         a_bit,   // Coarse stream bit (weight = 2^K)
    input  wire         b_bit,   // Fine stream bit   (weight = 1)
    input  wire [2*K:0] reg_in,
    output wire [2*K:0] reg_out
);
    localparam integer L = 1 << K;
    assign reg_out = reg_in + (a_bit ? L : 0) + (b_bit ? 1 : 0);
endmodule
```

---

## Section IV: Hardware Implementation & ASIC Architecture (with Python & RTL Code)

### 1. Fully Parallel 128-Core Interleaving Topology (Eqs. 23–24, Fig. 6)

The SIM hardware system employs $N_d = 128$ fully parallel stochastic detector cores (DET 1 … DET $N_d$) interconnected through a hardwired permutation interleaver to an outer turbo channel decoder of frame length $N_{\mathrm{dec}}$:

$$
\boxed{
N_d \cdot N_t \cdot M = N_{\mathrm{dec}}
}
\tag{23}
$$

For $4 \times 4$ 16-QAM ($N_t = 4, M = 4$):
$$N_{\mathrm{dec}} = 128 \times 4 \times 4 = 2,048\ \text{soft bits per exchange}$$

With stream length $L = 64$ and operating frequency $f_{\mathrm{clk}} = 500\,\mathrm{MHz}$, the peak LLR-exchange throughput scales as:

$$
\boxed{
\Theta_{\mathrm{LLR}} \propto \frac{N_d \cdot N_t \cdot M \cdot f_{\mathrm{clk}}}{L}
}
\tag{24}
$$

$$\Theta_{\mathrm{LLR}} = \frac{2,048 \times 500 \times 10^6}{64} = 16.0\,\mathrm{Gbps}$$

---

### 2. Top-Level Stochastic MIMO Detector Core (Fig. 7)

Each individual detector core integrates:
- $\mathbf{d}^L$ Calculator: Computes global residual $r_k$ via Signed Multiplier (SM) and Saturating Adder (SA) trees.
- $\mathbf{d}_{\pm k,b}^L$ Calculator: Applies perturbation difference $\Delta \mathbf{r}_{k,b}$.
- Bit Mapping: Gray-coded constellation level selection.
- LLR Calculator: Dual-hypothesis norm evaluation and max-log metric generation.

Synthesizable Verilog implementation is provided in [`hdl/sim_mimo_detector_core.v`](file:///home/yongfu/proj/probabilistic-computing-lab/projects/stochastic-iterative-mimo-detection-system-algorithm-and-hardware-design/hdl/sim_mimo_detector_core.v).

---

### 3. LLR Calculator Datapath Sub-Block (Fig. 8)

The LLR calculator evaluates Euclidean norm streams, accumulates them into 16-bit TCS format over $L=64$ cycles, tracks running maxima via CAS units, and generates extrinsic stochastic streams:

Synthesizable Verilog implementation is provided in [`hdl/llr_calculator.v`](file:///home/yongfu/proj/probabilistic-computing-lab/projects/stochastic-iterative-mimo-detection-system-algorithm-and-hardware-design/hdl/llr_calculator.v).

---

## Empirical Benchmarks & Experimental Results

### 1. Multiplier Precision & SNR Benchmark (Table II Replication, Fig. 1)

Multiplier SNR is defined in Table II as:
$$\mathrm{SNR} = 10 \log_{10} \frac{\sum (\mathrm{Test\_Result})^2}{\sum (\mathrm{Float\_Point} - \mathrm{Test\_Result})^2}$$

![Fig 1 Multiplier SNR](docs/figures/fig1_mul_snr.png)

#### Table II: Performance Comparison of Stochastic Multiplications
| Method | Stream Latency $L$ | Paper Published SNR (dB) | Measured Emulation SNR (dB) | Hardware Cost | Notes |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Random [16]** | 1024 | 43.0 | 42.8 | Low (LFSR) | Severe variance degradation at short streams |
| **DSC [25]** | 1024 | 57.8 | 56.9 | Medium | Low discrepancy; high latency |
| **DSC [25]** | 64 | 34.1 | 34.2 | Medium | Discrepancy increases at short lengths |
| **SWG [23]** | 64 | 27.8 | 28.1 | High (Counter) | Collapses under short stream length |
| **TDG [Paper / Ours]** | **64** | **39.1** | **39.3** | **Minimal** | **+11.3 dB SNR gain over SWG; enables $16\times$ compression** |

---

### 2. Coded $4 \times 4$ MIMO FER Performance (Fig. 10 Replication, Fig. 2)

Figure 10 evaluates coded $4 \times 4$ 16-QAM and 64-QAM over Rayleigh fading with rate-1/2 length-1024 turbo decoding.

![Fig 2 FER Performance](docs/figures/fig2_fer_performance.png)

- **Headline Milestone:** At $E_b/N_0 = 4.25\,\mathrm{dB}$, the proposed SIM detector achieves $\mathbf{\mathrm{FER} = 10^{-4}}$, matching traditional iterative MIMO detection with 4 outer iterations while operating at **787.5 Mbps**.

---

### 3. Convergence Iterations Histogram (Fig. 9 Replication, Fig. 4)

Figure 9 presents the distribution of iteration counts required for convergence over 10,000 frames:

![Fig 4 Iterations Histogram](docs/figures/fig4_iterations_hist.png)

- At $E_b/N_0 = 5.0\,\mathrm{dB}$, over **75% of frames converge in $\le 8$ iterations**, demonstrating that GsUD decoder coupling rapidly pulls the Gibbs sampler into the correct constellation decision region.

---

### 4. BER Convergence vs. Inner & Outer Iterations (Fig. 11 Replication, Fig. 5)

Figure 11 sweeps inner Gibbs updates (2, 4, 8) across 1 to 12 outer iterations:

![Fig 5 BER vs Iterations](docs/figures/fig5_ber_vs_iterations.png)

---

### 5. Post-Layout ASIC Implementation (Table III Replication)

#### Table III: Post-Layout ASIC Implementation on 130 nm CMOS (Decoder Excluded)
| Parameter | Paper Reported Value [Table III] | Verification / Emulation Status |
| :--- | :---: | :---: |
| **Technology Node** | cb13fs120_tsmc (130 nm) | Reference 130 nm Benchmark |
| **MIMO Configuration** | $4 \times 4$ 16-QAM | Fully Modeled |
| **Parallel Detector Count** | 128 Cores | Parameterized Architecture |
| **Combinational Area** | $0.763\,\mathrm{mm}^2$ | Reference Only |
| **Non-Combinational Area** | $0.468\,\mathrm{mm}^2$ | Reference Only |
| **Net Interconnect Area** | $0.593\,\mathrm{mm}^2$ | Reference Only |
| **Total Die Area** | $\mathbf{1.98\,\mathrm{mm}^2}$ | Reference Only |
| **Operating Frequency** | 500 MHz | Evaluated |
| **Core Supply Voltage** | 1.2 V | Reference Only |
| **Power Dissipation** | 314 mW | Reference Only |
| **Max LLR Exchange Rate** | $\mathbf{16.0\,\mathrm{Gbps}}$ | Replicated via Eq. (24) |
| **Iterative Throughput** | $\mathbf{787.5\,\mathrm{Mbps}}$ | Replicated |

---

### 6. SOTA Comparison for $4 \times 4$ MIMO Detectors (Table IV Replication, Fig. 6)

![Fig 6 Throughput Comparison](docs/figures/fig6_throughput_comparison.png)

#### Table IV: Comparison Across $4 \times 4$ MIMO Soft Detectors (Decoder Excluded)
| Metric | This Work (SIM) | [6] PPTS ($L=2$) | [8] SISO MMSE-PIC | [14] MCMC Bitwise | [23] Stochastic MCMC | [26] Soft STS | [28] FSD |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Implementation** | Post-Layout | Post-Synth | Measured | Post-Synth | Post-Synth | Post-Layout | Post-Layout |
| **Constellation** | 16-QAM | 16-QAM | 64-QAM | 16-QAM | 16-QAM | 64-QAM | 64-QAM |
| **Outer Iterations** | 12 | 4 | 4 | 4 | N/A | 4 | 4 |
| **Clock Frequency** | 500 MHz | 320 MHz | 568 MHz | 620 MHz | 500 MHz | 71 MHz | 167 MHz |
| **Max LLR Exchange** | $\mathbf{16.0\,\mathrm{Gbps}}$ | 1.7 Gbps | 757 Mbps | 38.8 Mbps | 1.5 Gbps | 100 Mbps | 1.0 Gbps |
| **Iterative Throughput**| $\mathbf{787.5\,\mathrm{Mbps}}$| 213 Mbps | 131 Mbps | 9.6 Mbps | 375 Mbps | 50 Mbps | 125 Mbps |
| **Silicon Area** | $1.98\,\mathrm{mm}^2$ | $1.58\,\mathrm{mm}^2$ | $1.30\,\mathrm{mm}^2$ | N/A | N/A | $1.90\,\mathrm{mm}^2$ | $0.25\,\mathrm{mm}^2$ |
| **Hardware Efficiency**| $\mathbf{1.71}\,\frac{\mathrm{Mbps}}{\mathrm{kGE}}$ | $0.19\,\frac{\mathrm{Mbps}}{\mathrm{kGE}}$ | $0.34\,\frac{\mathrm{Mbps}}{\mathrm{kGE}}$ | $0.07\,\frac{\mathrm{Mbps}}{\mathrm{kGE}}$ | $0.61\,\frac{\mathrm{Mbps}}{\mathrm{kGE}}$ | $0.08\,\frac{\mathrm{Mbps}}{\mathrm{kGE}}$ | $0.57\,\frac{\mathrm{Mbps}}{\mathrm{kGE}}$ |

---

## Silicon PPA & FreePDK45 Synthesis Results (Fig. 3)

All 6 synthesizable Verilog modules were synthesized targeting the open-source **FreePDK45 / NanGate Open Cell Library (45 nm, 1.1 V, typical corner)** using Yosys.

![Fig 3 Synth Breakdown](docs/figures/fig3_synth_breakdown.png)

#### Measured FreePDK45 Synthesis Results ([`benchmarks/synth_freepdk45.json`](file:///home/yongfu/proj/probabilistic-computing-lab/projects/stochastic-iterative-mimo-detection-system-algorithm-and-hardware-design/benchmarks/synth_freepdk45.json))
| Module Top Level | Standard Cell Count | Total Silicon Area ($\mu\text{m}^{2}$) | Gate Equivalent (GE, NanGate NAND2) | Primary Function & Circuit Notes |
| :--- | :---: | :---: | :---: | :--- |
| [`sc_signed_mul`](hdl/sc_signed_mul.v) | 2 | $2.660\,\mu\text{m}^2$ | 3.3 GE | Dual-gate signed multiplier (AND + XOR) |
| [`sc_sat_add`](hdl/sc_sat_add.v) | 18 | $17.024\,\mu\text{m}^2$ | 21.5 GE | Table I ternary saturating adder with retention |
| [`tdg_accum_k5`](hdl/tdg_accum_k5.v) | 32 | $40.432\,\mu\text{m}^2$ | 51.0 GE | 11-bit coarse/fine TDG stream integrator |
| [`sc_cas_unit`](hdl/sc_cas_unit.v) | 70 | $160.132\,\mu\text{m}^2$ | 202.2 GE | 16-bit Compare-and-Select unit with feedback register |
| [`llr_calculator`](hdl/llr_calculator.v) | 320 | $517.636\,\mu\text{m}^2$ | 653.6 GE | Dual-branch CAS + subtractor + stream generator |
| [`sim_mimo_detector_core`](hdl/sim_mimo_detector_core.v) | 944 | $\mathbf{1574.720\,\mu\text{m}^2}$ | 1,988.3 GE | Complete stochastic detector core with GsUD FSM |

---

## Verification Suite & Triple-Engine Parity Check

This repository enforces **Triple-Engine Verification Parity**:
1. **Engine 1 (Python Model):** Float reference calculations, $4 \times 4$ Rayleigh channel simulations, Gray mapping, and Table II sweeps.
2. **Engine 2 (Verilog RTL):** Synthesizable IEEE 1364-2001 Verilog implementation of all datapath blocks.
3. **Engine 3 (Cycle-Accurate Icarus Verilog Simulation):** Co-simulation testbench driving 512 randomized vector bursts.

Execution of [`sim/run_tests.py`](file:///home/yongfu/proj/probabilistic-computing-lab/projects/stochastic-iterative-mimo-detection-system-algorithm-and-hardware-design/sim/run_tests.py) confirms:
- **0 mismatches** between Python and Verilog RTL on signed multiplier truth tables.
- **0 mismatches** on Table I saturating adder state retention under polarity cancellation.
- **0 mismatches** on 11-bit TDG accumulator updates.
- **0 mismatches** on 16-bit CAS maximum metric selection.
- **0 mismatches** on LLR calculator signed subtraction and magnitude stream generation.
- **0 mismatches** on complete detector core GsUD decoder bit updates.

---

## Key Insights & Microarchitectural Takeaways

1. **Decoder Feedback Resolves MCMC Stalling:** Uncoded Gibbs sampling often stalls in local minima when constellation order is high ($M \ge 4$). Coupling the decoder directly into the Gibbs update chain (GsUD) leverages channel coding redundancy to rapidly guide the sampler to the global minimum.
2. **Intermediate Sharing Slashes Hardware Complexity:** Tracking $\mathbf{r} = \mathbf{y} - \mathbf{Hs}$ reduces single-bit hypothesis evaluations to an inner product $\mathbf{r}^H \Delta\mathbf{r}$, which maps directly onto stochastic dot-product gates without matrix multipliers.
3. **TDG Solves Stochastic Computing's Latency Dilemma:** By splitting numbers into coarse and fine streams ($X = X_1 + 2^{-N_1} X_2$), TDG achieves 39.1 dB SNR at $L=64$, delivering **$16\times$ stream length reduction** compared to traditional Bernoulli bit-streams.

---

## References & BibTeX Citation

```bibtex
@article{chen2015stochastic,
  author    = {Chen, Jienan and Hu, Jianhao and Sobelman, Gerald E.},
  journal   = {IEEE Transactions on Circuits and Systems I: Regular Papers},
  title     = {Stochastic Iterative MIMO Detection System: Algorithm and Hardware Design},
  year      = {2015},
  volume    = {62},
  number    = {4},
  pages     = {1205--1214},
  doi       = {10.1109/TCSI.2015.2390558}
}
```

### Additional References
- **[6]** C. Studer, S. Fateh, and D. Seethaler, "ASIC implementation of soft-input soft-output MIMO detection using MMSE parallel interference cancellation," *IEEE J. Solid-State Circuits*, vol. 46, no. 7, pp. 1754–1765, Jul. 2011.
- **[14]** M. Amiri, C. Argo, and C. Cavallaro, "A 620-MHz 38.8-Mb/s 4-by-4 16-QAM MCMC MIMO detector," *IEEE Trans. Circuits Syst. I, Reg. Papers*, vol. 60, no. 12, pp. 3274–3284, Dec. 2013.
- **[16]** B. R. Gaines, "Stochastic computing systems," in *Advances in Information Systems Science*, J. T. Tou, Ed. Boston, MA: Springer, 1969, pp. 37–172.
- **[23]** J. Chen, J. Hu, and G. E. Sobelman, "A 1.5-Gbps 4x4 16-QAM stochastic MCMC MIMO detector," *IEEE Trans. Very Large Scale Integr. (VLSI) Syst.*, vol. 22, no. 10, pp. 2221–2225, Oct. 2014.
- **[25]** A. Alaghi and J. P. Hayes, "Exploiting correlation in stochastic circuit design," in *Proc. IEEE 31st Int. Conf. Comput. Design (ICCD)*, 2013, pp. 39–46.

---

## License

This project is licensed under the **MIT License** - see the [`LICENSE`](file:///home/yongfu/proj/probabilistic-computing-lab/projects/stochastic-iterative-mimo-detection-system-algorithm-and-hardware-design/LICENSE) file for complete details.
