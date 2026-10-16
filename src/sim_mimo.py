"""Stochastic Iterative MIMO (SIM) detection: algorithm model and coded system simulator.

Floating-point model of Sec. III of Chen, Hu, Sobelman, TCAS-I 2015:
- Warm-up processing, Eqs. (7)-(9): every bit of the sample is updated in parallel from the
  current sample by x = [l+ - l- + R > 0] (Eq. 8), R a zero-mean random signal; the LLR is the
  difference of the running maxima of l+ and l- over the visited samples (Eq. 9, CAS of Eq. 18).
- GsUD processing, Eqs. (10)-(14): the sample is replaced by the decoder's hard decisions,
  l+- = +-lambda2^e / 2 - ||y - H s+-||^2 / sigma^2 (Eq. 12) and lambda1 = max l+ - max l- (Eq. 13).
- Parallel LLR calculation, Eqs. (15)-(17): d = y - Hs is computed once and every single-bit
  hypothesis reuses it, d_flip = d - H(:, k) (s_flip - s_k).

The decoder receives the extrinsic part lambda1^e = lambda1 - lambda2^e and returns its
posterior lambda2, from which lambda2^e = lambda2 - lambda1^e (Fig. 6).

Reference detectors for the iterative (IDD) comparisons of Fig. 10 / Fig. 11:
- ``LogMapDetector``: exhaustive soft-input soft-output Log-MAP (16-QAM, 4x4 only)
- ``MmsePicDetector``: soft MMSE parallel interference cancellation
- ``KBestDetector``: real-valued soft-output K-best list detector
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .channel_code import TurboCode, TurboDecoderState
from .mimo_channel import TGnChannelC, complex_to_real_mimo, compute_noise_var, rayleigh_frame

LLR_CLIP = 20.0


# ------------------------------------------------------------------------------
# Constellation helpers (Gray PAM per real dimension, Eq. 11)
# ------------------------------------------------------------------------------

@dataclass
class Constellation:
    """Square QAM as two Gray-coded PAM dimensions with unit average complex energy.

    Bit layout of a transmit vector: antenna i carries bits [re_0 .. re_{q-1}, im_0 .. im_{q-1}],
    q = log2(M) / 2. Real dimension i holds Re(s_i) and dimension Nt + i holds Im(s_i)
    (the ordering of ``complex_to_real_mimo``).
    """

    mod_order: int
    n_t: int = 4
    q: int = field(init=False)
    levels: np.ndarray = field(init=False)
    labels: np.ndarray = field(init=False)
    lut: np.ndarray = field(init=False)

    def __post_init__(self) -> None:
        self.q = int(np.log2(self.mod_order)) // 2
        n_lvl = 1 << self.q
        amp = np.arange(-(n_lvl - 1), n_lvl, 2, dtype=float)
        scale = 1.0 / np.sqrt(2.0 * np.mean(amp ** 2))
        gray = np.arange(n_lvl) ^ (np.arange(n_lvl) >> 1)
        # Bits of level index i (ascending amplitude) are the Gray code of i:
        # 16-QAM 00->-3, 01->-1, 11->+1, 10->+3; 64-QAM 000->-7 ... 100->+7 (src/qam.py, Fig. 7).
        code = gray
        self.levels = amp * scale
        self.labels = np.array([[(c >> (self.q - 1 - b)) & 1 for b in range(self.q)] for c in code], dtype=np.int64)
        self.lut = np.zeros(n_lvl)
        for i, c in enumerate(code):
            self.lut[c] = self.levels[i]

    @property
    def bits_per_vector(self) -> int:
        return 2 * self.q * self.n_t

    @property
    def es_dim(self) -> float:
        return 0.5

    def bit_dim_pos(self) -> tuple[np.ndarray, np.ndarray]:
        """Real dimension and position within the PAM label of every bit of a vector."""
        dims, pos = [], []
        for i in range(self.n_t):
            for part in range(2):
                for b in range(self.q):
                    dims.append(i + part * self.n_t)
                    pos.append(b)
        return np.array(dims), np.array(pos)

    def map_real(self, bits: np.ndarray) -> np.ndarray:
        """Bits (V, nb) -> real-valued symbol vectors (V, 2 Nt)."""
        V = bits.shape[0]
        b = bits.reshape(V, self.n_t, 2, self.q)
        w = 1 << np.arange(self.q - 1, -1, -1)
        idx = (b * w).sum(axis=-1)  # (V, Nt, 2)
        vals = self.lut[idx]
        return np.concatenate([vals[:, :, 0], vals[:, :, 1]], axis=1)

    def map_complex(self, bits: np.ndarray) -> np.ndarray:
        s = self.map_real(bits)
        return s[:, : self.n_t] + 1j * s[:, self.n_t :]


# ------------------------------------------------------------------------------
# SIM detector (Eqs. 7-18)
# ------------------------------------------------------------------------------

class SimDetector:
    """Batched floating-point SIM detector for V MIMO vectors.

    ``cas_scope``: "global" keeps the CAS maxima of Eq. (18) across warm-up and all GsUD
    iterations; "iteration" restarts them at every GsUD iteration.
    ``r_temp``: scale of the zero-mean random signal R of Eq. (8). R is logistic, which makes
    [l+ - l- + R > 0] an exact draw from P(x = 1) = sigmoid((l+ - l-) / r_temp).
    ``init``: initial sample, "random" (Sec. II-A) or "mmse" (linear MMSE hard decisions).
    """

    def __init__(
        self,
        y_r: np.ndarray,
        H_r: np.ndarray,
        noise_var: float,
        const: Constellation,
        rng: np.random.Generator,
        r_temp: float = 1.0,
        cas_scope: str = "global",
        init: str = "random",
    ) -> None:
        self.y, self.H, self.n0 = y_r, H_r, noise_var
        self.c = const
        self.rng = rng
        self.r_temp = r_temp
        self.cas_scope = cas_scope
        self.dims, self.pos = const.bit_dim_pos()
        V = y_r.shape[0]
        nb = const.bits_per_vector
        if init == "random":
            self.x = rng.integers(0, 2, size=(V, nb))
        elif init == "zeros":
            self.x = np.zeros((V, nb), dtype=np.int64)
        elif init == "mmse":
            self.x = self._mmse_bits()
        else:
            raise ValueError(init)
        self.lmax1 = np.full((V, nb), -np.inf)
        self.lmax0 = np.full((V, nb), -np.inf)

    def _mmse_bits(self) -> np.ndarray:
        """Hard decisions of a linear MMSE estimate, used as the initial sample."""
        Ht = self.H.transpose(0, 2, 1)
        G = Ht @ self.H + (self.n0 / 2.0) / self.c.es_dim * np.eye(self.H.shape[2])
        s_hat = np.linalg.solve(G, np.einsum("vji,vj->vi", self.H, self.y)[..., None])[..., 0]
        lvl = np.argmin(np.abs(s_hat[..., None] - self.c.levels), axis=-1)  # (V, 2Nt)
        lab = self.c.labels[lvl]  # (V, 2Nt, q)
        n_t = self.c.n_t
        return np.concatenate([lab[:, :n_t], lab[:, n_t:]], axis=2).reshape(self.y.shape[0], -1)

    def hypothesis_distances(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """||y - H s+||^2 and ||y - H s-||^2 for every bit, via Eqs. (15)-(17)."""
        s = self.c.map_real(x)
        d = self.y - np.einsum("vij,vj->vi", self.H, s)  # Eq. (15)
        cur = np.sum(d ** 2, axis=1)  # (V,)
        x_flip = x.copy()
        # value of the flipped symbol for each bit
        V, nb = x.shape
        s_flip = np.empty((V, nb))
        q = self.c.q
        w = 1 << np.arange(q - 1, -1, -1)
        for j in range(nb):
            dim, pos = self.dims[j], self.pos[j]
            ant = dim % self.c.n_t
            part = dim // self.c.n_t
            base = ant * 2 * q + part * q
            lab = x[:, base : base + q].copy()
            lab[:, pos] ^= 1
            s_flip[:, j] = self.c.lut[(lab * w).sum(axis=1)]
        delta = s_flip - s[:, self.dims]  # s_{+-k,b} difference, Eq. (17)
        d_flip = d[:, None, :] - self.H[:, :, self.dims].transpose(0, 2, 1) * delta[:, :, None]
        flip = np.sum(d_flip ** 2, axis=2)  # (V, nb)
        del x_flip
        dist1 = np.where(x == 1, cur[:, None], flip)
        dist0 = np.where(x == 0, cur[:, None], flip)
        return dist1, dist0

    def _channel_metrics(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Channel part of Eqs. (7) / (12): -||y - H s+-||^2 / sigma^2 for every bit."""
        dist1, dist0 = self.hypothesis_distances(x)
        return -dist1 / self.n0, -dist0 / self.n0

    def _cas(self, l1: np.ndarray, l0: np.ndarray, restart: bool) -> np.ndarray:
        """Eq. (18) on the channel metrics; returns max l+ - max l- without the prior.

        lambda2^{e+-}(x_kb) depends only on the bit itself, so it is the same for every
        sample in the max of Eq. (13) and is added after the CAS:
        lambda1 = lambda2^e + max(ch+) - max(ch-). Keeping it inside the CAS registers would
        mix priors from different iterations.
        """
        if restart:
            self.lmax1, self.lmax0 = l1.copy(), l0.copy()
        else:
            self.lmax1 = np.maximum(self.lmax1, l1)
            self.lmax0 = np.maximum(self.lmax0, l0)
        return np.clip(self.lmax1 - self.lmax0, -LLR_CLIP, LLR_CLIP)

    def warmup(self, n_warmup: int) -> np.ndarray:
        """Warm-up processing; returns lambda1 (Eq. 9)."""
        lam = np.zeros_like(self.lmax1)
        for _ in range(n_warmup):
            l1, l0 = self._channel_metrics(self.x)  # lambda2^e = 0 during warm-up
            lam = self._cas(l1, l0, restart=False)
            r = self.rng.logistic(0.0, self.r_temp, size=l1.shape)
            self.x = ((l1 - l0 + r) > 0).astype(np.int64)  # Eq. (8)
        return lam

    def gsud(self, x_dec: np.ndarray, l2e: np.ndarray) -> np.ndarray:
        """One GsUD iteration with decoder bits (Eq. 10).

        Returns the extrinsic LLR lambda1^e = lambda1 - lambda2^e = max ch+ - max ch-.
        """
        self.x = x_dec.astype(np.int64)
        l1, l0 = self._channel_metrics(self.x)
        return self._cas(l1, l0, restart=self.cas_scope == "iteration")


# ------------------------------------------------------------------------------
# Reference SISO detectors
# ------------------------------------------------------------------------------

class LogMapDetector:
    """Exhaustive soft-input soft-output Log-MAP detector (Fig. 10 'Optimal Log-MAP' [27])."""

    def __init__(self, y_r, H_r, noise_var, const: Constellation, chunk: int = 16) -> None:
        nb = const.bits_per_vector
        if nb > 16:
            raise ValueError("exhaustive Log-MAP is limited to 2^16 candidates")
        self.y, self.H, self.n0, self.chunk = y_r, H_r, noise_var, chunk
        cand = (np.arange(1 << nb)[:, None] >> np.arange(nb - 1, -1, -1)) & 1
        self.bits = cand.astype(np.float64)
        self.S = const.map_real(cand)

    def detect(self, l2e: np.ndarray) -> np.ndarray:
        V = self.y.shape[0]
        out = np.empty_like(l2e)
        for a in range(0, V, self.chunk):
            sl = slice(a, a + self.chunk)
            hs = np.matmul(self.S[None], self.H[sl].transpose(0, 2, 1))  # (v, cand, 2Nr)
            hs -= self.y[sl][:, None, :]
            dist = np.einsum("vcr,vcr->vc", hs, hs)
            metric = -dist / self.n0 + l2e[sl] @ self.bits.T
            metric -= metric.max(axis=1, keepdims=True)
            e = np.exp(metric)
            num = e @ self.bits
            den = e @ (1.0 - self.bits)
            out[sl] = np.log(num + 1e-300) - np.log(den + 1e-300) - l2e[sl]
        return np.clip(out, -LLR_CLIP, LLR_CLIP)


class MmsePicDetector:
    """Soft-input soft-output MMSE parallel interference cancellation (Fig. 10 'MMSE-PIC' [8])."""

    def __init__(self, y_r, H_r, noise_var, const: Constellation) -> None:
        self.y, self.H, self.n0, self.c = y_r, H_r, noise_var, const
        self.dims, self.pos = const.bit_dim_pos()

    def _pam_logprior(self, l2e: np.ndarray) -> np.ndarray:
        """Log-prior of every PAM level of every real dimension, (V, 2Nt, levels)."""
        c = self.c
        V = l2e.shape[0]
        lp = np.zeros((V, 2 * c.n_t, len(c.levels)))
        for j in range(l2e.shape[1]):
            d, p = self.dims[j], self.pos[j]
            lp[:, d, :] += np.where(c.labels[:, p][None, :] == 1, 0.5, -0.5) * l2e[:, j : j + 1]
        return lp

    def detect(self, l2e: np.ndarray) -> np.ndarray:
        c = self.c
        lp = self._pam_logprior(l2e)
        pr = np.exp(lp - lp.max(axis=2, keepdims=True))
        pr /= pr.sum(axis=2, keepdims=True)
        m = pr @ c.levels
        v = np.clip(pr @ c.levels ** 2 - m ** 2, 1e-9, None)
        sig2 = self.n0 / 2.0
        nr2 = self.H.shape[1]
        C = np.einsum("vik,vk,vjk->vij", self.H, v, self.H) + sig2 * np.eye(nr2)
        resid = self.y - np.einsum("vij,vj->vi", self.H, m)
        Cinv = np.linalg.inv(C)
        out = np.empty_like(l2e)
        for k in range(2 * c.n_t):
            h = self.H[:, :, k]
            # C_k = C + (Es - v_k) h h^T, inverted with Sherman-Morrison
            a = c.es_dim - v[:, k]
            Ch = np.einsum("vij,vj->vi", Cinv, h)
            hCh = np.sum(h * Ch, axis=1)
            w = Ch / (1.0 + a * hCh)[:, None]
            mu = np.sum(w * h, axis=1)
            z = np.sum(w * (resid + h * m[:, k : k + 1]), axis=1)
            var = np.clip((1.0 - c.es_dim * mu) / np.clip(mu, 1e-9, None), 1e-9, None)
            zs = z / np.clip(mu, 1e-9, None)
            ll = -((zs[:, None] - c.levels[None, :]) ** 2) / (2.0 * var[:, None])  # (V, levels)
            for j in np.where(self.dims == k)[0]:
                p = self.pos[j]
                own = np.where(c.labels[:, p][None, :] == 1, 0.5, -0.5) * l2e[:, j : j + 1]
                tot = ll + lp[:, k, :] - own
                one = c.labels[:, p] == 1
                out[:, j] = _lse(tot[:, one]) - _lse(tot[:, ~one])
        return np.clip(out, -LLR_CLIP, LLR_CLIP)


class KBestDetector:
    """Real-valued soft-output K-best detector with a-priori information (Fig. 10 'K-best' [10])."""

    def __init__(self, y_r, H_r, noise_var, const: Constellation, k: int = 32) -> None:
        self.c, self.n0, self.k = const, noise_var, k
        self.dims, self.pos = const.bit_dim_pos()
        Q, R = np.linalg.qr(H_r)
        self.R = R
        self.yt = np.einsum("vji,vj->vi", Q, y_r)

    def detect(self, l2e: np.ndarray) -> np.ndarray:
        c = self.c
        V = self.yt.shape[0]
        n = 2 * c.n_t
        n_lvl = len(c.levels)
        # per-dimension prior cost of each level (minus log prior up to a constant)
        prior = np.zeros((V, n, n_lvl))
        for j in range(l2e.shape[1]):
            d, p = self.dims[j], self.pos[j]
            prior[:, d, :] -= np.where(c.labels[:, p][None, :] == 1, 0.5, -0.5) * l2e[:, j : j + 1]
        paths = np.zeros((V, 1, 0), dtype=np.int64)
        cost = np.zeros((V, 1))
        for lvl in range(n - 1, -1, -1):
            K = paths.shape[1]
            idx = np.arange(n_lvl)
            new_paths = np.concatenate(
                [np.repeat(paths, n_lvl, axis=1), np.tile(idx, K)[None, :, None].repeat(V, 0)], axis=2
            )  # columns ordered from dimension n-1 down to lvl
            sym = c.levels[new_paths]  # (V, K*lvl, depth)
            rrow = self.R[:, lvl, lvl:][:, ::-1]  # matches column order n-1 .. lvl
            e = self.yt[:, lvl][:, None] - np.einsum("vkd,vd->vk", sym, rrow)
            inc = e ** 2 / (self.n0 / 2.0) * 0.5 + np.take_along_axis(prior[:, lvl, :], new_paths[:, :, -1], axis=1)
            new_cost = np.repeat(cost, n_lvl, axis=1) + inc
            keep = min(self.k, new_cost.shape[1])
            sel = np.argpartition(new_cost, keep - 1, axis=1)[:, :keep]
            paths = np.take_along_axis(new_paths, sel[:, :, None], axis=1)
            cost = np.take_along_axis(new_cost, sel, axis=1)
        lvl_idx = paths[:, :, ::-1]  # (V, K, n) in dimension order 0..n-1
        out = np.empty_like(l2e)
        for j in range(l2e.shape[1]):
            d, p = self.dims[j], self.pos[j]
            bit = c.labels[lvl_idx[:, :, d], p]
            c1 = np.where(bit == 1, cost, np.inf).min(axis=1)
            c0 = np.where(bit == 0, cost, np.inf).min(axis=1)
            own = 0.5 * l2e[:, j]
            # cost includes -(+-0.5 lambda2e) of this bit; remove it for the extrinsic value
            lam = (c0 - own) - (c1 + own)
            out[:, j] = np.where(np.isinf(c1), -LLR_CLIP, np.where(np.isinf(c0), LLR_CLIP, lam))
        return np.clip(out, -LLR_CLIP, LLR_CLIP)


def _lse(a: np.ndarray) -> np.ndarray:
    m = a.max(axis=1)
    return m + np.log(np.sum(np.exp(a - m[:, None]), axis=1))


# ------------------------------------------------------------------------------
# Coded system simulation (JDD for SIM, IDD for the reference detectors)
# ------------------------------------------------------------------------------

@dataclass
class SystemConfig:
    detector: str = "sim"           # "sim", "logmap", "mmse_pic", "kbest"
    mod_order: int = 16
    n_t: int = 4
    n_r: int = 4
    code_k: int = 1024
    code_parity: int | None = None  # None -> rate 1/2 (alternate puncturing)
    channel: str = "tgnc"            # "tgnc" or "rayleigh"
    n_outer: int = 12                # decoder invocations (N_itera)
    n_warmup: int = 8                # SIM warm-up iterations
    n_dec_iter: int = 1              # turbo iterations per outer iteration
    reset_decoder: bool = False      # True for IDD (decoder restarts each outer iteration)
    r_temp: float = 1.0              # scale of the logistic random signal R of Eq. (8)
    gsud_bits: str = "hard"          # "hard": sign of lambda2; "sample": x ~ sigmoid(lambda2)
    cas_scope: str = "global"
    init: str = "random"
    kbest_k: int = 32


def build_code(cfg: SystemConfig) -> TurboCode:
    if cfg.code_parity is None:
        return TurboCode.rate_half(cfg.code_k)
    return TurboCode.with_parity_count(cfg.code_k, cfg.code_parity)


def simulate_frames(
    cfg: SystemConfig, eb_n0_db: float, n_frames: int, batch: int = 50, seed: int = 0
) -> dict:
    """Monte Carlo of the coded MIMO link.

    Returns per-outer-iteration frame/bit error counts and, per frame, the first outer
    iteration at which all information bits were decoded correctly (0 if never).
    """
    rng = np.random.default_rng(seed)
    code = build_code(cfg)
    const = Constellation(cfg.mod_order, cfg.n_t)
    nb = const.bits_per_vector
    n_vec = int(np.ceil(code.n / nb))
    n_pad = n_vec * nb - code.n
    chan_perm = np.random.default_rng(12345).permutation(code.n)
    chan_inv = np.argsort(chan_perm)
    n0 = compute_noise_var(eb_n0_db, cfg.mod_order, code.rate, cfg.n_t)
    tgn = TGnChannelC(cfg.n_r, cfg.n_t) if cfg.channel == "tgnc" else None

    fe = np.zeros(cfg.n_outer, dtype=np.int64)
    be = np.zeros(cfg.n_outer, dtype=np.int64)
    first_ok: list[int] = []
    done = 0
    while done < n_frames:
        B = min(batch, n_frames - done)
        u = rng.integers(0, 2, size=(B, code.k))
        cw = code.encode(u).astype(np.int64)
        tx = np.concatenate([cw[:, chan_perm], np.zeros((B, n_pad), dtype=np.int64)], axis=1)
        bits_v = tx.reshape(B * n_vec, nb)
        s = const.map_complex(bits_v)
        if tgn is not None:
            H = np.concatenate([tgn.frame(n_vec, rng) for _ in range(B)])
        else:
            H = rayleigh_frame(B * n_vec, rng, cfg.n_r, cfg.n_t)
        noise = (rng.normal(size=(B * n_vec, cfg.n_r)) + 1j * rng.normal(size=(B * n_vec, cfg.n_r))) * np.sqrt(n0 / 2)
        y = np.einsum("vrc,vc->vr", H, s) + noise
        y_r, H_r, _ = complex_to_real_mimo(y, H)

        pad_prior = np.full((B, n_pad), -LLR_CLIP)

        def to_vectors(coded: np.ndarray, pad: np.ndarray) -> np.ndarray:
            return np.concatenate([coded[:, chan_perm], pad], axis=1).reshape(B * n_vec, nb)

        def to_codeword(vec: np.ndarray) -> np.ndarray:
            return vec.reshape(B, n_vec * nb)[:, : code.n][:, chan_inv]

        dec = TurboDecoderState(code, B)
        ok_at = np.zeros(B, dtype=np.int64)
        if cfg.detector == "sim":
            det = SimDetector(y_r, H_r, n0, const, rng, cfg.r_temp, cfg.cas_scope, cfg.init)
            lam1e = det.warmup(cfg.n_warmup)
        else:
            det = {
                "logmap": lambda: LogMapDetector(y_r, H_r, n0, const),
                "mmse_pic": lambda: MmsePicDetector(y_r, H_r, n0, const),
                "kbest": lambda: KBestDetector(y_r, H_r, n0, const, cfg.kbest_k),
            }[cfg.detector]()
            lam1e = det.detect(np.zeros((B * n_vec, nb)))

        for it in range(cfg.n_outer):
            l_in = to_codeword(lam1e)
            if cfg.reset_decoder:
                dec.reset()
            post, app_u = dec.iterate(l_in, cfg.n_dec_iter)
            err = (app_u > 0).astype(np.int64) != u
            n_err = err.sum(axis=1)
            fe[it] += int(np.sum(n_err > 0))
            be[it] += int(n_err.sum())
            newly = (ok_at == 0) & (n_err == 0)
            ok_at[newly] = it + 1
            if it == cfg.n_outer - 1:
                break
            l2e = np.clip(post - l_in, -LLR_CLIP, LLR_CLIP)
            l2e_v = to_vectors(l2e, pad_prior)
            if cfg.detector == "sim":
                if cfg.gsud_bits == "sample":
                    # a stochastic decoder emits its decoded bit as a random stream whose
                    # mean is the bit posterior; one bit of that stream is one sample
                    hard = (rng.random(post.shape) < 1.0 / (1.0 + np.exp(-post))).astype(np.int64)
                else:
                    hard = (post > 0).astype(np.int64)
                x_dec = to_vectors(hard, np.zeros((B, n_pad), dtype=np.int64))
                lam1e = det.gsud(x_dec, l2e_v)
            else:
                lam1e = det.detect(l2e_v)
        first_ok.extend(ok_at.tolist())
        done += B

    return {
        "eb_n0_db": eb_n0_db,
        "n_frames": n_frames,
        "info_bits": code.k,
        "frame_errors": fe.tolist(),
        "bit_errors": be.tolist(),
        "fer": (fe / n_frames).tolist(),
        "ber": (be / (n_frames * code.k)).tolist(),
        "first_correct_iteration": first_ok,
    }
