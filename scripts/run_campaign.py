#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sim_mimo import (
    dsc_multiply,
    simulate_ber,
    snr_db,
    tdg_multiply,
    tdg_multiply_stream,
    traditional_sc_multiply,
)


def table2_style(n_trials: int = 300, seed: int = 0) -> dict:
    """Table II-style mul SNR (paper cells REFERENCE ONLY)."""
    rng = np.random.default_rng(seed)
    refs = []
    buckets = {
        "random_1024": [],
        "dsc_1024": [],
        "dsc_64": [],
        "tdg_exact_k5": [],
        "tdg_stream_k5": [],
        "random_64": [],
    }
    for i in range(n_trials):
        x, y = float(rng.uniform(-0.95, 0.95)), float(rng.uniform(-0.95, 0.95))
        refs.append(x * y)
        buckets["random_1024"].append(traditional_sc_multiply(x, y, 1024, seed=i))
        buckets["dsc_1024"].append(dsc_multiply(x, y, 1024))
        buckets["dsc_64"].append(dsc_multiply(x, y, 64))
        buckets["tdg_exact_k5"].append(tdg_multiply(x, y, k=5))
        buckets["tdg_stream_k5"].append(tdg_multiply_stream(x, y, k=5))
        buckets["random_64"].append(traditional_sc_multiply(x, y, 64, seed=i + 7))
    r = np.array(refs)
    return {k: snr_db(r, np.array(v)) for k, v in buckets.items()}


def main() -> None:
    out = ROOT / "benchmarks" / "results"
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "paper_doi": "10.1109/TCSI.2015.2390558",
        "note": (
            "Measured TDG/DSC/random mul SNR and 2x2 BPSK SIM BER. "
            "Tables III–IV 130 nm ASIC and 4x4 16-QAM FER are REFERENCE ONLY."
        ),
        "mul_snr_db": table2_style(),
        "paper_table2_reference_db": {
            "random_1024": 43.0,
            "dsc_1024": 57.8,
            "dsc_64": 34.1,
            "swg_64": 27.8,
            "tdg_64": 39.1,
        },
        "ber_2x2_bpsk": simulate_ber(
            [0, 4, 8, 12], n_tx=2, n_frames=300, n_warmup=8, n_outer=12, seed=3
        ),
    }
    path = out / "sim_campaign.json"
    path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
