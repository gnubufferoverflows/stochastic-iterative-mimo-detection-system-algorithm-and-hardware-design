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


def main() -> None:
    sim = Path(__file__).resolve().parent
    rng = np.random.default_rng(5)
    n = 512
    with (sim / "stim_sim.hex").open("w") as fs, (sim / "gold_sim.hex").open("w") as fg:
        for _ in range(n):
            a_mag, a_sign, b_mag, b_sign = (int(x) for x in rng.integers(0, 2, size=4))
            sx = int(rng.choice([-1, 0, 1]))
            sy = int(rng.choice([-1, 0, 1]))
            sat_p = int(rng.choice([-1, 0, 1]))
            a_tdg, b_tdg = (int(x) for x in rng.integers(0, 2, size=2))
            reg_in = int(rng.integers(0, 512))
            zm, zs = sc_signed_mul(a_mag, a_sign, b_mag, b_sign)
            zz, sat = sc_sat_add_bits(sx, sy, sat_p)
            L = 32
            reg_out = reg_in + (L if a_tdg else 0) + (1 if b_tdg else 0)
            stim = (
                (a_mag << 31)
                | (a_sign << 30)
                | (b_mag << 29)
                | (b_sign << 28)
                | (pack2(sx) << 26)
                | (pack2(sy) << 24)
                | (pack2(sat_p) << 22)
                | (a_tdg << 21)
                | (b_tdg << 20)
                | ((reg_in & 0x7FF) << 9)
            )
            gold = (
                (zm << 31)
                | (zs << 30)
                | (pack2(zz) << 28)
                | (pack2(sat) << 26)
                | ((reg_out & 0x7FF) << 15)
            )
            fs.write(f"{stim:08x}\n")
            fg.write(f"{gold:08x}\n")
    print(f"wrote {n} vectors")


if __name__ == "__main__":
    main()
