#!/usr/bin/env python3
"""Generate Icarus stimulus and golden vectors from the Python models.

units_stim.txt / units_gold.txt: one line per clock cycle for the leaf modules
  (sc_signed_mul, sc_sat_add, debruijn_gen, tdg_sng, sc_norm_unit, sc_cas_unit, llr_calculator).
core_stim.txt / core_gold.txt: one command per detector iteration for sim_mimo_detector_core,
  checked against src/sc_detector.py (x, lambda1^e and the 17 TCS counts after every iteration).
All values are written as decimal integers.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.mimo_channel import complex_to_real_mimo, rayleigh_frame  # noqa: E402
from src.sc_detector import StochasticDetector, quantize_inputs, sa  # noqa: E402
from src.sim_mimo import Constellation  # noqa: E402
from src.tdg import debruijn_next, sc_sat_add_bits, sc_signed_mul_bits  # noqa: E402

N_UNIT_CYCLES = 2000
N_CORE_CASES = 6


def gen_units(sim_dir: Path, rng: np.random.Generator) -> None:
    g6 = 1                      # debruijn_gen N=6 SEED=1
    tdg_sat = 0
    integ = 0
    cas = -127
    lpos_max = lneg_max = -127
    with (sim_dir / "units_stim.txt").open("w") as fs, (sim_dir / "units_gold.txt").open("w") as fg:
        for i in range(N_UNIT_CYCLES):
            a_mag, a_sign, b_mag, b_sign = (int(v) for v in rng.integers(0, 2, 4))
            sx, sy, sp = (int(v) for v in rng.integers(-1, 2, 3))
            g6_en = int(rng.integers(0, 2))
            tdg_clr = int(rng.random() < 0.05)
            tdg_sign = int(rng.integers(0, 2))
            tdg_mag = int(rng.integers(0, 1024))
            r6 = int(rng.integers(0, 64)) if rng.random() > 0.2 else 63
            r4 = int(rng.integers(0, 16))
            n_clr = int(rng.random() < 0.05)
            n_in = int(rng.integers(-1, 2))
            cas_clr = int(rng.random() < 0.05)
            cas_en = int(rng.integers(0, 2))
            cas_in = int(rng.integers(-128, 128))
            l_clr = int(rng.random() < 0.05)
            l_upd = int(rng.integers(0, 2))
            x_bit = int(rng.integers(0, 2))
            c_cur = int(rng.integers(0, 65))
            c_flip = int(rng.integers(0, 65))
            rnd = int(rng.integers(0, 64))

            # combinational golden values (before the clock edge)
            zm, zs = sc_signed_mul_bits(a_mag, a_sign, b_mag, b_sign)
            z, sat = sc_sat_add_bits(sx, sy, sp)
            coarse = 1 if (tdg_mag >> 4) > r6 else 0
            fine = 1 if ((tdg_mag & 15) > r4 and r6 == 63) else 0
            tz, tsat_n = sc_sat_add_bits(coarse, fine, tdg_sat)
            tdg_out = -tz if tdg_sign else tz
            s_int = integ + n_in
            fire = 1 if abs(s_int) >= 8 else 0
            c_pos = c_cur if x_bit else c_flip
            c_neg = c_flip if x_bit else c_cur
            l_pos, l_neg = -c_pos, -c_neg

            # register updates (clock edge)
            g6_next = debruijn_next(g6, 6) if g6_en else g6
            tdg_sat = 0 if tdg_clr else tsat_n
            integ = 0 if n_clr else (s_int - 8 * int(np.sign(s_int)) if fire else s_int)
            if cas_clr:
                cas = -127
            elif cas_en and cas_in > cas:
                cas = cas_in
            if l_clr:
                lpos_max = lneg_max = -127
            elif l_upd:
                lpos_max = max(lpos_max, l_pos)
                lneg_max = max(lneg_max, l_neg)
            llr = lpos_max - lneg_max
            llr_sign = 1 if llr < 0 else 0
            llr_mag = 1 if min(abs(llr), 63) > rnd else 0
            g6 = g6_next

            fs.write(
                f"{a_mag} {a_sign} {b_mag} {b_sign} {sx} {sy} {sp} {g6_en} {tdg_clr} {tdg_sign} {tdg_mag} "
                f"{r6} {r4} {n_clr} {n_in} {cas_clr} {cas_en} {cas_in} {l_clr} {l_upd} {x_bit} {c_cur} {c_flip} {rnd}\n"
            )
            fg.write(
                f"{zm} {zs} {z} {sat} {tdg_out} {fire} {l_pos} {l_neg} "
                f"{g6} {cas} {llr} {llr_sign} {llr_mag}\n"
            )


def gen_core(sim_dir: Path, rng: np.random.Generator) -> None:
    const = Constellation(16)
    with (sim_dir / "core_stim.txt").open("w") as fs, (sim_dir / "core_gold.txt").open("w") as fg:
        for case in range(N_CORE_CASES):
            snr = [8.0, 14.0, 20.0, 26.0][case % 4]
            n0 = 4 * 10 ** (-snr / 10)
            bits = rng.integers(0, 2, (1, 16))
            H = rayleigh_frame(1, rng)
            noise = (rng.normal(size=(1, 4)) + 1j * rng.normal(size=(1, 4))) * np.sqrt(n0 / 2)
            y = np.einsum("vrc,vc->vr", H, const.map_complex(bits)) + noise
            y_r, H_r, _ = complex_to_real_mimo(y, H)
            h_q, y_q, _ = quantize_inputs(H_r, y_r, const.levels.max())
            x0 = rng.integers(0, 2, (1, 16))
            r_shift = int(case % 3)
            det = StochasticDetector(h_q, y_q, x0, r_shift=r_shift)
            steps = [("warm", None)] * 3 + [("gsud", rng.integers(0, 2, (1, 16))) for _ in range(2)]
            for n, (mode, dec) in enumerate(steps):
                gsud = mode == "gsud"
                tr = det.run_iteration(gsud, dec)
                rst = 1 if n == 0 else 0
                init = int("".join(str(int(v)) for v in x0[0][::-1]), 2)
                dec_i = 0 if dec is None else int("".join(str(int(v)) for v in dec[0][::-1]), 2)
                fs.write(
                    f"{rst} {int(gsud)} {rst} {rst} {r_shift} {init} {dec_i} "
                    + " ".join(str(int(v)) for v in h_q[0].ravel())
                    + " "
                    + " ".join(str(int(v)) for v in y_q[0])
                    + "\n"
                )
                xi = int("".join(str(int(v)) for v in tr.x[0][::-1]), 2)
                fg.write(
                    f"{xi} " + " ".join(str(int(v)) for v in tr.llr[0]) + " "
                    + " ".join(str(int(v)) for v in tr.counts[0]) + "\n"
                )


def main() -> None:
    sim_dir = Path(__file__).resolve().parent
    rng = np.random.default_rng(42)
    gen_units(sim_dir, rng)
    gen_core(sim_dir, rng)
    print(f"wrote {N_UNIT_CYCLES} unit cycles and {N_CORE_CASES} core cases ({N_CORE_CASES * 5} iterations)")


if __name__ == "__main__":
    main()
