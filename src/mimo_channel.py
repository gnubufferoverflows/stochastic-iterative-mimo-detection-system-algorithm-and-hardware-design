"""MIMO Channel Model, Complex-to-Real Equivalent Decomposition & Baselines.

Implements Eq. (1): y = H * s + n for Nt x Nr spatial-multiplexing MIMO systems.
"""

from __future__ import annotations

import numpy as np


def generate_channel(n_r: int = 4, n_t: int = 4, rng: np.random.Generator | None = None) -> np.ndarray:
    """Generate complex i.i.d. Rayleigh flat-fading channel matrix H.
    
    Each entry is CN(0, 1) = (randn + j * randn) / sqrt(2).
    """
    rng = rng or np.random.default_rng()
    h_real = rng.normal(0.0, 1.0 / np.sqrt(2.0), size=(n_r, n_t))
    h_imag = rng.normal(0.0, 1.0 / np.sqrt(2.0), size=(n_r, n_t))
    return h_real + 1j * h_imag


def complex_to_real_mimo(y: np.ndarray, H: np.ndarray, s: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    """Convert complex MIMO system y = H*s + n into equivalent real-valued system:
    
    [ Re(y) ] = [ Re(H)  -Im(H) ] * [ Re(s) ] + [ Re(n) ]
    [ Im(y) ]   [ Im(H)   Re(H) ]   [ Im(s) ]   [ Im(n) ]
    
    Dimensions:
    y_real: (2*Nr,)
    H_real: (2*Nr, 2*Nt)
    s_real: (2*Nt,)
    """
    n_r, n_t = H.shape
    y_real = np.concatenate([np.real(y), np.imag(y)])
    H_real = np.block([[np.real(H), -np.imag(H)], [np.imag(H), np.real(H)]])
    s_real = None
    if s is not None:
        s_real = np.concatenate([np.real(s), np.imag(s)])
    return y_real, H_real, s_real


def compute_noise_var(eb_n0_db: float, mod_order: int = 16, code_rate: float = 0.5, n_t: int = 4) -> float:
    """Calculate noise variance sigma^2 per complex dimension for given Eb/N0 in dB.
    
    Eb/N0 = Es / (bits_per_symbol * code_rate * N0)
    For average Es = 1.0, N0 = 1 / (log2(mod_order) * code_rate * 10^(Eb_N0_dB / 10)).
    Noise variance per complex dimension is sigma^2 = N0.
    In real equivalent model, noise variance per real dimension is sigma^2 / 2.
    """
    bits_per_sym = int(np.log2(mod_order))
    eb_n0_lin = 10.0 ** (eb_n0_db / 10.0)
    n0 = 1.0 / (bits_per_sym * code_rate * eb_n0_lin)
    return float(n0)


def zf_detect(y: np.ndarray, H: np.ndarray) -> np.ndarray:
    """Zero-Forcing (ZF) linear detector baseline: s_hat = (H^H * H)^(-1) * H^H * y."""
    h_pseudo_inv = np.linalg.pinv(H)
    return h_pseudo_inv @ y


def mmse_detect(y: np.ndarray, H: np.ndarray, noise_var: float) -> np.ndarray:
    """MMSE linear detector baseline: s_hat = (H^H * H + noise_var * I)^(-1) * H^H * y."""
    n_t = H.shape[1]
    w = np.linalg.inv(H.conj().T @ H + noise_var * np.eye(n_t)) @ H.conj().T
    return w @ y
