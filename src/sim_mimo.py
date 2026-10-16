"""Stochastic Iterative MIMO (SIM) Detection System — Chen et al. IEEE TCAS-I 2015.

Implements:
- MIMO system model (Eq. 1) & LLR metrics (Eq. 2)
- Intermediate residual vector sharing (Eqs. 15-17): r = y - H*s
- Gibbs sampler warm-up with Bernoulli sampling (Eqs. 7-9)
- GsUD (Gibbs Sampler Updated by Decoder) loop (Eqs. 10-14)
- Extrinsic LLR computation & soft output feedback (Eq. 13)
- Real equivalent 4x4 16-QAM and 64-QAM SIM detection
"""

from __future__ import annotations

from typing import Callable
import numpy as np

from .mimo_channel import complex_to_real_mimo, generate_channel
from .qam import get_constellation, hard_demap_qam, map_bits_to_qam
from .tdg import (
    dsc_multiply,
    random_sc_multiply,
    sc_sat_add_bits,
    sc_signed_mul_bits,
    snr_db,
    swg_multiply,
    tdg_multiply,
)


def compute_residual(y: np.ndarray, H: np.ndarray, s: np.ndarray) -> np.ndarray:
    """Eq. (15): Shared residual vector r = y - H * s."""
    return y - H @ s


def update_residual_delta(
    r: np.ndarray, H_col: np.ndarray, delta_s: float | complex
) -> tuple[np.ndarray, float]:
    """Eqs. (16)-(17): Compute delta_r and fast norm update when symbol changes by delta_s.
    
    delta_r = H_col * delta_s
    ||r + delta_r||^2 = ||r||^2 + 2 * Re{r^H * delta_r} + ||delta_r||^2
    """
    delta_r = H_col * delta_s
    r_next = r - delta_r
    norm_sq = float(np.real(np.vdot(r_next, r_next)))
    return r_next, norm_sq


def maxlog_llr_qam(
    y_real: np.ndarray,
    H_real: np.ndarray,
    s_real: np.ndarray,
    current_bits: np.ndarray,
    noise_var: float,
    mod_order: int = 16,
) -> np.ndarray:
    """Compute max-log LLRs for all bits using residual sharing (Eqs. 15-18).
    
    For each bit b in the transmission, evaluate distance metric when b=0 vs b=1.
    Uses Eq. (17) perturbation around current residual r = y - H*s.
    """
    total_bits = len(current_bits)
    llrs = np.zeros(total_bits, dtype=np.float64)
    r = compute_residual(y_real, H_real, s_real)
    norm_r_sq = float(np.dot(r, r))

    # Bit positions per real dimension
    bits_per_real_dim = int(np.log2(mod_order)) // 2  # 2 for 16-QAM, 3 for 64-QAM
    dim_count = len(s_real)

    # For each real dimension
    n_t = dim_count // 2
    for dim in range(dim_count):
        h_col = H_real[:, dim]
        current_val = s_real[dim]
        is_imag = (dim >= n_t)
        ant_idx = dim - n_t if is_imag else dim

        # Evaluate candidate points along this PAM dimension
        for b in range(bits_per_real_dim):
            bit_idx = ant_idx * (2 * bits_per_real_dim) + (bits_per_real_dim if is_imag else 0) + b
            # Test flipping bit bit_idx: find best symbol with bit=1 and bit=0
            d0_min = 1e9
            d1_min = 1e9

            # Scale factor for PAM
            scale = 1.0 / np.sqrt(10.0) if mod_order == 16 else 1.0 / np.sqrt(42.0)
            pam_pts = np.array([-3.0, -1.0, 1.0, 3.0]) * scale if mod_order == 16 else np.array([-7.0, -5.0, -3.0, -1.0, 1.0, 3.0, 5.0, 7.0]) * scale
            
            # Map pam pts to bits
            for pt in pam_pts:
                delta_s = pt - current_val
                delta_r = h_col * delta_s
                metric = norm_r_sq - 2.0 * np.dot(r, delta_r) + np.dot(delta_r, delta_r)

                # Determine bit value at position b for this PAM point
                if mod_order == 16:
                    # Gray mapping bit values for 2-PAM
                    bit_val = 1 if ((b == 0 and pt > 0) or (b == 1 and (abs(pt) < 2.0 * scale))) else 0
                else:
                    bit_val = 1 if pt > 0 else 0

                if bit_val == 1:
                    d1_min = min(d1_min, metric)
                else:
                    d0_min = min(d0_min, metric)

            # LLR: ln P(b=1) / P(b=0) approx (d0_min - d1_min) / noise_var
            llrs[bit_idx] = (d0_min - d1_min) / (noise_var + 1e-12)

    return llrs


def sim_mimo_detect(
    y: np.ndarray,
    H: np.ndarray,
    noise_var: float,
    mod_order: int = 16,
    n_warmup: int = 8,
    n_outer: int = 12,
    decoder: Callable[[np.ndarray], np.ndarray] | None = None,
    init_bits: np.ndarray | None = None,
    seed: int = 0,
    confidence_thresh: float = 6.0,
    early_stop_stability: int = 2,
) -> dict[str, np.ndarray | int]:
    """Full Stochastic Iterative MIMO (SIM) detector algorithm (Sec. III).
    
    1. Warm-Up Processing (Sec. III-B.1, Eqs. 7-9):
       Runs n_warmup Gibbs iterations with dithered Bernoulli sampling.
    2. GsUD Processing (Sec. III-B.2, Eqs. 10-14):
       Gibbs sampler updated directly by decoded bits from channel decoder.
    """
    rng = np.random.default_rng(seed)
    n_r, n_t = H.shape
    bits_per_sym = int(np.log2(mod_order))
    total_bits = n_t * bits_per_sym

    # Real equivalent decomposition
    y_real, H_real, _ = complex_to_real_mimo(y, H)

    # Initial state: from MMSE initialization (or passed init_bits)
    if init_bits is not None:
        current_bits = np.asarray(init_bits, dtype=np.uint8).copy()
    else:
        # MMSE linear filter initialization
        w = np.linalg.inv(H.conj().T @ H + noise_var * np.eye(n_t)) @ H.conj().T
        s_mmse = w @ y
        current_bits = hard_demap_qam(s_mmse, mod_order)

    s_complex = map_bits_to_qam(current_bits, mod_order)
    _, _, s_real = complex_to_real_mimo(y, H, s_complex)

    # 1. Warm-up processing (Eqs. 7-8)
    for _ in range(n_warmup):
        llrs = maxlog_llr_qam(y_real, H_real, s_real, current_bits, noise_var, mod_order)
        # Gibbs Bernoulli update for each bit (Eq. 8)
        for b in range(total_bits):
            prob1 = 1.0 / (1.0 + np.exp(-np.clip(llrs[b], -30.0, 30.0)))
            # Dither to avoid latching into local minima
            dither = rng.normal(0.0, 0.05)
            sample_prob = float(np.clip(prob1 + dither, 0.01, 0.99))
            current_bits[b] = 1 if (rng.random() < sample_prob) else 0

        # Update symbol representation
        s_complex = map_bits_to_qam(current_bits, mod_order)
        _, _, s_real = complex_to_real_mimo(y, H, s_complex)

    # Extrinsic LLR after warm-up (Eq. 9)
    llr_ext = maxlog_llr_qam(y_real, H_real, s_real, current_bits, noise_var, mod_order)

    # Default channel decoder: soft threshold MAP decision
    if decoder is None:
        def default_decoder(llr_in: np.ndarray) -> np.ndarray:
            return (llr_in >= 0.0).astype(np.uint8)
        decoder = default_decoder

    # 2. GsUD Outer Iterations (Eqs. 10-14)
    iterations_used = n_warmup
    prev_bits = current_bits.copy()
    stable_count = 0
    for it in range(n_outer):
        iterations_used += 1
        # Channel decoder updates hard bits (Eq. 10)
        decoded_bits = decoder(llr_ext)
        if np.array_equal(decoded_bits, prev_bits):
            stable_count += 1
        else:
            stable_count = 0
        prev_bits = decoded_bits.copy()
        current_bits = decoded_bits.copy()

        # Update QAM symbols (Eq. 11)
        s_complex = map_bits_to_qam(current_bits, mod_order)
        _, _, s_real = complex_to_real_mimo(y, H, s_complex)

        # Recompute extrinsic LLR for next loop (Eqs. 12-13)
        llr_ext = maxlog_llr_qam(y_real, H_real, s_real, current_bits, noise_var, mod_order)

        # Early termination checks
        if early_stop_stability > 0 and stable_count >= early_stop_stability and np.mean(np.abs(llr_ext)) >= confidence_thresh:
            break
        if np.all(np.abs(llr_ext) > 15.0):
            break

    final_bits = (llr_ext >= 0.0).astype(np.uint8)
    return {
        "bits_hat": final_bits,
        "llr": llr_ext,
        "iterations_used": iterations_used,
        "symbols_hat": map_bits_to_qam(final_bits, mod_order),
    }


def traditional_sc_multiply(x: float, y: float, length: int = 64, seed: int = 0) -> float:
    """Compatibility alias for traditional Bernoulli stochastic multiplication."""
    return random_sc_multiply(x, y, length=length, seed=seed)


def sc_signed_mul(a_mag: int, a_sign: int, b_mag: int, b_sign: int) -> tuple[int, int]:
    """Compatibility alias for sc_signed_mul_bits."""
    return sc_signed_mul_bits(a_mag, a_sign, b_mag, b_sign)


def gibbs_mimo_detect(
    y: np.ndarray,
    H: np.ndarray,
    noise_var: float,
    n_warmup: int = 8,
    n_outer: int = 12,
    decoder: Callable[[np.ndarray], np.ndarray] | None = None,
    seed: int = 0,
) -> dict:
    """Compatibility wrapper for real BPSK / general SIM MIMO detection."""
    if np.iscomplexobj(y) or np.iscomplexobj(H):
        return sim_mimo_detect(
            y, H, noise_var, mod_order=16, n_warmup=n_warmup, n_outer=n_outer, decoder=decoder, seed=seed
        )
    # Real 2x2 BPSK mode
    rng = np.random.default_rng(seed)
    nt = H.shape[1]
    s = rng.choice([-1.0, 1.0], size=nt)
    if decoder is None:
        decoder = lambda llr: np.where(llr >= 0, 1.0, -1.0)

    for _ in range(n_warmup):
        for i in range(nt):
            # Distance metrics
            s0, s1 = s.copy(), s.copy()
            s0[i], s1[i] = -1.0, 1.0
            d0 = np.sum((y - H @ s0) ** 2)
            d1 = np.sum((y - H @ s1) ** 2)
            llr = (d0 - d1) / (noise_var + 1e-12)
            p1 = 1.0 / (1.0 + np.exp(-np.clip(llr, -30.0, 30.0)))
            s[i] = 1.0 if (rng.random() < p1) else -1.0

    # GsUD loop
    for _ in range(n_outer):
        s0, s1 = s.copy(), s.copy()
        llrs = np.zeros(nt)
        for i in range(nt):
            s0_i, s1_i = s.copy(), s.copy()
            s0_i[i], s1_i[i] = -1.0, 1.0
            d0 = np.sum((y - H @ s0_i) ** 2)
            d1 = np.sum((y - H @ s1_i) ** 2)
            llrs[i] = (d0 - d1) / (noise_var + 1e-12)
        s = decoder(llrs)

    return {"s_hat": s, "llr": llrs, "s_final": s}


def tdg_multiply_stream(x: float, y: float, k: int = 5) -> float:
    """Compatibility alias for tdg_multiply."""
    return tdg_multiply(x, y, k=k)


def simulate_ber(
    snr_list: list[float],
    n_tx: int = 2,
    n_frames: int = 200,
    n_warmup: int = 8,
    n_outer: int = 12,
    seed: int = 0,
) -> list[dict[str, float]]:
    """Simulate uncoded BER vs SNR for SIM detection against Zero-Forcing (ZF)."""
    rng = np.random.default_rng(seed)
    results = []
    for snr_db_val in snr_list:
        noise_var = 10.0 ** (-snr_db_val / 10.0)
        err_sim = 0
        err_zf = 0
        total_bits = n_frames * n_tx

        for _ in range(n_frames):
            H = rng.normal(0.0, 1.0 / np.sqrt(2.0), size=(n_tx, n_tx))
            s = rng.choice([-1.0, 1.0], size=n_tx)
            n = rng.normal(0.0, np.sqrt(noise_var), size=n_tx)
            y = H @ s + n

            # SIM Gibbs detection
            det_sim = gibbs_mimo_detect(y, H, noise_var, n_warmup=n_warmup, n_outer=n_outer, seed=int(rng.integers(0, 100000)))
            s_hat_sim = det_sim["s_hat"]
            err_sim += int(np.sum(s_hat_sim != s))

            # ZF detection
            s_hat_zf = np.sign(np.linalg.pinv(H) @ y)
            s_hat_zf[s_hat_zf == 0] = 1.0
            err_zf += int(np.sum(s_hat_zf != s))

        results.append({
            "snr_db": float(snr_db_val),
            "ber_sim": float(err_sim / total_bits),
            "ber_zf": float(err_zf / total_bits),
        })

    return results

