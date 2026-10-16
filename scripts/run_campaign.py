#!/usr/bin/env python3
"""Monte Carlo campaign for the SIM detection system (Chen, Hu, Sobelman, TCAS-I 2015).

Parts (run separately with --part, merged into benchmarks/results/sim_campaign.json by --merge):
  table2  Table II stochastic multiplier SNR
  fig10a  4x4 16-QAM, rate-1/2 length-1024 turbo code, TGn-C: FER of SIM vs Log-MAP, MMSE-PIC, K-best
  fig10b  4x4 64-QAM, same code: SIM vs MMSE-PIC, K-best
  fig9    SIM iteration-count histograms (first outer iteration with all info bits correct)
  fig11   4x4 16-QAM, rate ~5/6 length-1952 turbo code (BCJR), BER vs outer iterations
  table4  Table IV values transcribed from the paper (not simulated)

Detector/decoder schedules:
  SIM (JDD): N_warm-up = 8 warm-up iterations, then N_itera decoder invocations; the turbo
    decoder keeps its state and runs one turbo iteration per outer iteration (a 64-cycle
    stochastic sub-iteration of the paper is mapped to one floating-point turbo iteration).
  Reference detectors (IDD): 4 outer iterations, the decoder restarts and runs 8 turbo
    iterations each time (the paper's 256-cycle decoding for traditional detectors).
Frame counts are far below the paper's 10K frames; FER below ~1/n_frames is not resolved.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.sim_mimo import SystemConfig, simulate_frames  # noqa: E402
from src.tdg import run_table2_benchmark  # noqa: E402

OUT = ROOT / "benchmarks" / "results"


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def sweep(label: str, cfg: SystemConfig, snrs: list[float], n_frames: int, batch: int, seed: int) -> dict:
    curve = {"label": label, "config": cfg.__dict__.copy(), "snr_db": [], "fer": [], "ber": [],
             "fer_per_iteration": [], "n_frames": n_frames}
    for snr in snrs:
        t = time.time()
        r = simulate_frames(cfg, snr, n_frames, batch=batch, seed=seed)
        curve["snr_db"].append(snr)
        curve["fer"].append(r["fer"][-1])
        curve["ber"].append(r["ber"][-1])
        curve["fer_per_iteration"].append(r["fer"])
        log(f"{label:34s} {snr:5.1f} dB FER={r['fer'][-1]:.4f} BER={r['ber'][-1]:.2e} ({time.time() - t:.0f}s)")
    return curve


def part_table2() -> dict:
    return run_table2_benchmark(n_trials=2000, seed=42)


_SNR_10A = [6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0]
_IDD = dict(n_outer=4, n_dec_iter=8, reset_decoder=True)
# (label, config, SNR points, frame-count divisor, batch)
FIG10A_CURVES = [
    ("SIM N_itera=12 (paper: random init)", SystemConfig("sim", n_outer=12), _SNR_10A, 1, 100),
    ("SIM N_itera=8 (paper: random init)", SystemConfig("sim", n_outer=8), _SNR_10A, 1, 100),
    ("SIM N_itera=12, MMSE init (variant)", SystemConfig("sim", n_outer=12, init="mmse"), _SNR_10A, 1, 100),
    ("MMSE-PIC (itera=4)", SystemConfig("mmse_pic", **_IDD), _SNR_10A, 1, 100),
    ("K-best K=32 (itera=4)", SystemConfig("kbest", kbest_k=32, **_IDD), _SNR_10A, 1, 100),
    ("Log-MAP (itera=4)", SystemConfig("logmap", **_IDD), [6.0, 6.5, 7.0, 7.5, 8.0], 2, 20),
]
FIG10A_META = {"modulation": "16-QAM", "code": "turbo R=1/2 K=1024", "channel": "TGn C"}


def part_fig10a(n_frames: int) -> dict:
    curves = [sweep(lbl, cfg, snrs, max(40, n_frames // div), b, 1) for lbl, cfg, snrs, div, b in FIG10A_CURVES]
    return {**FIG10A_META, "curves": curves}


def run_job(curve: int, snr: float, n_frames: int) -> None:
    """Run one (curve, SNR) point of Fig. 10(a); --merge assembles the jobs."""
    lbl, cfg, _, div, b = FIG10A_CURVES[curve]
    res = sweep(lbl, cfg, [snr], max(40, n_frames // div), b, 1)
    (OUT / f"job_fig10a_{curve}_{snr:.1f}.json").write_text(json.dumps(res) + "\n")


def assemble_fig10a_jobs() -> dict | None:
    curves = []
    for i, (lbl, cfg, snrs, div, b) in enumerate(FIG10A_CURVES):
        pts = [OUT / f"job_fig10a_{i}_{x:.1f}.json" for x in snrs]
        if not all(p.exists() for p in pts):
            return None
        rs = [json.loads(p.read_text()) for p in pts]
        c = rs[0]
        for r in rs[1:]:
            for k in ("snr_db", "fer", "ber", "fer_per_iteration"):
                c[k] += r[k]
        curves.append(c)
    return {**FIG10A_META, "curves": curves}


def part_fig10b(n_frames: int) -> dict:
    snr = [11.0, 13.0, 15.0, 17.0, 19.0]
    idd = dict(mod_order=64, n_outer=4, n_dec_iter=8, reset_decoder=True)
    curves = [
        sweep("SIM N_itera=24 (paper: random init)", SystemConfig("sim", mod_order=64, n_outer=24), snr, n_frames, 50, 2),
        sweep("SIM N_itera=12 (paper: random init)", SystemConfig("sim", mod_order=64, n_outer=12), snr, n_frames, 50, 2),
        sweep("SIM N_itera=24, MMSE init (variant)", SystemConfig("sim", mod_order=64, n_outer=24, init="mmse"), snr, n_frames, 50, 2),
        sweep("MMSE-PIC (itera=4)", SystemConfig("mmse_pic", **idd), snr, n_frames, 50, 2),
        sweep("K-best K=32 (itera=4)", SystemConfig("kbest", kbest_k=32, **idd), snr, n_frames, 50, 2),
    ]
    return {"modulation": "64-QAM", "code": "turbo R=1/2 K=1024 (2048 bits padded to 86 vectors)",
            "channel": "TGn C", "curves": curves}


def part_fig9(n_frames: int) -> dict:
    out = {"max_outer": 16, "n_frames": n_frames, "histograms": []}
    for label, init, snrs in [("paper: random init", "random", [6.8, 7.0, 7.2]),
                              ("MMSE init (variant)", "mmse", [10.0, 12.0, 14.0])]:
        for snr in snrs:
            cfg = SystemConfig("sim", n_outer=16, init=init)
            t = time.time()
            r = simulate_frames(cfg, snr, n_frames, batch=100, seed=3)
            first = np.array(r["first_correct_iteration"])
            counts = [int(np.sum(first == i)) for i in range(1, 17)]
            out["histograms"].append({"label": label, "snr_db": snr, "counts_by_iteration": counts,
                                      "not_converged": int(np.sum(first == 0))})
            log(f"fig9 {label} {snr} dB: converged {n_frames - int(np.sum(first == 0))}/{n_frames} ({time.time() - t:.0f}s)")
    return out


def part_fig11(n_frames: int) -> dict:
    base = dict(code_k=1952, code_parity=400, reset_decoder=True)
    cfgs = [
        ("MMSE I_dec=8 I_outer=4", SystemConfig("mmse_pic", n_outer=4, n_dec_iter=8, **base)),
        ("Sto MCMC I_dec=4 I_outer=8", SystemConfig("sim", n_outer=8, n_dec_iter=4, **base)),
        ("Sto MCMC I_dec=3 I_outer=10", SystemConfig("sim", n_outer=10, n_dec_iter=3, **base)),
        ("Sto MCMC I_dec=4 I_outer=8, MMSE init", SystemConfig("sim", n_outer=8, n_dec_iter=4, init="mmse", **base)),
    ]
    out = {"code": "turbo K=1952, 400 parity bits (rate 0.83), BCJR", "curves": []}
    for snr in (11.0, 13.0):
        for label, cfg in cfgs:
            t = time.time()
            r = simulate_frames(cfg, snr, n_frames, batch=50, seed=4)
            out["curves"].append({"label": label, "snr_db": snr, "ber_per_outer_iteration": r["ber"],
                                  "n_frames": n_frames})
            log(f"fig11 {label} {snr} dB BER={r['ber']} ({time.time() - t:.0f}s)")
    return out


def part_table4() -> dict:
    """Table IV of the paper, transcribed (scaled to 130 nm by the paper where marked a)."""
    cols = ["This Work", "[6]", "[8]", "[14]", "[23]", "[26]", "[28]"]
    rows = {
        "algorithm": ["SIM", "PPTS L=2", "SISO MMSE-PIC", "MCMC Bitwise", "Stochastic Detector", "Soft STS", "FSD"],
        "result_from": ["Post Layout", "Post Synthesis", "Measured", "Post Synthesis", "Post Synthesis", "Post Layout", "Post Layout"],
        "constellation": ["16-QAM", "16-QAM", "64-QAM", "16-QAM", "16-QAM", "64-QAM", "64-QAM"],
        "iteration_time": ["12", "4", "4", "4", "N/A", "4", "4"],
        "clock_mhz": [500, 320, 568, 620, 500, 71, 167],
        "max_throughput_per_llr_exchange": ["16 Gbps", "1.7 Gbps (850 Mbps)a", "757 Mbps (524 Mbps)a", "38.75 Mbps",
                                            "1.5 Gbps", "100 Mbps (200 Mbps)a", "1 Gbps (500 Mbps)a"],
        "iterative_throughput_mbps": [787.5, 213, 131, 9.6, 375, 50, 125],
        "core_area_mm2": [1.98, 1.58, 1.3, None, None, 1.9, 0.25],
        "gate_count_k": [457.4, 1097, 359.6, 29.6, 614, 56.8, "83.7+30"],
        "technology_nm": [130, 65, 90, 130, 130, 250, 65],
        "power_mw": [314, None, "189.1 (273.1)", None, None, None, "59.3 (118.6)"],
        "hardware_efficiency_mbps_per_kge": [1.71, 0.2, 0.36, 0.324, 0.61, 0.88, 1.09],
        "energy_efficiency_nj_per_bit": [0.4, None, 2.08, None, None, None, 0.94],
    }
    refs = {
        "[6]": "Y. Sun and J. R. Cavallaro, Trellis-search based soft-input soft-output MIMO detector, IEEE TSP 60(5), 2012",
        "[8]": "C. Studer, S. Fateh, D. Seethaler, ASIC implementation of SISO MIMO detection using MMSE-PIC, IEEE JSSC 46(7), 2011",
        "[14]": "S. A. Laraway and B. Farhang-Boroujeny, Implementation of a MCMC based multiuser/MIMO detector, IEEE TCAS-I 56(1), 2009",
        "[23]": "J. Chen, J. Hu, G. E. Sobelman, Stochastic Markov chain Monte Carlo MIMO detector, IEEE TSP 62(6), 2014",
        "[26]": "C. Studer, A. Burg, H. Bolcskei, Soft-output sphere decoding: algorithms and VLSI implementation, IEEE JSAC 26(2), 2008",
        "[28]": "L. Liu, J. Lofgren, P. Nilsson, V. Owall, VLSI implementation of a soft-output signal detector for multimode adaptive MIMO, IEEE TVLSI 21(12), 2013",
    }
    return {"columns": cols, "rows": rows, "references": refs,
            "footnotes": {"a": "technology scaling to 130 nm: throughput ~ 1/s, power ~ (1/s)(Vdd/Vdd')",
                          "d": "LDD iterative method [24] assumed to optimize the iterative throughput"}}


def throughput_model() -> dict:
    """Cycle accounting of the paper's operating point against the RTL in hdl/."""
    f = 500e6
    iters = 8 + 12
    return {
        "paper_cycles_per_iteration": 64,
        "rtl_cycles_per_iteration": 66,
        "iterations_per_frame": iters,
        "info_bits_per_frame": 1024,
        "coded_bits_per_frame": 2048,
        "info_throughput_64cyc_mbps": 1024 * f / (iters * 64) / 1e6,
        "coded_throughput_64cyc_mbps": 2048 * f / (iters * 64) / 1e6,
        "coded_throughput_65cyc_mbps": 2048 * f / (iters * 65) / 1e6,
        "paper_reported_mbps": 787.5,
        "note": "The paper does not give its throughput formula; 787.5 Mb/s is close to "
                "2048 coded bits per 20 iterations of 65 cycles at 500 MHz (787.7 Mb/s).",
    }


PARTS = {
    "table2": lambda n: part_table2(),
    "fig10a": part_fig10a,
    "fig10b": part_fig10b,
    "fig9": part_fig9,
    "fig11": part_fig11,
    "table4": lambda n: part_table4(),
}


def merge() -> None:
    payload = {
        "metadata": {
            "paper_doi": "10.1109/TCSI.2015.2390558",
            "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "note": "Measured with scripts/run_campaign.py. table4 is transcribed from the paper, not simulated.",
        },
        "throughput_model": throughput_model(),
    }
    jobs = assemble_fig10a_jobs()
    if jobs is not None:
        (OUT / "part_fig10a.json").write_text(json.dumps(jobs, indent=1) + "\n")
    for name in PARTS:
        f = OUT / f"part_{name}.json"
        if f.exists():
            payload[name] = json.loads(f.read_text())
    (OUT / "sim_campaign.json").write_text(json.dumps(payload, indent=1) + "\n")
    log(f"merged {[k for k in payload if k in PARTS]} into sim_campaign.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=list(PARTS) + ["all"], default="all")
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--job", nargs=2, metavar=("CURVE", "SNR"), help="one Fig. 10(a) point")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.job:
        run_job(int(args.job[0]), float(args.job[1]), args.frames)
        return
    if args.merge:
        merge()
        return
    for name in (PARTS if args.part == "all" else [args.part]):
        t = time.time()
        res = PARTS[name](args.frames)
        if isinstance(res, dict):
            res["runtime_s"] = round(time.time() - t, 1)
        (OUT / f"part_{name}.json").write_text(json.dumps(res, indent=1) + "\n")
        log(f"part {name} done in {time.time() - t:.0f}s")
    if args.part == "all":
        merge()


if __name__ == "__main__":
    main()
