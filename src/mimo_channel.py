"""MIMO channel models, complex-to-real decomposition and noise scaling.

Implements Eq. (1): y = H s + n.

- ``generate_channel``: i.i.d. Rayleigh flat fading (kept for unit tests and quick checks).
- ``TGnChannelC``: IEEE 802.11n TGn channel model C (Sec. V-A of the paper), NLOS.
  Tap delays, cluster powers, AoA/AoD and angular spreads are those of Erceg et al.,
  "TGn Channel Models," IEEE 802.11-03/940r4. Each tap is a Kronecker-correlated Rayleigh
  matrix built from truncated-Laplacian power azimuth spectra on half-wavelength uniform
  linear arrays. The frequency response is sampled on the 52 data subcarriers of a 20 MHz
  802.11n OFDM symbol; consecutive MIMO vectors of a frame occupy consecutive subcarriers.
  The channel is held static over a frame (no Doppler).
"""

from __future__ import annotations

import numpy as np


def generate_channel(n_r: int = 4, n_t: int = 4, rng: np.random.Generator | None = None) -> np.ndarray:
    """Complex i.i.d. Rayleigh flat-fading channel with CN(0, 1) entries."""
    rng = rng or np.random.default_rng()
    return (rng.normal(0.0, 1.0, (n_r, n_t)) + 1j * rng.normal(0.0, 1.0, (n_r, n_t))) / np.sqrt(2.0)


def complex_to_real_mimo(y: np.ndarray, H: np.ndarray, s: np.ndarray | None = None):
    """Real-valued equivalent of y = H s + n.

    [Re y; Im y] = [[Re H, -Im H], [Im H, Re H]] [Re s; Im s].
    Works on single vectors or on batches with leading axes (y: (..., Nr), H: (..., Nr, Nt)).
    """
    y_real = np.concatenate([np.real(y), np.imag(y)], axis=-1)
    hr, hi = np.real(H), np.imag(H)
    H_real = np.concatenate(
        [np.concatenate([hr, -hi], axis=-1), np.concatenate([hi, hr], axis=-1)], axis=-2
    )
    s_real = None if s is None else np.concatenate([np.real(s), np.imag(s)], axis=-1)
    return y_real, H_real, s_real


def compute_noise_var(eb_n0_db: float, mod_order: int = 16, code_rate: float = 0.5, n_t: int = 4) -> float:
    """Complex noise variance N0 for a given Eb/N0 (unit-energy symbols, E|h|^2 = 1).

    Per receive antenna the signal power is Nt and Nt * log2(M) * R information bits are
    carried per channel use, so Eb = 1 / (log2(M) R) and N0 = 1 / (log2(M) R Eb/N0).
    """
    bits_per_sym = int(np.log2(mod_order))
    return float(1.0 / (bits_per_sym * code_rate * 10.0 ** (eb_n0_db / 10.0)))


def zf_detect(y: np.ndarray, H: np.ndarray) -> np.ndarray:
    """Zero-forcing linear detector: s_hat = pinv(H) y."""
    return np.linalg.pinv(H) @ y


def mmse_detect(y: np.ndarray, H: np.ndarray, noise_var: float) -> np.ndarray:
    """Linear MMSE detector: s_hat = (H^H H + N0 I)^-1 H^H y."""
    n_t = H.shape[1]
    w = np.linalg.inv(H.conj().T @ H + noise_var * np.eye(n_t)) @ H.conj().T
    return w @ y


# ------------------------------------------------------------------------------
# IEEE 802.11n TGn channel model C
# ------------------------------------------------------------------------------

TGN_C = {
    "delay_ns": np.array([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 110, 140, 170, 200], dtype=float),
    "power_db": np.array([
        [0, -2.1, -4.3, -6.5, -8.6, -10.8, -13.0, -15.2, -17.3, -19.5, -np.inf, -np.inf, -np.inf, -np.inf],
        [-np.inf] * 6 + [-5.0, -7.2, -9.3, -11.5, -13.7, -15.8, -18.0, -20.2],
    ]),
    "aoa_deg": np.array([290.3, 332.3]),
    "as_rx_deg": np.array([24.6, 22.4]),
    "aod_deg": np.array([13.5, 56.4]),
    "as_tx_deg": np.array([24.7, 22.5]),
}

HT20_DATA_SUBCARRIERS = np.array([k for k in range(-28, 29) if k not in (0, -21, -7, 7, 21)])
SUBCARRIER_SPACING_HZ = 312.5e3


def laplacian_ula_correlation(n_ant: int, mean_deg: float, as_deg: float, spacing: float = 0.5) -> np.ndarray:
    """Spatial correlation of a ULA (spacing in wavelengths) for a truncated Laplacian PAS."""
    phi = np.deg2rad(np.linspace(-180.0, 180.0, 7201))
    mean = np.deg2rad(mean_deg)
    sigma = np.deg2rad(as_deg)
    wrapped = np.angle(np.exp(1j * (phi - mean)))
    pas = np.exp(-np.sqrt(2.0) * np.abs(wrapped) / sigma)
    pas /= np.trapezoid(pas, phi) if hasattr(np, "trapezoid") else np.trapz(pas, phi)
    m = np.arange(n_ant)
    lag = m[:, None] - m[None, :]
    integrand = np.exp(1j * 2 * np.pi * spacing * lag[..., None] * np.sin(phi)) * pas
    trap = np.trapezoid if hasattr(np, "trapezoid") else np.trapz
    return trap(integrand, phi, axis=-1)


def _psd_sqrt(r: np.ndarray) -> np.ndarray:
    w, v = np.linalg.eigh(r)
    return (v * np.sqrt(np.clip(w, 0.0, None))) @ v.conj().T


class TGnChannelC:
    """Frequency-selective TGn model C channel sampled per OFDM data subcarrier."""

    def __init__(self, n_r: int = 4, n_t: int = 4, spacing: float = 0.5) -> None:
        self.n_r, self.n_t = n_r, n_t
        p = 10.0 ** (TGN_C["power_db"] / 10.0)  # (2 clusters, taps)
        self.tap_cluster_power = p / p.sum()
        self.delays = TGN_C["delay_ns"] * 1e-9
        self.rx_sqrt = [
            _psd_sqrt(laplacian_ula_correlation(n_r, a, s, spacing))
            for a, s in zip(TGN_C["aoa_deg"], TGN_C["as_rx_deg"])
        ]
        self.tx_sqrt = [
            _psd_sqrt(laplacian_ula_correlation(n_t, a, s, spacing))
            for a, s in zip(TGN_C["aod_deg"], TGN_C["as_tx_deg"])
        ]

    def taps(self, rng: np.random.Generator) -> np.ndarray:
        """Draw one realization of the per-tap MIMO matrices, shape (taps, Nr, Nt)."""
        n_taps = len(self.delays)
        out = np.zeros((n_taps, self.n_r, self.n_t), dtype=np.complex128)
        for c in range(2):
            for t in range(n_taps):
                pw = self.tap_cluster_power[c, t]
                if pw <= 0:
                    continue
                g = (rng.normal(size=(self.n_r, self.n_t)) + 1j * rng.normal(size=(self.n_r, self.n_t))) / np.sqrt(2)
                out[t] += np.sqrt(pw) * self.rx_sqrt[c] @ g @ self.tx_sqrt[c].T
        return out

    def frame(self, n_vec: int, rng: np.random.Generator) -> np.ndarray:
        """Channel matrices for ``n_vec`` consecutive MIMO vectors of one frame, (n_vec, Nr, Nt)."""
        taps = self.taps(rng)
        sc = HT20_DATA_SUBCARRIERS[np.arange(n_vec) % len(HT20_DATA_SUBCARRIERS)]
        phase = np.exp(-2j * np.pi * sc[:, None] * SUBCARRIER_SPACING_HZ * self.delays[None, :])
        return np.einsum("vt,trc->vrc", phase, taps)


def rayleigh_frame(n_vec: int, rng: np.random.Generator, n_r: int = 4, n_t: int = 4) -> np.ndarray:
    """Block-independent i.i.d. Rayleigh matrices for each vector of a frame."""
    return (rng.normal(size=(n_vec, n_r, n_t)) + 1j * rng.normal(size=(n_vec, n_r, n_t))) / np.sqrt(2)
