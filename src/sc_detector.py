"""Bit-accurate model of one stochastic SIM detector (Figs. 4, 5, 7, 8) for 4x4 16-QAM.

This is the golden reference for ``hdl/sim_mimo_detector_core.v``: every register and every
stream bit is modelled cycle by cycle, so the RTL must match it exactly. All V vectors in a
batch are independent detector instances with identical random generators.

One iteration lasts L = 64 clock cycles (Sec. V-A). In every cycle:
1. TDG converts each 10-bit |H_kj| and |y_k| to a stream bit (Fig. 5, k1 = 6, k2 = 4).
2. The bit mapping unit turns the current sample x into symbol streams s_j (Fig. 7): the sign
   is ~b0 and the magnitude is all ones (outer level 3/3) or the period-3 pattern 100 (1/3).
3. d(k) = SA(y_k, -SA_chain_j SM(H_kj, s_j)) (Eq. 15, Fig. 7 top).
4. For every bit (k, b): delta = SA(s_flip, -s_k) and d_flip(r) = SA(d(r), -SM(H_rk, delta))
   (Eq. 17, Fig. 7 bottom). Only the hypothesis that differs from x needs a new vector.
5. Each of the 17 x 8 d streams passes a norm unit (Fig. 8): an integrator that emits 1 and
   subtracts U whenever its magnitude reaches U = sqrt(L) = 8. The 8 outputs of a vector are
   merged by an SA chain and counted by the TCS converter (reset every L cycles).
After the 64 cycles the counts c give l = -c (an L1 approximation of -||d||^2 / sigma^2), the
CAS units keep the maxima (Eq. 18), lambda1^e = lmax+ - lmax- and, in warm-up, the sample is
updated by x = [l+ - l- + R > 0] (Eq. 8). R is zero mean and different for every bit: bit b
uses 6-bit generator b mod 5 rotated left by b div 5, minus 32, shifted right by ``r_shift``.

Reading of Fig. 8's norm unit: the drawing shows an accumulator, a |x| >= U comparator whose
output is the stream bit, and a mux feeding U back. It is modelled as a subtract-U integrator,
which makes the output rate |d| / U (a scaled absolute value); the paper gives no equation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .tdg import K1, K2, K_BITS, debruijn_next

L = 1 << K1          # stream length / cycles per iteration
U = 8                # norm-unit threshold, U ~ sqrt(L)
NT2 = 8              # real transmit dimensions (4 complex antennas)
NR2 = 8              # real receive dimensions
NB = 16              # bits per vector (4 antennas x 4 bits)
Q = 2                # bits per real dimension (16-QAM)
G6_SEEDS = (1, 13, 29, 47, 58)  # H column groups 0-3, y / R / LLR stream
G4_SEEDS = (1, 6, 11)           # H fine, y fine, tie breaking
CNT_BITS = 7
LLR_BITS = 8


def bit_dims() -> tuple[np.ndarray, np.ndarray]:
    """Real dimension and label position of each of the 16 bits (antenna-major, re then im)."""
    dims, pos = [], []
    for i in range(4):
        for part in range(2):
            for b in range(Q):
                dims.append(i + 4 * part)
                pos.append(b)
    return np.array(dims), np.array(pos)


DIMS, POS = bit_dims()


def rot6(v: int, k: int) -> int:
    """Rotate a 6-bit value left by k; gives each bit its own R from the shared generators."""
    k %= 6
    return ((v << k) | (v >> (6 - k))) & 0x3F


def sa(x: np.ndarray, y: np.ndarray, sat: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Table I adder on ternary arrays; returns (z, new sat)."""
    s = x + y
    z = np.where(s >= 1, 1, np.where(s <= -1, -1, sat))
    new_sat = np.where(s == 2, 1, np.where(s == -2, -1, 0))
    return z.astype(np.int8), new_sat.astype(np.int8)


def quantize_inputs(H_r: np.ndarray, y_r: np.ndarray, smax: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Scale to [-1, 1] (Sec. V-A) and quantize to sign + 10-bit magnitude.

    H is scaled by the largest PAM amplitude so that symbols map to {+-1, +-1/3}.
    Returns (h_q, y_q, scale) with h_q (V, 8, 8) and y_q (V, 8) signed integers in [-1023, 1023].
    """
    Hs = H_r * smax
    a = 1.0 / np.maximum(np.abs(Hs).max(axis=(1, 2)), np.abs(y_r).max(axis=1))
    full = (1 << K_BITS) - 1
    h_q = np.clip(np.round(Hs * a[:, None, None] * (1 << K_BITS)), -full, full).astype(np.int64)
    y_q = np.clip(np.round(y_r * a[:, None] * (1 << K_BITS)), -full, full).astype(np.int64)
    return h_q, y_q, a


@dataclass
class IterationTrace:
    counts: np.ndarray   # (V, 17) TCS counts: index 0 = current sample, 1 + j = bit j flipped
    llr: np.ndarray      # (V, 16) lambda1^e after the CAS
    x: np.ndarray        # (V, 16) sample after the iteration


class StochasticDetector:
    """Batched bit-accurate detector; ``r_shift`` scales the Eq. (8) random signal R."""

    def __init__(self, h_q: np.ndarray, y_q: np.ndarray, x0: np.ndarray, r_shift: int = 0) -> None:
        self.V = h_q.shape[0]
        self.h_sign = (h_q < 0).astype(np.int8)
        self.h_mag = np.abs(h_q)
        self.y_sign = (y_q < 0).astype(np.int8)
        self.y_mag = np.abs(y_q)
        self.x = np.asarray(x0, dtype=np.int64).copy()
        self.r_shift = r_shift
        self.g6 = list(G6_SEEDS)
        self.g4 = list(G4_SEEDS)
        lmin = -(1 << (LLR_BITS - 1)) + 1
        self.lmax1 = np.full((self.V, NB), lmin, dtype=np.int64)
        self.lmax0 = np.full((self.V, NB), lmin, dtype=np.int64)
        self.cas_valid = False

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _tdg_bit(mag: np.ndarray, sign: np.ndarray, r6: int, r4: int, sat: np.ndarray):
        coarse = ((mag >> K2) > r6).astype(np.int8)
        fine = (((mag & ((1 << K2) - 1)) > r4) & (r6 == (1 << K1) - 1)).astype(np.int8)
        z, sat = sa(coarse, fine, sat)
        return (z * (1 - 2 * sign)).astype(np.int8), sat

    def _symbol_streams(self, x: np.ndarray, phase3: int, flip: int | None = None) -> np.ndarray:
        """Ternary symbol stream bits of all 8 real dimensions for sample x (V, 16)."""
        out = np.empty((self.V, NT2), dtype=np.int8)
        inner_on = 1 if phase3 == 0 else 0
        for k in range(NT2):
            ant, part = k % 4, k // 4
            base = ant * 4 + part * 2
            b0 = x[:, base]
            b1 = x[:, base + 1]
            mag = np.where(b1 == 1, inner_on, 1)
            out[:, k] = mag * np.where(b0 == 1, 1, -1)
        return out

    def _flip_stream(self, x: np.ndarray, j: int, phase3: int) -> np.ndarray:
        """Symbol stream of dimension DIMS[j] with bit j flipped, (V,)."""
        k = DIMS[j]
        ant, part = k % 4, k // 4
        base = ant * 4 + part * 2
        b0 = x[:, base].copy()
        b1 = x[:, base + 1].copy()
        if POS[j] == 0:
            b0 ^= 1
        else:
            b1 ^= 1
        inner_on = 1 if phase3 == 0 else 0
        return (np.where(b1 == 1, inner_on, 1) * np.where(b0 == 1, 1, -1)).astype(np.int8)

    # ---------------------------------------------------------------- iteration
    def run_iteration(self, mode_gsud: bool, dec_bits: np.ndarray | None = None) -> IterationTrace:
        V = self.V
        if mode_gsud:
            self.x = np.asarray(dec_bits, dtype=np.int64).copy()  # Eq. (10)
        x = self.x
        z8 = lambda *s: np.zeros((V,) + s, dtype=np.int8)
        sat_h, sat_y = z8(NR2, NT2), z8(NR2)
        sat_tree, sat_d = z8(NR2, NT2), z8(NR2)
        sat_delta, sat_f = z8(NB), z8(NB, NR2)
        sat_sum = z8(NB + 1, NR2)
        integ = np.zeros((V, NB + 1, NR2), dtype=np.int64)
        cnt = np.zeros((V, NB + 1), dtype=np.int64)
        r4h, r4y = self.g4[0], self.g4[1]
        for t in range(L):
            phase3 = t % 3
            # 1. TDG input streams
            h_bits = np.empty((V, NR2, NT2), dtype=np.int8)
            for j in range(NT2):
                r6 = self.g6[j % 4]
                h_bits[:, :, j], sat_h[:, :, j] = self._tdg_bit(
                    self.h_mag[:, :, j], self.h_sign[:, :, j], r6, r4h, sat_h[:, :, j]
                )
            y_bits, sat_y = self._tdg_bit(self.y_mag, self.y_sign, self.g6[4], r4y, sat_y)
            # 2-3. symbol streams and d = y - H s
            s_bits = self._symbol_streams(x, phase3)
            prod = h_bits * s_bits[:, None, :]
            acc = prod[:, :, 0]
            for j in range(1, NT2):
                acc, sat_tree[:, :, j] = sa(acc, prod[:, :, j], sat_tree[:, :, j])
            d, sat_d = sa(y_bits, -acc, sat_d)
            # 4. flipped hypotheses, Eq. (17)
            streams = np.empty((V, NB + 1, NR2), dtype=np.int8)
            streams[:, 0, :] = d
            for j in range(NB):
                k = DIMS[j]
                delta, sat_delta[:, j] = sa(self._flip_stream(x, j, phase3), -s_bits[:, k], sat_delta[:, j])
                p = h_bits[:, :, k] * delta[:, None]
                streams[:, 1 + j, :], sat_f[:, j, :] = sa(d, -p, sat_f[:, j, :])
            # 5. norm units, SA chain, TCS converter
            integ += streams
            fire = np.abs(integ) >= U
            integ -= np.where(fire, np.sign(integ) * U, 0)
            nb_out = fire.astype(np.int8)
            acc_n = nb_out[:, :, 0]
            for r in range(1, NR2):
                acc_n, sat_sum[:, :, r] = sa(acc_n, nb_out[:, :, r], sat_sum[:, :, r])
            cnt += acc_n
            # generators advance every cycle; 4-bit generators once per window
            self.g6 = [debruijn_next(g, K1) for g in self.g6]
        self.g4 = [debruijn_next(g, K2) for g in self.g4]

        # end of iteration: CAS, LLR and sample update
        cur = cnt[:, :1]
        flip = cnt[:, 1:]
        c1 = np.where(x == 1, cur, flip)
        c0 = np.where(x == 0, cur, flip)
        l1, l0 = -c1, -c0
        self.lmax1 = np.maximum(self.lmax1, l1)
        self.lmax0 = np.maximum(self.lmax0, l0)
        llr = self.lmax1 - self.lmax0
        if not mode_gsud:
            r = np.array([(rot6(self.g6[b % 5], b // 5) - (1 << (K1 - 1))) >> self.r_shift for b in range(NB)])
            diff = l1 - l0 + r[None, :]
            tie = self.g4[2] & 1
            self.x = np.where(diff > 0, 1, np.where(diff < 0, 0, tie)).astype(np.int64)
        return IterationTrace(counts=cnt.copy(), llr=llr.copy(), x=self.x.copy())

    def llr_stream_bit(self, llr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Stream generator of Fig. 8: (sign, |lambda| > r6) for the current generator state."""
        sign = (llr < 0).astype(np.int8)
        mag = (np.minimum(np.abs(llr), (1 << K1) - 1) > self.g6[4]).astype(np.int8)
        return sign, mag
