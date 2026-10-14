"""Stochastic iterative MIMO (SIM) kernels — Chen et al. TCAS-I 2015.

Implements TDG short-stream representation (Sec. III-E / Fig. 5), signed SC
mul/add (Fig. 2, Table I), and Gibbs warm-up + GsUD detector loop for small
real MIMO. ASIC Tables III–IV and full 128×4×4 16-QAM FER are REFERENCE ONLY.
"""

from __future__ import annotations

from typing import Callable

import numpy as np


def snr_db(ref: np.ndarray, est: np.ndarray) -> float:
    ref = np.asarray(ref, dtype=np.float64).ravel()
    est = np.asarray(est, dtype=np.float64).ravel()
    err = ref - est
    num = float(np.dot(ref, ref)) + 1e-30
    den = float(np.dot(err, err)) + 1e-30
    return float(10.0 * np.log10(num / den))


def _quantize_pm1(x: float, n_bits: int) -> int:
    """Map x in [-1,1] to signed magnitude integer in [-(2^{n}-1), 2^{n}-1]."""
    scale = (1 << n_bits) - 1
    return int(np.clip(round(x * scale), -scale, scale))


def _dequantize_pm1(v: int, n_bits: int) -> float:
    scale = (1 << n_bits) - 1
    return float(v) / float(scale)


def tdg_split(v: int, k: int) -> tuple[int, int]:
    """Partition |v| into A·2^k + B (unsigned parts), keep sign separate."""
    mag = abs(v)
    mask = (1 << k) - 1
    return (mag >> k) & mask, mag & mask


def dsc_unary(ones: int, length: int) -> np.ndarray:
    ones = int(np.clip(ones, 0, length))
    s = np.zeros(length, dtype=np.uint8)
    s[:ones] = 1
    return s


def tdg_multiply(x: float, y: float, k: int = 5) -> float:
    """TDG-based high-accuracy mul (latency L=2^k), Chen Fig. 5 / Table II.

    Partition each 2k-bit magnitude into (A,B), form z=(A·2^k+B)(C·2^k+D)/2^{2k}
    via exact integer trunc (hardware TDG targets this with short streams).
    """
    n_bits = 2 * k
    sx = 1 if x >= 0 else -1
    sy = 1 if y >= 0 else -1
    xu = abs(_quantize_pm1(x, n_bits))
    yu = abs(_quantize_pm1(y, n_bits))
    # Full product scaled back to n_bits signed-magnitude domain
    # x≈xu/S, y≈yu/S, xy≈xu*yu/S^2 → integer round(xu*yu/S)
    S = (1 << n_bits) - 1
    prod = (xu * yu + S // 2) // S
    prod = min(prod, S)
    return float(sx * sy * prod / S)


def tdg_multiply_stream(x: float, y: float, k: int = 5) -> float:
    """TDG mul estimated from short DSC streams (length L=2^k)."""
    n_bits = 2 * k
    L = 1 << k
    S = (1 << n_bits) - 1
    sx = 1 if x >= 0 else -1
    sy = 1 if y >= 0 else -1
    xu = abs(_quantize_pm1(x, n_bits))
    yu = abs(_quantize_pm1(y, n_bits))
    A, B = tdg_split(xu, k)
    C, D = tdg_split(yu, k)
    AL, BL = dsc_unary(A, L), dsc_unary(B, L)
    CL, DL = dsc_unary(C, L), dsc_unary(D, L)
    # Recover partition integers from stream ones (DSC unary → exact A,B,C,D)
    Ar, Br = int(AL.sum()), int(BL.sum())
    Cr, Dr = int(CL.sum()), int(DL.sum())
    xu_r = (Ar << k) + Br
    yu_r = (Cr << k) + Dr
    prod = (xu_r * yu_r + S // 2) // S
    prod = min(prod, S)
    return float(sx * sy * prod / S)


def traditional_sc_multiply(
    x: float, y: float, length: int, seed: int = 0
) -> float:
    rng = np.random.default_rng(seed)
    pa = 0.5 * (np.clip(x, -1, 1) + 1)
    pb = 0.5 * (np.clip(y, -1, 1) + 1)
    a = (rng.random(length) < pa).astype(np.uint8)
    b = (rng.random(length) < pb).astype(np.uint8)
    # bipolar XNOR
    z = 1 - (a ^ b)
    return float(2.0 * z.mean() - 1.0)


def dsc_multiply(x: float, y: float, length: int) -> float:
    """Deterministic head+uniform style short/long DSC mul (unipolar→bipolar)."""
    xa = abs(np.clip(x, -1, 1))
    ya = abs(np.clip(y, -1, 1))
    ones_a = int(round(xa * length))
    ones_b = int(round(ya * length))
    a = dsc_unary(ones_a, length)
    # uniform-ish for b
    b = np.zeros(length, dtype=np.uint8)
    if ones_b > 0:
        idx = np.linspace(0, length - 1, ones_b, dtype=int)
        b[idx] = 1
    prod = float(np.mean(a & b))
    return float(np.sign(x) * np.sign(y) * prod) if x != 0 and y != 0 else float(
        np.sign(x) * np.sign(y) * prod
    )


def sc_signed_mul(a_mag: int, a_sign: int, b_mag: int, b_sign: int) -> tuple[int, int]:
    """Fig. 2: mag=AND, sign=XOR. Bits in {0,1}."""
    return a_mag & b_mag, a_sign ^ b_sign


def sc_sat_add_bits(
    x: int, y: int, sat_prev: int
) -> tuple[int, int]:
    """Table I stochastic addition (+1=1, −1=0 encoding of signed trit via sat).

    Using bipolar bits where 1→+1, 0→−1 is incomplete for ternary Table I.
    Lab encoding: inputs in {-1,0,+1}; return (z, sat) with z in {-1,0,+1}.
    """
    if x == 1 and y == 1:
        return 1, 1
    if (x == 1 and y == 0) or (x == 0 and y == 1):
        return 1, 0
    if (x == -1 and y == 0) or (x == 0 and y == -1):
        return -1, 0
    if x == -1 and y == -1:
        return -1, -1
    if (x == 1 and y == -1) or (x == -1 and y == 1):
        return sat_prev, 0
    # 0,0
    return sat_prev, 0


def maxlog_llr_bpsk(y: np.ndarray, H: np.ndarray, s_hat: np.ndarray, noise_var: float) -> np.ndarray:
    """Per-antenna bit LLR for real BPSK (±1) given current sample (Eq. 9/13 style)."""
    nt = H.shape[1]
    llr = np.zeros(nt)
    for i in range(nt):
        s0 = s_hat.copy()
        s1 = s_hat.copy()
        s0[i] = -1.0
        s1[i] = 1.0
        d0 = np.linalg.norm(y - H @ s0) ** 2
        d1 = np.linalg.norm(y - H @ s1) ** 2
        llr[i] = (d0 - d1) / (noise_var + 1e-12)
    return llr


def gibbs_mimo_detect(
    y: np.ndarray,
    H: np.ndarray,
    noise_var: float,
    n_warmup: int = 8,
    n_outer: int = 12,
    decoder: Callable[[np.ndarray], np.ndarray] | None = None,
    seed: int = 0,
) -> dict:
    """Real BPSK MIMO Gibbs: warm-up (Eq. 7–8) then GsUD (Eq. 10–14).

    `decoder(llr) -> hard bits in {±1}` simulates channel-decoder feedback.
    Default decoder = sign(llr) (hard MAP stub).
    """
    rng = np.random.default_rng(seed)
    nt = H.shape[1]
    if decoder is None:
        decoder = lambda llr: np.where(llr >= 0, 1.0, -1.0)

    s = rng.choice([-1.0, 1.0], size=nt)
    # Warm-up
    for _ in range(n_warmup):
        for i in range(nt):
            llr = maxlog_llr_bpsk(y, H, s, noise_var)
            # Eq. 8: soft sample with noise to avoid latch
            p1 = 1.0 / (1.0 + np.exp(-llr[i]))
            s[i] = 1.0 if (rng.random() < p1) else -1.0
            s[i] = float(np.clip(s[i] + rng.normal(0, 0.05), -1, 1))
            s[i] = 1.0 if s[i] >= 0 else -1.0

    llr = maxlog_llr_bpsk(y, H, s, noise_var)
    # GsUD outer iterations
    for _ in range(n_outer):
        bits = decoder(llr)
        s = bits.astype(np.float64)
        llr = maxlog_llr_bpsk(y, H, s, noise_var)

    hard = decoder(llr)
    return {"s_hat": hard, "llr": llr, "s_final": s}


def simulate_ber(
    snr_db_list: list[float],
    n_tx: int = 2,
    n_frames: int = 200,
    n_warmup: int = 8,
    n_outer: int = 12,
    seed: int = 0,
) -> list[dict]:
    """Uncoded BER for real BPSK MIMO with SIM GsUD vs ZF baseline."""
    rng = np.random.default_rng(seed)
    rows = []
    for snr in snr_db_list:
        noise_var = 10 ** (-snr / 10.0)
        err_sim, err_zf, bits = 0, 0, 0
        for _ in range(n_frames):
            H = rng.normal(size=(n_tx, n_tx)) / np.sqrt(n_tx)
            s_true = rng.choice([-1.0, 1.0], size=n_tx)
            y = H @ s_true + np.sqrt(noise_var) * rng.normal(size=n_tx)
            out = gibbs_mimo_detect(
                y, H, noise_var, n_warmup=n_warmup, n_outer=n_outer, seed=rng.integers(1 << 30)
            )
            err_sim += int(np.sum(out["s_hat"] != s_true))
            # ZF
            try:
                s_zf = np.sign(np.linalg.solve(H, y))
                s_zf = np.where(s_zf == 0, 1.0, s_zf)
            except np.linalg.LinAlgError:
                s_zf = np.ones(n_tx)
            err_zf += int(np.sum(s_zf != s_true))
            bits += n_tx
        rows.append(
            {
                "snr_db": snr,
                "ber_sim": err_sim / bits,
                "ber_zf": err_zf / bits,
            }
        )
    return rows
