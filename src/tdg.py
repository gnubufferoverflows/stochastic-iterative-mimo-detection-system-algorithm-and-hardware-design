"""Two Divisions Generator (TDG) and Stochastic Multiplier Benchmark Suite.

Implements:
- Signed stochastic signal representation (Eq. 5, Fig. 1)
- Stochastic Signed Multiplication (SM, Fig. 2)
- Stochastic Signed Saturating Addition (SA, Table I, Eq. 6)
- Two Divisions Generator (TDG, Eqs. 19-22, Fig. 5)
- Table II benchmark replication: Random vs DSC vs SWG vs TDG
"""

from __future__ import annotations

import numpy as np


def snr_db(ref: np.ndarray, est: np.ndarray) -> float:
    """Eq. (Table II footnote): SNR = 10 * log10( sum(Test^2) / sum((Float - Test)^2) )."""
    ref = np.asarray(ref, dtype=np.float64).ravel()
    est = np.asarray(est, dtype=np.float64).ravel()
    err = ref - est
    num = float(np.sum(est ** 2)) + 1e-30
    den = float(np.sum(err ** 2)) + 1e-30
    return float(10.0 * np.log10(num / den))


# ------------------------------------------------------------------------------
# Signed Stochastic Representation & Elementary SCEs
# ------------------------------------------------------------------------------

def sc_signed_mul_bits(a_mag: int, a_sign: int, b_mag: int, b_sign: int) -> tuple[int, int]:
    """Fig. 2: Stochastic signed multiplier bit-level operation.
    
    Magnitude is AND, Sign is XOR.
    """
    z_mag = int(a_mag & b_mag) & 1
    z_sign = int(a_sign ^ b_sign) & 1
    return z_mag, z_sign


def sc_sat_add_bits(x: int, y: int, sat_prev: int) -> tuple[int, int]:
    """Table I: Stochastic saturating signed adder.
    
    Inputs x, y in {-1, 0, +1}, sat_prev in {-1, 0, +1}.
    Returns (z, sat_next).
    """
    if x == 1 and y == 1:
        return 1, 1
    elif (x == 1 and y == 0) or (x == 0 and y == 1):
        return 1, 0
    elif (x == -1 and y == 0) or (x == 0 and y == -1):
        return -1, 0
    elif x == -1 and y == -1:
        return -1, -1
    elif (x == 1 and y == -1) or (x == -1 and y == 1):
        return sat_prev, 0
    else:  # x == 0 and y == 0
        return sat_prev, 0


# ------------------------------------------------------------------------------
# Two Divisions Generator (TDG) Implementation (Sec. III-D / Fig. 5)
# ------------------------------------------------------------------------------

def quantize_signed(x: float, n_bits: int = 10) -> tuple[int, int]:
    """Quantize x in [-1.0, 1.0] to signed-magnitude: (sign, magnitude).
    
    sign: 0 for positive, 1 for negative.
    magnitude: integer in [0, 2^(n_bits-1) - 1].
    """
    x_clip = float(np.clip(x, -1.0, 1.0))
    sign = 1 if x_clip < 0 else 0
    max_val = (1 << (n_bits - 1)) - 1
    mag = int(round(abs(x_clip) * max_val))
    return sign, min(mag, max_val)


def tdg_decompose(mag: int, k: int = 5) -> tuple[int, int]:
    """Eq. (19): Partition magnitude into coarse X1 and fine X2.
    
    mag = X1 * 2^k + X2, where X1 = mag >> k, X2 = mag & (2^k - 1).
    """
    mask = (1 << k) - 1
    x1 = (mag >> k) & mask
    x2 = mag & mask
    return x1, x2


def generate_dsc_unary(value: int, length: int) -> np.ndarray:
    """Generate low-discrepancy deterministic unary stream with exact 'value' ones."""
    val_clamped = int(np.clip(value, 0, length))
    stream = np.zeros(length, dtype=np.uint8)
    # Uniform interleaved placement for minimal discrepancy
    if val_clamped > 0 and val_clamped < length:
        indices = np.round(np.linspace(0, length - 1, val_clamped)).astype(int)
        stream[indices] = 1
    elif val_clamped >= length:
        stream[:] = 1
    return stream


def tdg_multiply(x: float, y: float, k: int = 5, n_bits: int = 10) -> float:
    """TDG-based signed multiplication (Fig. 5 / Table II).
    
    Decomposes |x| into (A, B) and |y| into (C, D) using k-bit divisions (k=5 => L=32 or k=6 => L=64).
    Computes product z via TDG short stream accumulation.
    """
    sign_x, mag_x = quantize_signed(x, n_bits)
    sign_y, mag_y = quantize_signed(y, n_bits)
    sign_z = sign_x ^ sign_y

    a, b = tdg_decompose(mag_x, k)
    c, d = tdg_decompose(mag_y, k)

    length = 1 << k
    max_val = (1 << (n_bits - 1)) - 1

    # Streams for coarse and fine partitions
    stream_a = generate_dsc_unary(a, length)
    stream_b = generate_dsc_unary(b, length)
    stream_c = generate_dsc_unary(c, length)
    stream_d = generate_dsc_unary(d, length)

    # TDG bit-level integration (Fig. 5b):
    # Cross products: A*C, A*D, B*C, B*D
    # Coarse accumulator: Ar = sum(A), Br = sum(B), Cr = sum(C), Dr = sum(D)
    ar = int(np.sum(stream_a))
    br = int(np.sum(stream_b))
    cr = int(np.sum(stream_c))
    dr = int(np.sum(stream_d))

    # Composite magnitude:
    # mag_x_est = ar * 2^k + br
    # mag_y_est = cr * 2^k + dr
    mag_x_est = (ar << k) + br
    mag_y_est = (cr << k) + dr

    # Product in fixed-point scale
    prod_mag = (mag_x_est * mag_y_est + (max_val >> 1)) // max_val
    prod_mag = min(prod_mag, max_val)

    val = float(prod_mag) / float(max_val)
    return -val if sign_z else val


# ------------------------------------------------------------------------------
# Alternative Multipliers for Table II Replication
# ------------------------------------------------------------------------------

def random_sc_multiply(x: float, y: float, length: int = 1024, seed: int = 0) -> float:
    """Method 1: Random Bernoulli bitstream multiplication via bipolar XNOR (Ref. [16])."""
    rng = np.random.default_rng(seed)
    p_x = 0.5 * (float(np.clip(x, -1.0, 1.0)) + 1.0)
    p_y = 0.5 * (float(np.clip(y, -1.0, 1.0)) + 1.0)
    
    bits_x = (rng.random(length) < p_x).astype(np.uint8)
    bits_y = (rng.random(length) < p_y).astype(np.uint8)
    
    # Bipolar multiplication via XNOR gate: Z = 1 - (X ^ Y)
    bits_z = 1 - (bits_x ^ bits_y)
    
    p_z = float(np.mean(bits_z))
    return float(2.0 * p_z - 1.0)


def dsc_multiply(x: float, y: float, length: int = 1024) -> float:
    """Method 2 & 3: Deterministic Stochastic Computation (DSC) multiplier (Ref. [25]).
    
    Uses deterministic low-discrepancy Halton or interleaved sequences.
    """
    p_x = 0.5 * (float(np.clip(x, -1.0, 1.0)) + 1.0)
    p_y = 0.5 * (float(np.clip(y, -1.0, 1.0)) + 1.0)

    n_x = int(round(p_x * length))
    n_y = int(round(p_y * length))

    # Low-discrepancy bit generation
    stream_x = np.zeros(length, dtype=np.uint8)
    stream_y = np.zeros(length, dtype=np.uint8)

    if n_x > 0:
        idx_x = (np.arange(n_x) * length // n_x).astype(int)
        stream_x[idx_x] = 1
    if n_y > 0:
        # Mutually orthogonal prime step for second stream
        idx_y = ((np.arange(n_y) * 37) % length).astype(int)
        stream_y[idx_y] = 1

    bits_z = 1 - (stream_x ^ stream_y)
    p_z = float(np.mean(bits_z))
    return float(2.0 * p_z - 1.0)


def swg_multiply(x: float, y: float, length: int = 64, seed: int = 0) -> float:
    """Method 4: Sawtooth Wave Generator (SWG) multiplier (Ref. [23]).
    
    Generates periodic sawtooth ramp comparator streams.
    """
    rng = np.random.default_rng(seed)
    p_x = 0.5 * (float(np.clip(x, -1.0, 1.0)) + 1.0)
    p_y = 0.5 * (float(np.clip(y, -1.0, 1.0)) + 1.0)

    ramp_x = (np.arange(length) % 16) / 16.0
    ramp_y = ((np.arange(length) * 5 + 3) % 16) / 16.0

    bits_x = (ramp_x < p_x).astype(np.uint8)
    bits_y = (ramp_y < p_y).astype(np.uint8)

    bits_z = 1 - (bits_x ^ bits_y)
    p_z = float(np.mean(bits_z))
    return float(2.0 * p_z - 1.0)


def run_table2_benchmark(n_trials: int = 500, seed: int = 42) -> dict[str, dict[str, float]]:
    """Reproduce Table II: Performance of Various Stochastic Multiplication Computations."""
    rng = np.random.default_rng(seed)
    x_vals = rng.uniform(-0.95, 0.95, size=n_trials)
    y_vals = rng.uniform(-0.95, 0.95, size=n_trials)
    ref_prods = x_vals * y_vals

    # 1. Random (L=1024)
    rnd_1024 = np.array([random_sc_multiply(x, y, length=1024, seed=i) for i, (x, y) in enumerate(zip(x_vals, y_vals))])
    snr_rnd_1024 = snr_db(ref_prods, rnd_1024)

    # 2. DSC (L=1024)
    dsc_1024 = np.array([dsc_multiply(x, y, length=1024) for x, y in zip(x_vals, y_vals)])
    snr_dsc_1024 = snr_db(ref_prods, dsc_1024)

    # 3. DSC (L=64)
    dsc_64 = np.array([dsc_multiply(x, y, length=64) for x, y in zip(x_vals, y_vals)])
    snr_dsc_64 = snr_db(ref_prods, dsc_64)

    # 4. SWG (L=64)
    swg_64 = np.array([swg_multiply(x, y, length=64, seed=i) for i, (x, y) in enumerate(zip(x_vals, y_vals))])
    snr_swg_64 = snr_db(ref_prods, swg_64)

    # 5. TDG (L=64, k=6 -> 64 cycles)
    tdg_64 = np.array([tdg_multiply(x, y, k=5, n_bits=10) for x, y in zip(x_vals, y_vals)])
    snr_tdg_64 = snr_db(ref_prods, tdg_64)

    return {
        "Random_1024": {"latency": 1024, "paper_snr_db": 43.0, "measured_snr_db": round(snr_rnd_1024, 1)},
        "DSC_1024": {"latency": 1024, "paper_snr_db": 57.8, "measured_snr_db": round(snr_dsc_1024, 1)},
        "DSC_64": {"latency": 64, "paper_snr_db": 34.1, "measured_snr_db": round(snr_dsc_64, 1)},
        "SWG_64": {"latency": 64, "paper_snr_db": 27.8, "measured_snr_db": round(snr_swg_64, 1)},
        "TDG_64": {"latency": 64, "paper_snr_db": 39.1, "measured_snr_db": round(snr_tdg_64, 1)},
    }
