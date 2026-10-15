#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sim_mimo import sc_sat_add_bits, sc_signed_mul


def pack2(v: int) -> int:
    return v & 0x3


def to_signed16(val: int) -> int:
    return val & 0xFFFF


def from_signed16(val: int) -> int:
    val = val & 0xFFFF
    if val >= 0x8000:
        return val - 0x10000
    return val


def main() -> None:
    sim_dir = Path(__file__).resolve().parent
    rng = np.random.default_rng(42)
    n = 512

    # Initial states for sequential models
    cas_max_reg = -32768
    pos_max_reg = -32768
    neg_max_reg = -32768

    with (sim_dir / "stim_sim.hex").open("w") as fs, (sim_dir / "gold_sim.hex").open("w") as fg:
        for i in range(n):
            # Combinational inputs
            a_mag, a_sign, b_mag, b_sign = (int(x) for x in rng.integers(0, 2, size=4))
            sx = int(rng.choice([-1, 0, 1]))
            sy = int(rng.choice([-1, 0, 1]))
            sat_p = int(rng.choice([-1, 0, 1]))
            a_tdg, b_tdg = (int(x) for x in rng.integers(0, 2, size=2))
            reg_in = int(rng.integers(0, 512))

            # Sequential CAS inputs
            cas_clr = 1 if (i % 32 == 0) else 0
            cas_en = 1 if (i % 32 != 0) else 0
            cas_in = int(rng.integers(-500, 500))

            # Sequential LLR inputs
            llr_clr = 1 if (i % 64 == 0) else 0
            llr_eval = 1 if (i % 64 == 32 or i % 64 == 63) else 0
            m_pos = int(rng.integers(-1000, 1000))
            m_neg = int(rng.integers(-1000, 1000))
            rng_val = int(rng.integers(0, 1000))

            # Golden reference evaluations
            zm, zs = sc_signed_mul(a_mag, a_sign, b_mag, b_sign)
            zz, sat = sc_sat_add_bits(sx, sy, sat_p)
            L = 32
            reg_out = reg_in + (L if a_tdg else 0) + (1 if b_tdg else 0)

            # Update CAS model
            if cas_clr:
                cas_max_reg = cas_in
            elif cas_en:
                if cas_in >= cas_max_reg:
                    cas_max_reg = cas_in

            # Update LLR model
            if llr_clr:
                pos_max_reg = m_pos
                neg_max_reg = m_neg
            elif llr_eval:
                if m_pos >= pos_max_reg:
                    pos_max_reg = m_pos
                if m_neg >= neg_max_reg:
                    neg_max_reg = m_neg

            llr_val = pos_max_reg - neg_max_reg
            llr_sign = 1 if llr_val < 0 else 0
            abs_llr = abs(llr_val) & 0x7FFF
            llr_mag = 1 if abs_llr > rng_val else 0

            # Pack stimulus
            stim_lo = (
                (a_mag << 0)
                | (a_sign << 1)
                | (b_mag << 2)
                | (b_sign << 3)
                | (pack2(sx) << 4)
                | (pack2(sy) << 6)
                | (pack2(sat_p) << 8)
                | (a_tdg << 10)
                | (b_tdg << 11)
                | ((reg_in & 0x7FF) << 12)
                | (cas_clr << 23)
                | (cas_en << 24)
                | (to_signed16(cas_in) << 25)
                | (llr_clr << 41)
                | (llr_eval << 42)
            )

            stim_hi = (
                to_signed16(m_pos)
                | (to_signed16(m_neg) << 16)
                | ((rng_val & 0x7FFF) << 32)
            )

            # Pack golden
            gold_lo = (
                (zm << 0)
                | (zs << 1)
                | (pack2(zz) << 2)
                | (pack2(sat) << 4)
                | ((reg_out & 0x7FF) << 6)
                | (to_signed16(cas_max_reg) << 17)
            )

            gold_hi = (
                to_signed16(llr_val)
                | (llr_sign << 16)
                | (llr_mag << 17)
            )

            fs.write(f"{stim_hi:016x} {stim_lo:016x}\n")
            fg.write(f"{gold_hi:016x} {gold_lo:016x}\n")

    print(f"wrote {n} vectors to stim_sim.hex and gold_sim.hex")


if __name__ == "__main__":
    main()
