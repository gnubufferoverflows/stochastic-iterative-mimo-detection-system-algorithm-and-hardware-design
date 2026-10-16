# Compliance Report

**Paper:** J. Chen, J. Hu, and G. E. Sobelman, "Stochastic Iterative MIMO Detection System: Algorithm and Hardware Design," *IEEE TCAS-I*, vol. 62, no. 4, pp. 1205–1214, Apr. 2015. [doi:10.1109/TCSI.2015.2390558](https://doi.org/10.1109/TCSI.2015.2390558)

Status key: **Implemented** (follows the paper and is tested), **Interpreted** (the paper is ambiguous; the choice is documented in the README), **Not reproduced** (implemented, but the measured result disagrees with the paper), **Not implemented**, **Paper value** (quoted, not measured).

| Item | Status | Evidence |
| :--- | :--- | :--- |
| System model, Eq. (1), real-valued decomposition | Implemented | `src/mimo_channel.py`; test "Real decomposition" |
| TGn channel model C | Implemented | `TGnChannelC`; unit power, antenna and frequency correlation checked |
| Gray 16/64-QAM mapping, Eq. (11), Fig. 7 | Implemented | test "16/64-QAM Gray mapping" (includes Fig. 7 level order) |
| Signed streams, SM (Fig. 2), SA (Table I, Eq. 6) | Implemented | Python truth tables and RTL, 0 mismatches over 2000 random cycles |
| TDG, Eqs. (19)–(22), k1 = 6, k2 = 4, L = 64 | Implemented, Interpreted | Every 10-bit value is carried exactly by 16 windows (test "TDG windows"); fine-bit injection timing is a documented choice |
| Table II multiplier SNR | Not reproduced | Measured values are 3–14 dB below the paper for every method (see README) |
| Warm-up, Eqs. (7)–(9) | Implemented, Interpreted | Logistic R in Eq. (8); random initial sample |
| GsUD, Eqs. (10)–(14) | Implemented, Interpreted | λ₂ added after the CAS; extrinsic λ₁^e to the decoder |
| Parallel LLR, Eqs. (15)–(17) | Implemented | test "Parallel LLR distances" against brute force |
| CAS, Eq. (18) | Implemented | Python and RTL; RTL uses a signed compare (no overflow) |
| Turbo code, R = 1/2 K = 1024; R ≈ 5/6 K = 1952 | Implemented | Error-free at high SNR; FER 0.5% at 1.5 dB on BPSK AWGN (rate 1/2) |
| Fig. 10 FER (16/64-QAM) | Not reproduced | SIM with the paper's settings has FER = 1 at every SNR tested |
| Fig. 9 convergence histogram | Not reproduced | 0 of 200 frames converge at 6.8–7.2 dB with the paper's settings |
| Fig. 11 BER vs iterations | Not reproduced | SIM BER stays near 0.3 |
| Detector datapath, Figs. 4, 7, 8 | Implemented, Interpreted | `src/sc_detector.py` and `hdl/sim_mimo_detector_core.v`, bit-exact (0 mismatches, 30 iterations); norm unit is a documented reading of Fig. 8 |
| Stochastic turbo decoder [22] | Not implemented | Floating-point max-log BCJR used instead |
| 128-detector array, interleaver network (Fig. 6, Eqs. 23–24) | Not implemented | Single-vector core only |
| Synthesis | Implemented (generic) | Yosys generic gate counts in `benchmarks/synth_results.json`; no technology mapping, timing or power |
| Table III (1.98 mm², 500 MHz, 314 mW, 787.5 Mbps) | Paper value | The paper's Table III names library `cb13fs120_tsmc` while its text says SMIC 130 nm |
| Table IV comparison | Paper value | Transcribed in `scripts/run_campaign.py` and the README |
| 787.5 Mb/s throughput | Paper value | Not derivable from the stated parameters; 2048 coded bits / (20 × 65 cycles) at 500 MHz gives 787.7 Mb/s |

See the README sections "Interpretation choices" and "What does not match the paper" for details.
