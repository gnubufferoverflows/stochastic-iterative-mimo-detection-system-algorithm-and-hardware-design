"""Parallel concatenated (turbo) code with a batched max-log-MAP (BCJR) decoder.

The paper uses a length N_L = 1024, rate R = 1/2 turbo code (Sec. V-A) and, in Fig. 11, a
length-1952 rate-5/6 turbo code decoded with BCJR. Constituent codes here are the 8-state
(13, 15)_8 RSC codes of UMTS/LTE; the paper does not name its constituent code or interleaver.
Parity bits are punctured to reach the target rate; the trellis is not terminated.

All LLRs follow the paper's convention lambda = ln P(bit = 1) / P(bit = 0).
Every routine works on a batch of frames (leading axis B) to keep the Monte Carlo fast.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

N_STATES = 8
NEG_INF = -1e30


def _rsc_tables() -> tuple[np.ndarray, np.ndarray]:
    """Next-state and parity tables of the (13, 15)_8 RSC encoder.

    Shift register (d1, d2, d3), d1 most recent; state = d1*4 + d2*2 + d3.
    Feedback 13_8 = 1 + D^2 + D^3: a = u ^ d2 ^ d3.  Feedforward 15_8 = 1 + D + D^3: p = a ^ d1 ^ d3.
    """
    nxt = np.zeros((N_STATES, 2), dtype=np.int64)
    par = np.zeros((N_STATES, 2), dtype=np.int64)
    for s in range(N_STATES):
        d1, d2, d3 = (s >> 2) & 1, (s >> 1) & 1, s & 1
        for u in range(2):
            a = u ^ d2 ^ d3
            par[s, u] = a ^ d1 ^ d3
            nxt[s, u] = (a << 2) | (d1 << 1) | d2
    return nxt, par


NEXT_STATE, PARITY = _rsc_tables()

# For each next state, its two incoming branches (previous state, input, parity)
_PREV = [[] for _ in range(N_STATES)]
for _s in range(N_STATES):
    for _u in range(2):
        _PREV[NEXT_STATE[_s, _u]].append((_s, _u, PARITY[_s, _u]))
PREV_STATE = np.array([[b[0] for b in _PREV[n]] for n in range(N_STATES)])
PREV_INPUT = np.array([[b[1] for b in _PREV[n]] for n in range(N_STATES)])
PREV_PARITY = np.array([[b[2] for b in _PREV[n]] for n in range(N_STATES)])


def rsc_encode(u: np.ndarray) -> np.ndarray:
    """Parity sequence of the RSC encoder for info bits u of shape (B, K)."""
    u = np.asarray(u, dtype=np.int64)
    s = np.zeros(u.shape[0], dtype=np.int64)
    p = np.empty_like(u)
    for t in range(u.shape[1]):
        p[:, t] = PARITY[s, u[:, t]]
        s = NEXT_STATE[s, u[:, t]]
    return p


def bcjr_maxlog(l_sys: np.ndarray, l_par: np.ndarray, l_apr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Max-log-MAP decoding of one RSC code.

    Args: channel LLRs of the systematic and parity bits and a-priori LLRs of the info
    bits, each (B, K); punctured parity positions carry LLR 0.
    Returns the a-posteriori LLRs of the info bits and of the parity bits, each (B, K).
    """
    l_u = l_sys + l_apr
    B, K = l_u.shape
    # gamma for the four (u, p) branch labels, laid out as index 2*u + p
    g = np.stack([np.zeros_like(l_u), l_par, l_u, l_u + l_par], axis=-1)  # (B, K, 4)
    lab_in = 2 * PREV_INPUT + PREV_PARITY  # (8, 2)

    alpha = np.empty((K + 1, B, N_STATES))
    alpha[0] = NEG_INF
    alpha[0][:, 0] = 0.0
    for t in range(K):
        gt = g[:, t, :]
        a = alpha[t]
        cand = a[:, PREV_STATE] + gt[:, lab_in]  # (B, 8, 2)
        nxt = cand.max(axis=2)
        alpha[t + 1] = nxt - nxt.max(axis=1, keepdims=True)

    beta = np.empty((K + 1, B, N_STATES))
    beta[K] = 0.0  # unterminated trellis
    lab_out = 2 * np.arange(2)[None, :] + PARITY  # (8, 2): label of branch (s, u)
    for t in range(K - 1, -1, -1):
        gt = g[:, t, :]
        cand = beta[t + 1][:, NEXT_STATE] + gt[:, lab_out]  # (B, 8, 2)
        b = cand.max(axis=2)
        beta[t] = b - b.max(axis=1, keepdims=True)

    # branch metrics for all (s, u) at every t: (K, B, 8, 2)
    m = alpha[:-1][:, :, :, None] + np.transpose(g, (1, 0, 2))[:, :, lab_out] + beta[1:][:, :, NEXT_STATE]
    m = np.transpose(m, (1, 0, 2, 3))  # (B, K, 8, 2)
    l_app_u = m[..., 1].max(axis=2) - m[..., 0].max(axis=2)
    par_mask = PARITY.astype(bool)  # (8, 2)
    m_flat = m.reshape(B, K, 16)
    p1 = np.where(par_mask.ravel(), m_flat, NEG_INF).max(axis=2)
    p0 = np.where(~par_mask.ravel(), m_flat, NEG_INF).max(axis=2)
    return l_app_u, p1 - p0


@dataclass
class TurboCode:
    """Rate-adjustable turbo code: systematic bits plus punctured parity of two RSC encoders.

    ``keep1`` / ``keep2`` are the time indices whose parity bits are transmitted.
    The coded word is [sys_0 .. sys_{K-1}, p1[keep1], p2[keep2]] in that order.
    """

    k: int
    keep1: np.ndarray
    keep2: np.ndarray
    interleaver: np.ndarray = field(repr=False)
    deinterleaver: np.ndarray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.deinterleaver = np.argsort(self.interleaver)

    @property
    def n(self) -> int:
        return self.k + len(self.keep1) + len(self.keep2)

    @property
    def rate(self) -> float:
        return self.k / self.n

    @classmethod
    def rate_half(cls, k: int = 1024, seed: int = 7) -> "TurboCode":
        """Rate 1/2: odd/even alternate puncturing of the two parity streams."""
        t = np.arange(k)
        return cls(k, t[t % 2 == 0], t[t % 2 == 1], s_random_interleaver(k, seed))

    @classmethod
    def with_parity_count(cls, k: int, n_parity: int, seed: int = 7) -> "TurboCode":
        """Keep ``n_parity`` parity bits, split evenly and spread uniformly over time."""
        n1 = n_parity // 2
        n2 = n_parity - n1
        keep1 = np.floor(np.arange(n1) * k / n1).astype(np.int64)
        keep2 = np.floor((np.arange(n2) + 0.5) * k / n2).astype(np.int64)
        return cls(k, keep1, keep2, s_random_interleaver(k, seed))

    def encode(self, u: np.ndarray) -> np.ndarray:
        u = np.atleast_2d(np.asarray(u, dtype=np.int64))
        p1 = rsc_encode(u)
        p2 = rsc_encode(u[:, self.interleaver])
        return np.concatenate([u, p1[:, self.keep1], p2[:, self.keep2]], axis=1).astype(np.uint8)


class TurboDecoderState:
    """Turbo decoder whose extrinsic memory persists across calls.

    Persisting the second decoder's extrinsic output lets joint detection and decoding
    (JDD, Fig. 3(c)) run a few decoder sub-iterations per outer iteration without
    restarting the decoder, as the bit-iterative stochastic decoder of the paper does.
    """

    def __init__(self, code: TurboCode, batch: int, ext_scale: float = 0.7) -> None:
        self.code = code
        self.ext_scale = ext_scale  # standard max-log extrinsic scaling
        self.le21 = np.zeros((batch, code.k))

    def reset(self) -> None:
        self.le21[:] = 0.0

    def iterate(self, l_coded: np.ndarray, n_iter: int) -> tuple[np.ndarray, np.ndarray]:
        """Run ``n_iter`` turbo iterations on channel LLRs of the coded bits (B, N).

        Returns (posterior LLRs of the coded bits (B, N), posterior LLRs of the info bits (B, K)).
        """
        c = self.code
        B = l_coded.shape[0]
        l_sys = l_coded[:, : c.k]
        lp1 = np.zeros((B, c.k))
        lp2 = np.zeros((B, c.k))
        lp1[:, c.keep1] = l_coded[:, c.k : c.k + len(c.keep1)]
        lp2[:, c.keep2] = l_coded[:, c.k + len(c.keep1) :]
        app_p1 = app_p2 = None
        le12 = np.zeros_like(l_sys)
        for _ in range(max(1, n_iter)):
            app1, app_p1 = bcjr_maxlog(l_sys, lp1, self.le21)
            le12 = self.ext_scale * (app1 - l_sys - self.le21)
            app2, app_p2 = bcjr_maxlog(l_sys[:, c.interleaver], lp2, le12[:, c.interleaver])
            le2 = self.ext_scale * (app2 - l_sys[:, c.interleaver] - le12[:, c.interleaver])
            self.le21 = le2[:, c.deinterleaver]
        app_u = l_sys + le12 + self.le21
        post = np.concatenate([app_u, app_p1[:, c.keep1], app_p2[:, c.keep2]], axis=1)
        return post, app_u


def s_random_interleaver(k: int, seed: int = 7, s: int | None = None) -> np.ndarray:
    """S-random interleaver (spread s, default floor(sqrt(k/2))) with a random fallback."""
    rng = np.random.default_rng(seed)
    s = int(np.sqrt(k / 2)) if s is None else s
    for _ in range(50):
        pool = list(rng.permutation(k))
        out: list[int] = []
        ok = True
        while pool:
            for idx, cand in enumerate(pool):
                if all(abs(cand - out[-j]) > s for j in range(1, min(s, len(out)) + 1)):
                    out.append(pool.pop(idx))
                    break
            else:
                ok = False
                break
        if ok:
            return np.array(out, dtype=np.int64)
        s = max(1, s - 1)
    return rng.permutation(k)
