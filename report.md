# Implementation Report — Chen et al. TCAS-I 2015 SIM MIMO

## Scope lock

| Item | Status |
| :--- | :--- |
| TDG short-stream representation / mul | Implemented |
| Signed SC mul + Table I sat-add | Implemented (Python + HDL) |
| Gibbs warm-up + GsUD detector | Implemented (2×2 real BPSK) |
| Table II-style mul SNR campaign | Measured |
| 128-parallel 4×4 16-QAM ASIC | **REFERENCE ONLY** (Tables III–IV) |
| Full FER with LDPC/turbo | **REFERENCE ONLY** (Figs. 9–11) |
| FreePDK45 building blocks | Measured |

## Waivers

None for TDG/SC arithmetic and Gibbs GsUD core. Full ASIC/FER scope is paper silicon — labeled REFERENCE ONLY, not soft-waived kernels.

## DoD

D1–D7 satisfied via `src/sim_mimo.py`, HDL, Icarus 0 mism, `sim_campaign.json`, FreePDK45, plots, tests PASS.

## Key design learning

TDG is a short-latency high-precision partition of a 2k-bit TCS value into two k-bit streams (Fig. 5); gate Table II trends on measured SNR vs float products. GsUD replaces conditional Gibbs draws with decoder hard bits after warm-up — even a hard-MAP decoder stub demonstrates the update rule.
