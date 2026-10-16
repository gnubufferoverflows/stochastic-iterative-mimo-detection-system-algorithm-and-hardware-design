#!/usr/bin/env python3
"""Generate the figures in docs/figures from measured data.

- fig1_mul_snr:            Table II, paper vs measured multiplier SNR (sim_campaign.json)
- fig2_fer_16qam:          Fig. 10(a) replication, 16-QAM FER vs Eb/N0 (sim_campaign.json)
- fig2b_fer_64qam:         Fig. 10(b) replication, 64-QAM FER vs Eb/N0 (sim_campaign.json)
- fig3_synth:              Yosys synthesis cell counts (benchmarks/synth_results.json)
- fig4_iterations_hist:    Fig. 9 replication, iterations until a frame decodes (sim_campaign.json)
- fig5_ber_vs_iterations:  Fig. 11 replication, BER vs outer iterations (sim_campaign.json)
- fig6_throughput_comparison: Table IV iterative throughput, values transcribed from the paper
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "docs" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

CLR = ["#0033cc", "#cc0000", "#008844", "#7700aa", "#d97706", "#555555", "#0088aa"]
MARK = ["o", "s", "^", "D", "v", "*", "P"]

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 12,
    "legend.fontsize": 9,
    "axes.linewidth": 1.5,
    "lines.linewidth": 2.0,
    "grid.alpha": 0.4,
    "grid.linestyle": "--",
    "figure.autolayout": True,
})


def save(fig, name: str) -> None:
    fig.savefig(FIG_DIR / f"{name}.png", dpi=200)
    fig.savefig(FIG_DIR / f"{name}.svg")
    plt.close(fig)
    print(f"  wrote docs/figures/{name}.png/.svg")


def plot_table2(data: dict) -> None:
    t2 = data["table2"]
    keys = [k for k in t2 if isinstance(t2[k], dict)]
    labels = [k.replace("_", "\n") for k in keys]
    paper = [t2[k]["paper_snr_db"] if t2[k]["paper_snr_db"] is not None else np.nan for k in keys]
    meas = [t2[k]["measured_snr_db"] for k in keys]
    x = np.arange(len(keys))
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    ax.bar(x - 0.2, paper, 0.4, label="Paper, Table II", color=CLR[5], alpha=0.7)
    ax.bar(x + 0.2, meas, 0.4, label="Measured (src/tdg.py)", color=CLR[0])
    for i, v in enumerate(meas):
        ax.text(i + 0.2, v + 0.6, f"{v:.1f}", ha="center", fontsize=9)
    ax.set_xticks(x, labels)
    ax.set_ylabel("Product SNR (dB)")
    ax.set_title("Stochastic multiplier precision (10-bit inputs, uniform in [-1, 1])")
    ax.grid(axis="y")
    ax.legend()
    save(fig, "fig1_mul_snr")


def plot_fer(data: dict, part: str, name: str, title: str) -> None:
    if part not in data:
        return
    fig, ax = plt.subplots(figsize=(7.5, 6.2))
    floor = 1.0 / max(c["n_frames"] for c in data[part]["curves"])
    for i, c in enumerate(data[part]["curves"]):
        fer = np.array(c["fer"], dtype=float)
        fer_plot = np.where(fer > 0, fer, np.nan)
        ax.semilogy(c["snr_db"], fer_plot, marker=MARK[i % 7], color=CLR[i % 7],
                    label=f"{c['label']} [{c['n_frames']} frames]")
    ax.axhline(floor, color="k", lw=0.8, ls=":", label="1 frame error (resolution limit)")
    ax.set_xlabel("Eb/N0 (dB)")
    ax.set_ylabel("Frame error rate")
    ax.set_ylim(min(floor / 2, 1e-3), 1.5)
    ax.set_title(title)
    ax.grid(which="both")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2, fontsize=8)
    save(fig, name)


def plot_synth() -> None:
    f = ROOT / "benchmarks" / "synth_results.json"
    if not f.exists():
        return
    s = json.loads(f.read_text())
    tops = [t["top"] for t in s["targets"]]
    cells = [t["cells"] for t in s["targets"]]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(tops, cells, color=CLR[0])
    ax.set_xscale("log")
    for i, v in enumerate(cells):
        ax.text(v * 1.08, i, f"{v:,}", va="center", fontsize=9)
    ax.set_xlabel("Cells after synthesis" + (f" ({s['liberty']})" if s.get("liberty") else " (Yosys generic gates)"))
    ax.set_title("RTL synthesis (logic synthesis only, single-vector detector)")
    ax.grid(axis="x")
    save(fig, "fig3_synth")


def plot_fig9(data: dict) -> None:
    if "fig9" not in data:
        return
    h = data["fig9"]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    n = len(h["histograms"])
    width = 0.8 / n
    its = np.arange(1, h["max_outer"] + 1)
    for i, e in enumerate(h["histograms"]):
        ax.bar(its + (i - n / 2 + 0.5) * width, e["counts_by_iteration"], width, color=CLR[i % 7],
               label=f"{e['label']}, {e['snr_db']} dB (not converged: {e['not_converged']})")
    ax.set_xlabel("Outer iterations until all information bits are correct")
    ax.set_ylabel(f"Frames (of {h['n_frames']})")
    ax.set_title("SIM convergence, 4x4 16-QAM, R = 1/2 turbo code, TGn C")
    ax.grid(axis="y")
    ax.legend(fontsize=8)
    save(fig, "fig4_iterations_hist")


def plot_fig11(data: dict) -> None:
    if "fig11" not in data:
        return
    fig, ax = plt.subplots(figsize=(7.5, 5))
    for i, c in enumerate(data["fig11"]["curves"]):
        ber = np.array(c["ber_per_outer_iteration"], dtype=float)
        ls = "-" if c["snr_db"] == 11.0 else "--"
        ax.semilogy(np.arange(1, len(ber) + 1), np.where(ber > 0, ber, np.nan), ls=ls,
                    marker=MARK[i % 4], color=CLR[i % 4], label=f"{c['label']}, {c['snr_db']:.0f} dB")
    ax.set_xlabel("Outer iterations")
    ax.set_ylabel("Bit error rate")
    ax.set_title("4x4 16-QAM, K=1952 rate-0.83 turbo code (BCJR), TGn C")
    ax.grid(which="both")
    ax.legend(fontsize=8)
    save(fig, "fig5_ber_vs_iterations")


def plot_table4(data: dict) -> None:
    t4 = data["table4"]
    names = [f"{c}\n{a}" for c, a in zip(t4["columns"], t4["rows"]["algorithm"])]
    thr = t4["rows"]["iterative_throughput_mbps"]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.bar(range(len(thr)), thr, color=[CLR[0]] + [CLR[5]] * (len(thr) - 1))
    for b, v in zip(bars, thr):
        ax.text(b.get_x() + b.get_width() / 2, v * 1.1, f"{v:g}", ha="center", fontsize=9)
    ax.set_yscale("log")
    ax.set_xticks(range(len(thr)), names, fontsize=8)
    ax.set_ylabel("Iterative throughput (Mb/s)")
    ax.set_title("Table IV of the paper (reported values, not reproduced here)")
    ax.grid(axis="y")
    save(fig, "fig6_throughput_comparison")


def main() -> None:
    data = json.loads((ROOT / "benchmarks" / "results" / "sim_campaign.json").read_text())
    plot_table2(data)
    plot_fer(data, "fig10a", "fig2_fer_16qam", "4x4 16-QAM, R = 1/2 K = 1024 turbo code, TGn C")
    plot_fer(data, "fig10b", "fig2b_fer_64qam", "4x4 64-QAM, R = 1/2 K = 1024 turbo code, TGn C")
    plot_synth()
    plot_fig9(data)
    plot_fig11(data)
    plot_table4(data)


if __name__ == "__main__":
    main()
