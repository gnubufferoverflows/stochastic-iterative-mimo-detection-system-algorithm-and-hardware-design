"""Stochastic computing primitives, Two Divisions Generator (TDG) and Table II benchmark.

Implements (Chen, Hu, Sobelman, TCAS-I 2015):
- Signed stochastic streams in sign-magnitude form: a(X) magnitude bits, s(X) sign bits (Fig. 1, Eq. 5)
- Stochastic signed multiplication SM: XOR on signs, AND on magnitudes (Fig. 2)
- Stochastic signed addition SA with one saturation memory bit (Table I, Eq. 6)
- Two Divisions Generator: k = k1 + k2 = 6 + 4 bit split, 2^k1 = 64-cycle windows (Eqs. 19-22, Fig. 5)
- Table II replication: Random[16], DSC[25], SWG[23] and TDG multipliers

Bit-level conventions shared with the RTL in ``hdl/``:
- A signed stochastic bit is the pair (mag, sign); its value is (1 - 2*sign) * mag (Eq. 5).
- Magnitudes are quantized to ``K_BITS = 10`` bits: |x| -> round(|x| * 2^10), clipped to 2^10 - 1.
- Random numbers come from de Bruijn sequence generators (an LFSR with the all-zero state
  spliced in), so a 2^n-cycle window visits every n-bit value exactly once.
"""

from __future__ import annotations

import numpy as np

K_BITS = 10  # magnitude bits of the fixed-point signal (Sec. V-A)
K1 = 6       # coarse part, sets the stream length L = 2^K1 = 64
K2 = 4       # fine part, dithered one bit per window
L_STREAM = 1 << K1


def snr_db(ref: np.ndarray, est: np.ndarray) -> float:
    """Table II definition: SNR = 10 log10( sum(Test^2) / sum((Float - Test)^2) )."""
    ref = np.asarray(ref, dtype=np.float64).ravel()
    est = np.asarray(est, dtype=np.float64).ravel()
    num = float(np.sum(est ** 2)) + 1e-30
    den = float(np.sum((ref - est) ** 2)) + 1e-30
    return float(10.0 * np.log10(num / den))


# ------------------------------------------------------------------------------
# Deterministic random number generators (de Bruijn / modified LFSR)
# ------------------------------------------------------------------------------

DEBRUIJN_TAPS = {6: (5, 4), 4: (3, 2)}  # x^6 + x^5 + 1 and x^4 + x^3 + 1


def debruijn_next(state: int, n: int) -> int:
    """One step of the n-bit de Bruijn generator (matches hdl/debruijn_gen.v)."""
    t_hi, t_lo = DEBRUIJN_TAPS[n]
    fb = ((state >> t_hi) ^ (state >> t_lo)) & 1
    if (state & ((1 << (n - 1)) - 1)) == 0:
        fb ^= 1
    return ((state << 1) | fb) & ((1 << n) - 1)


def debruijn_sequence(n: int, length: int, seed: int = 1) -> np.ndarray:
    """Return ``length`` consecutive states of the n-bit de Bruijn generator."""
    out = np.empty(length, dtype=np.int64)
    s = seed & ((1 << n) - 1)
    for i in range(length):
        out[i] = s
        s = debruijn_next(s, n)
    return out


# ------------------------------------------------------------------------------
# Elementary stochastic computing elements
# ------------------------------------------------------------------------------

def quantize_signed(x: float, n_bits: int = K_BITS) -> tuple[int, int]:
    """Quantize x in [-1, 1] to sign-magnitude (sign, mag) with ``n_bits`` magnitude bits."""
    x_clip = float(np.clip(x, -1.0, 1.0))
    sign = 1 if x_clip < 0 else 0
    mag = int(round(abs(x_clip) * (1 << n_bits)))
    return sign, min(mag, (1 << n_bits) - 1)


def sc_signed_mul_bits(a_mag: int, a_sign: int, b_mag: int, b_sign: int) -> tuple[int, int]:
    """Fig. 2: stochastic signed multiplier. Magnitude is AND, sign is XOR."""
    return int(a_mag & b_mag) & 1, int(a_sign ^ b_sign) & 1


def sc_sat_add_bits(x: int, y: int, sat_prev: int) -> tuple[int, int]:
    """Table I: stochastic signed addition on ternary bits x, y in {-1, 0, +1}.

    Returns (z, sat) where sat is the saturation memory for the next cycle.
    """
    if x == 1 and y == 1:
        return 1, 1
    if (x == 1 and y == 0) or (x == 0 and y == 1):
        return 1, 0
    if (x == -1 and y == 0) or (x == 0 and y == -1):
        return -1, 0
    if x == -1 and y == -1:
        return -1, -1
    # (1,-1), (-1,1) and (0,0): emit the stored saturation value and clear it
    return sat_prev, 0


def stream_value(mag: np.ndarray, sign: np.ndarray) -> float:
    """Eq. (5): v(X) = (1/L) * sum (1 - 2 s(X(t))) a(X(t))."""
    mag = np.asarray(mag, dtype=np.int64)
    sign = np.asarray(sign, dtype=np.int64)
    return float(np.sum((1 - 2 * sign) * mag)) / len(mag)


# ------------------------------------------------------------------------------
# Two Divisions Generator (Eqs. 19-22, Fig. 5)
# ------------------------------------------------------------------------------

def tdg_split(mag: int, k1: int = K1, k2: int = K2) -> tuple[int, int]:
    """Eq. (19): x = x^{k1} * 2^{k2} + x^{k2}."""
    return (mag >> k2) & ((1 << k1) - 1), mag & ((1 << k2) - 1)


def tdg_window(mag: int, r6: np.ndarray, r4: int, k1: int = K1, k2: int = K2) -> np.ndarray:
    """One 2^k1-cycle TDG magnitude window X_i^{k1} (Fig. 5(b)).

    The coarse comparator emits (x^{k1} > r6(t)) every cycle. The fine comparator
    (x^{k2} > r4) is switched in once per window and the two streams are merged by the
    Table I adder, so the window holds x^{k1} + X^{k2}(i) ones (Eqs. 21-22).

    The switch closes in the cycle where r6 is all ones. The coarse bit is always 0 there
    (x^{k1} <= 2^{k1} - 1), so the fine bit is never lost; the Table I adder clears its
    saturation memory on a (1, 0) input, which would drop the bit in any other cycle.
    """
    x1, x2 = tdg_split(mag, k1, k2)
    fine = 1 if x2 > r4 else 0
    r_max = (1 << k1) - 1
    out = np.zeros(len(r6), dtype=np.int64)
    sat = 0
    for t, r in enumerate(r6):
        a = 1 if x1 > int(r) else 0
        b = fine if int(r) == r_max else 0
        z, sat = sc_sat_add_bits(a, b, sat)
        out[t] = z
    return out


# ------------------------------------------------------------------------------
# Table II multipliers (all use the sign-magnitude SM of Fig. 2)
# ------------------------------------------------------------------------------

def _sm_value(mx: np.ndarray, sx: int, my: np.ndarray, sy: int) -> float:
    return (1 - 2 * (sx ^ sy)) * float(np.mean(mx & my))


def random_sc_multiply(x: float, y: float, length: int = 1024, seed: int = 0) -> float:
    """Random[16]: magnitudes compared with independent uniform random numbers each cycle."""
    rng = np.random.default_rng(seed)
    sx, mx = quantize_signed(x)
    sy, my = quantize_signed(y)
    ux = rng.integers(0, 1 << K_BITS, size=length)
    uy = rng.integers(0, 1 << K_BITS, size=length)
    return _sm_value((mx > ux).astype(np.int64), sx, (my > uy).astype(np.int64), sy)


def _bitrev(v: np.ndarray, n: int) -> np.ndarray:
    out = np.zeros_like(v)
    for i in range(n):
        out |= ((v >> i) & 1) << (n - 1 - i)
    return out


def dsc_multiply(x: float, y: float, length: int = 1024) -> float:
    """DSC[25]: deterministic low-discrepancy streams (ramp vs. bit-reversed counter).

    The magnitudes are truncated to log2(length) bits, so DSC at L = 64 loses the 4 LSBs.
    """
    n = int(np.log2(length))
    sx, mx = quantize_signed(x)
    sy, my = quantize_signed(y)
    mx >>= K_BITS - n
    my >>= K_BITS - n
    t = np.arange(length, dtype=np.int64)
    return _sm_value((mx > t).astype(np.int64), sx, (my > _bitrev(t, n)).astype(np.int64), sy)


def swg_multiply(x: float, y: float, length: int = 64, seed: int = 0, long_length: int = 1024) -> float:
    """SWG[23]: sliding window method. A window of ``length`` bits is taken at a random
    offset from a ``long_length`` random stream, so only 2^k1 randomly selected bits are used.
    """
    rng = np.random.default_rng(seed)
    sx, mx = quantize_signed(x)
    sy, my = quantize_signed(y)
    ux = rng.integers(0, 1 << K_BITS, size=long_length)
    uy = rng.integers(0, 1 << K_BITS, size=long_length)
    ax = (mx > ux).astype(np.int64)
    ay = (my > uy).astype(np.int64)
    off = int(rng.integers(0, long_length - length + 1))
    return _sm_value(ax[off:off + length], sx, ay[off:off + length], sy)


def tdg_multiply(
    x: float, y: float, window: int = 0, gen: str = "counter", seed_x: int = 1, seed_y: int = 37
) -> float:
    """TDG multiplier (L = 64): both operands converted by TDG, multiplied by SM.

    ``window`` selects the TDG window index i (Eq. 22); the 4-bit generators step once
    per window. ``gen`` picks the 6-bit random source:
    - "counter": deterministic generator [25], a ramp for x and its bit reversal for y
    - "lfsr": two differently seeded 6-bit de Bruijn LFSRs (the detector RTL uses these)
    """
    sx, mx = quantize_signed(x)
    sy, my = quantize_signed(y)
    if gen == "counter":
        r6x = np.arange(L_STREAM, dtype=np.int64)
        r6y = _bitrev(r6x, K1)
    elif gen == "lfsr":
        r6x = debruijn_sequence(K1, L_STREAM, seed_x)
        r6y = debruijn_sequence(K1, L_STREAM, seed_y)
    else:
        raise ValueError(f"unknown generator {gen!r}")
    r4x = int(debruijn_sequence(K2, window + 1, seed_x)[window])
    r4y = int(debruijn_sequence(K2, window + 1, seed_y)[window])
    ax = tdg_window(mx, r6x, r4x)
    ay = tdg_window(my, r6y, r4y)
    return _sm_value(ax, sx, ay, sy)


def run_table2_benchmark(n_trials: int = 500, seed: int = 42) -> dict[str, dict[str, float]]:
    """Reproduce Table II: SNR of the stochastic multipliers against floating point."""
    rng = np.random.default_rng(seed)
    x_vals = rng.uniform(-1.0, 1.0, size=n_trials)
    y_vals = rng.uniform(-1.0, 1.0, size=n_trials)
    ref = x_vals * y_vals
    pairs = list(zip(x_vals, y_vals))

    meas = {
        "Random_1024": [random_sc_multiply(x, y, 1024, seed=i) for i, (x, y) in enumerate(pairs)],
        "DSC_1024": [dsc_multiply(x, y, 1024) for x, y in pairs],
        "DSC_64": [dsc_multiply(x, y, 64) for x, y in pairs],
        "SWG_64": [swg_multiply(x, y, 64, seed=i) for i, (x, y) in enumerate(pairs)],
        "TDG_64": [tdg_multiply(x, y, window=i % (1 << K2), gen="counter") for i, (x, y) in enumerate(pairs)],
        "TDG_64_LFSR": [tdg_multiply(x, y, window=i % (1 << K2), gen="lfsr") for i, (x, y) in enumerate(pairs)],
    }
    paper = {"Random_1024": 43.0, "DSC_1024": 57.8, "DSC_64": 34.1, "SWG_64": 27.8, "TDG_64": 39.1, "TDG_64_LFSR": None}
    latency = {k: (1024 if k.endswith("1024") else 64) for k in meas}
    return {
        k: {"latency": latency[k], "paper_snr_db": paper[k], "measured_snr_db": round(snr_db(ref, np.array(v)), 1)}
        for k, v in meas.items()
    }
