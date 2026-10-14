#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sim_mimo import (
    dsc_multiply,
    gibbs_mimo_detect,
    sc_sat_add_bits,
    sc_signed_mul,
    snr_db,
    tdg_multiply,
    tdg_multiply_stream,
    traditional_sc_multiply,
)


def test_signed_mul_truth() -> None:
    assert sc_signed_mul(1, 0, 1, 1) == (1, 1)
    assert sc_signed_mul(1, 1, 1, 1) == (1, 0)
    assert sc_signed_mul(0, 0, 1, 1) == (0, 1)


def test_sat_add_table() -> None:
    z, sat = sc_sat_add_bits(1, 1, 0)
    assert z == 1 and sat == 1
    z, sat = sc_sat_add_bits(1, -1, 1)
    assert z == 1 and sat == 0


def test_tdg_beats_short_random() -> None:
    rng = np.random.default_rng(0)
    refs, tdg, rnd = [], [], []
    for i in range(80):
        x, y = float(rng.uniform(-0.9, 0.9)), float(rng.uniform(-0.9, 0.9))
        refs.append(x * y)
        tdg.append(tdg_multiply(x, y, k=5))
        rnd.append(traditional_sc_multiply(x, y, length=64, seed=i))
    assert snr_db(np.array(refs), np.array(tdg)) > snr_db(
        np.array(refs), np.array(rnd)
    )


def test_tdg_stream_reasonable() -> None:
    x, y = 0.5, -0.25
    assert abs(tdg_multiply_stream(x, y, k=5) - x * y) < 0.2


def test_gibbs_recovers_easy() -> None:
    H = np.eye(2)
    s = np.array([1.0, -1.0])
    y = H @ s
    out = gibbs_mimo_detect(y, H, noise_var=0.01, n_warmup=4, n_outer=4, seed=1)
    assert np.all(out["s_hat"] == s)


def test_icarus() -> None:
    subprocess.check_call(["bash", str(ROOT / "sim" / "run_icarus.sh")])
    assert "mismatches=0" in (ROOT / "sim" / "tb_counts.txt").read_text()


def main() -> None:
    test_signed_mul_truth()
    test_sat_add_table()
    test_tdg_beats_short_random()
    test_tdg_stream_reasonable()
    test_gibbs_recovers_easy()
    # DSC smoke
    assert abs(dsc_multiply(0.5, 0.5, 128) - 0.25) < 0.05
    test_icarus()
    print("ALL TESTS PASS")


if __name__ == "__main__":
    main()
