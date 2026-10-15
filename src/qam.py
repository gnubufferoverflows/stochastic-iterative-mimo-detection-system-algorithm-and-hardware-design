"""QAM Modulation & Gray Mapping for MIMO Detection (16-QAM & 64-QAM).

Implements Eq. (11): s_k = map(x_k) and bit demapping for complex MIMO symbols.
"""

from __future__ import annotations

import numpy as np

# 16-QAM: 4 bits per symbol (2 real, 2 imag). Average energy Es = 1.0
# Normalization factor: 1 / sqrt(10)
Q16_SCALE = 1.0 / np.sqrt(10.0)
Q16_PAM2 = np.array([-3.0, -1.0, 3.0, 1.0]) * Q16_SCALE  # Gray: 00->-3, 01->-1, 10->+3, 11->+1 (or standard Gray)

# Canonical Gray mapping for 2-bit PAM:
# Bit pair (b0, b1):
# 00 -> -3, 01 -> -1, 11 -> +1, 10 -> +3
GRAY_2PAM = {
    (0, 0): -3.0 * Q16_SCALE,
    (0, 1): -1.0 * Q16_SCALE,
    (1, 1): +1.0 * Q16_SCALE,
    (1, 0): +3.0 * Q16_SCALE,
}

# 64-QAM: 6 bits per symbol (3 real, 3 imag). Average energy Es = 1.0
# Normalization factor: 1 / sqrt(42)
Q64_SCALE = 1.0 / np.sqrt(42.0)
# Canonical Gray mapping for 3-bit PAM:
# 000->-7, 001->-5, 011->-3, 010->-1, 110->+1, 111->+3, 101->+5, 100->+7
GRAY_3PAM = {
    (0, 0, 0): -7.0 * Q64_SCALE,
    (0, 0, 1): -5.0 * Q64_SCALE,
    (0, 1, 1): -3.0 * Q64_SCALE,
    (0, 1, 0): -1.0 * Q64_SCALE,
    (1, 1, 0): +1.0 * Q64_SCALE,
    (1, 1, 1): +3.0 * Q64_SCALE,
    (1, 0, 1): +5.0 * Q64_SCALE,
    (1, 0, 0): +7.0 * Q64_SCALE,
}


def bits_to_16qam(bits: np.ndarray) -> np.ndarray:
    """Map binary bit array of length 4*Nt to Nt complex 16-QAM symbols.
    
    Bits format: each symbol takes 4 bits: [b0, b1, b2, b3]
    Real part from (b0, b1), Imag part from (b2, b3).
    """
    bits = np.asarray(bits, dtype=np.uint8).ravel()
    assert len(bits) % 4 == 0, f"Bits length {len(bits)} must be multiple of 4"
    n_syms = len(bits) // 4
    syms = np.zeros(n_syms, dtype=np.complex128)
    for i in range(n_syms):
        b = bits[4 * i : 4 * i + 4]
        re = GRAY_2PAM[(b[0], b[1])]
        im = GRAY_2PAM[(b[2], b[3])]
        syms[i] = complex(re, im)
    return syms


def bits_to_64qam(bits: np.ndarray) -> np.ndarray:
    """Map binary bit array of length 6*Nt to Nt complex 64-QAM symbols.
    
    Bits format: each symbol takes 6 bits: [b0, b1, b2, b3, b4, b5]
    Real part from (b0, b1, b2), Imag part from (b3, b4, b5).
    """
    bits = np.asarray(bits, dtype=np.uint8).ravel()
    assert len(bits) % 6 == 0, f"Bits length {len(bits)} must be multiple of 6"
    n_syms = len(bits) // 6
    syms = np.zeros(n_syms, dtype=np.complex128)
    for i in range(n_syms):
        b = bits[6 * i : 6 * i + 6]
        re = GRAY_3PAM[(b[0], b[1], b[2])]
        im = GRAY_3PAM[(b[3], b[4], b[5])]
        syms[i] = complex(re, im)
    return syms


def map_bits_to_qam(bits: np.ndarray, mod_order: int = 16) -> np.ndarray:
    """Eq. (11): General QAM mapper for 16-QAM or 64-QAM."""
    if mod_order == 16:
        return bits_to_16qam(bits)
    elif mod_order == 64:
        return bits_to_64qam(bits)
    elif mod_order == 4 or mod_order == 2:  # QPSK / BPSK
        # QPSK: 2 bits per symbol
        bits = np.asarray(bits, dtype=np.uint8).ravel()
        n_syms = len(bits) // 2
        scale = 1.0 / np.sqrt(2.0)
        re = np.where(bits[0::2] == 1, scale, -scale)
        im = np.where(bits[1::2] == 1, scale, -scale)
        return re + 1j * im
    raise ValueError(f"Unsupported modulation order {mod_order}")


def get_constellation(mod_order: int = 16) -> tuple[np.ndarray, np.ndarray]:
    """Return all constellation points and corresponding bit labels."""
    if mod_order == 16:
        points = []
        labels = []
        for (b0, b1), re in GRAY_2PAM.items():
            for (b2, b3), im in GRAY_2PAM.items():
                points.append(complex(re, im))
                labels.append([b0, b1, b2, b3])
        return np.array(points, dtype=np.complex128), np.array(labels, dtype=np.uint8)
    elif mod_order == 64:
        points = []
        labels = []
        for (b0, b1, b2), re in GRAY_3PAM.items():
            for (b3, b4, b5), im in GRAY_3PAM.items():
                points.append(complex(re, im))
                labels.append([b0, b1, b2, b3, b4, b5])
        return np.array(points, dtype=np.complex128), np.array(labels, dtype=np.uint8)
    elif mod_order == 4:
        scale = 1.0 / np.sqrt(2.0)
        pts = np.array([complex(scale, scale), complex(-scale, scale), complex(scale, -scale), complex(-scale, -scale)])
        lbls = np.array([[1, 1], [0, 1], [1, 0], [0, 0]], dtype=np.uint8)
        return pts, lbls
    raise ValueError(f"Unsupported modulation order {mod_order}")


def hard_demap_qam(syms: np.ndarray, mod_order: int = 16) -> np.ndarray:
    """Hard slicer: finds closest constellation point and returns bit vector."""
    const_pts, const_labels = get_constellation(mod_order)
    m = int(np.log2(mod_order))
    out_bits = []
    for s in syms:
        dists = np.abs(s - const_pts) ** 2
        best_idx = int(np.argmin(dists))
        out_bits.extend(const_labels[best_idx])
    return np.array(out_bits, dtype=np.uint8)
