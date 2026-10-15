#!/usr/bin/env python3
"""Comprehensive Verification Suite for Stochastic Iterative MIMO Detection System.

Validates:
1. Elementary stochastic computing gates (SM Fig. 2, SA Table I)
2. Gray QAM mapping / demapping for 16-QAM & 64-QAM (Eq. 11)
3. Rayleigh MIMO channel and real-valued equivalent decomposition (Eq. 1)
4. Two Divisions Generator (TDG) short-stream SNR superiority (Table II, Eqs. 19-22)
5. Intermediate residual-vector sharing and fast metric updates (Eqs. 15-17)
6. Complete SIM detector with Gibbs warm-up and GsUD outer iteration loop (Eqs. 7-14)
7. Synthesizable Verilog RTL suite with 0 mismatches against Python reference in Icarus Verilog
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.qam import get_constellation, hard_demap_qam, map_bits_to_qam
from src.mimo_channel import (
    complex_to_real_mimo,
    compute_noise_var,
    generate_channel,
    mmse_detect,
    zf_detect,
)
from src.tdg import (
    dsc_multiply,
    random_sc_multiply,
    run_table2_benchmark,
    sc_sat_add_bits,
    sc_signed_mul_bits,
    snr_db,
    swg_multiply,
    tdg_multiply,
)
from src.sim_mimo import (
    compute_residual,
    maxlog_llr_qam,
    sim_mimo_detect,
    update_residual_delta,
)


def test_signed_mul_truth() -> None:
    # 1 * -1 = -1
    zm, zs = sc_signed_mul_bits(1, 0, 1, 1)
    assert zm == 1 and zs == 1, f"Expected 1, 1 but got {zm}, {zs}"
    # -1 * -1 = 1
    zm, zs = sc_signed_mul_bits(1, 1, 1, 1)
    assert zm == 1 and zs == 0, f"Expected 1, 0 but got {zm}, {zs}"
    # 0 * -1 = 0
    zm, zs = sc_signed_mul_bits(0, 0, 1, 1)
    assert zm == 0 and zs == 1, f"Expected 0, 1 but got {zm}, {zs}"


def test_sat_add_table() -> None:
    # (1, 1) -> 1, sat=1
    z, sat = sc_sat_add_bits(1, 1, 0)
    assert z == 1 and sat == 1
    # (-1, -1) -> -1, sat=-1
    z, sat = sc_sat_add_bits(-1, -1, 0)
    assert z == -1 and sat == -1
    # (1, -1) -> sat_prev, sat=0
    z, sat = sc_sat_add_bits(1, -1, 1)
    assert z == 1 and sat == 0
    z, sat = sc_sat_add_bits(1, -1, -1)
    assert z == -1 and sat == 0


def test_qam_roundtrip() -> None:
    rng = np.random.default_rng(123)
    # Test 16-QAM (4 bits/symbol * 4 symbols = 16 bits)
    bits16 = rng.integers(0, 2, size=16, dtype=np.uint8)
    syms16 = map_bits_to_qam(bits16, mod_order=16)
    demap16 = hard_demap_qam(syms16, mod_order=16)
    np.testing.assert_array_equal(bits16, demap16)

    # Test 64-QAM (6 bits/symbol * 4 symbols = 24 bits)
    bits64 = rng.integers(0, 2, size=24, dtype=np.uint8)
    syms64 = map_bits_to_qam(bits64, mod_order=64)
    demap64 = hard_demap_qam(syms64, mod_order=64)
    np.testing.assert_array_equal(bits64, demap64)


def test_channel_decomposition() -> None:
    rng = np.random.default_rng(42)
    H_c = generate_channel(n_r=4, n_t=4, rng=rng)
    tx_bits = rng.integers(0, 2, size=16, dtype=np.uint8)
    s_c = map_bits_to_qam(tx_bits, mod_order=16)
    noise_var = compute_noise_var(15.0, mod_order=16, code_rate=0.5, n_t=4)
    noise_c = rng.normal(0.0, np.sqrt(noise_var / 2.0), size=4) + 1j * rng.normal(0.0, np.sqrt(noise_var / 2.0), size=4)
    y_c = H_c @ s_c + noise_c

    y_r, H_r, s_r = complex_to_real_mimo(y_c, H_c, s_c)

    assert H_r.shape == (8, 8)
    assert len(y_r) == 8
    assert len(s_r) == 8

    # Verify linear equivalence
    noise_r = y_r - H_r @ s_r
    np.testing.assert_allclose(np.linalg.norm(noise_r), np.linalg.norm(noise_c), rtol=1e-5)


def test_tdg_table_ii() -> None:
    # Validate TDG achieves >35 dB SNR at L=64, beating Random and SWG
    results = run_table2_benchmark(n_trials=80, seed=42)
    assert results["TDG_64"]["measured_snr_db"] > 35.0, f"TDG SNR {results['TDG_64']['measured_snr_db']} dB lower than expected"
    assert results["TDG_64"]["measured_snr_db"] > results["SWG_64"]["measured_snr_db"], "TDG must beat SWG at L=64"


def test_residual_sharing() -> None:
    rng = np.random.default_rng(7)
    H = rng.standard_normal((8, 8))
    s = rng.choice([-3.0, -1.0, 1.0, 3.0], size=8) / np.sqrt(10.0)
    y = H @ s + 0.05 * rng.standard_normal(8)

    r = compute_residual(y, H, s)
    # Flip dimension 0
    delta_s = 2.0 / np.sqrt(10.0)
    r_new, norm_fast = update_residual_delta(r, H[:, 0], delta_s)
    s_new = s.copy()
    s_new[0] += delta_s
    norm_exact = np.dot(y - H @ s_new, y - H @ s_new)

    np.testing.assert_allclose(norm_fast, norm_exact, rtol=1e-6)


def test_mimo_sim_detector() -> None:
    rng = np.random.default_rng(2026)
    H_c = generate_channel(n_r=4, n_t=4, rng=rng)
    tx_bits = rng.integers(0, 2, size=16, dtype=np.uint8)
    s_c = map_bits_to_qam(tx_bits, mod_order=16)
    noise_var = 0.001
    noise_c = rng.normal(0.0, np.sqrt(noise_var / 2.0), size=4) + 1j * rng.normal(0.0, np.sqrt(noise_var / 2.0), size=4)
    y_c = H_c @ s_c + noise_c

    # Ideal decoder oracle for testing GsUD coupling
    def mock_decoder(llrs: np.ndarray) -> np.ndarray:
        return (llrs >= 0.0).astype(np.uint8)

    det_out = sim_mimo_detect(
        y=y_c,
        H=H_c,
        noise_var=noise_var,
        mod_order=16,
        n_warmup=8,
        n_outer=12,
        decoder=mock_decoder,
        seed=42,
    )

    detected = det_out["bits_hat"]
    bit_errors = int(np.sum(detected != tx_bits))
    assert bit_errors == 0, f"Expected 0 bit errors at high SNR, got {bit_errors}"


def test_icarus() -> None:
    subprocess.check_call(["bash", str(ROOT / "sim" / "run_icarus.sh")])
    tb_text = (ROOT / "sim" / "tb_counts.txt").read_text()
    assert "mismatches=0" in tb_text, f"Icarus mismatches detected: {tb_text}"


def main() -> None:
    print("Running Python algorithmic unit tests...")
    test_signed_mul_truth()
    print("  [PASS] Signed multiplier truth table")
    test_sat_add_table()
    print("  [PASS] Saturating adder Table I truth table")
    test_qam_roundtrip()
    print("  [PASS] 16-QAM and 64-QAM Gray mapping roundtrip")
    test_channel_decomposition()
    print("  [PASS] Complex Rayleigh channel and equivalent real decomposition")
    test_tdg_table_ii()
    print("  [PASS] Two Divisions Generator (TDG) Table II SNR verification")
    test_residual_sharing()
    print("  [PASS] Intermediate residual sharing (Eqs. 15-17)")
    test_mimo_sim_detector()
    print("  [PASS] Complete SIM detector Gibbs warm-up and GsUD outer loop")
    print("Running cycle-accurate Icarus Verilog hardware simulation...")
    test_icarus()
    print("  [PASS] Synthesizable Verilog RTL suite parity check (0 mismatches)")
    print("\nALL VERIFICATION TESTS COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    main()
