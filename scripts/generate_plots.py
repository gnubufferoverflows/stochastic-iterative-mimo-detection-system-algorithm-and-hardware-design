#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "docs" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
BLUE, RED, GRAY = "#0072BD", "#D95319", "#666666"
plt.rcParams.update({"font.size": 11, "axes.linewidth": 1.5, "lines.linewidth": 2.0})


def main() -> None:
    d = json.loads((ROOT / "benchmarks" / "results" / "sim_campaign.json").read_text())
    m = d["mul_snr_db"]
    labels = ["random_64", "dsc_64", "tdg_stream_k5", "tdg_exact_k5", "random_1024", "dsc_1024"]
    vals = [m[k] for k in labels]
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    ax.bar(range(len(labels)), vals, color=BLUE)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("SNR (dB)")
    ax.set_title("SC multiply SNR vs float (measured)")
    # dashed ref for paper TDG 39.1
    ax.axhline(d["paper_table2_reference_db"]["tdg_64"], color=GRAY, ls="--", lw=1.2, label="Paper TDG L=64 (ref)")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "fig1_mul_snr.svg")
    fig.savefig(FIG / "fig1_mul_snr.png", dpi=150)
    plt.close(fig)

    ber = d["ber_2x2_bpsk"]
    snrs = [r["snr_db"] for r in ber]
    fig, ax = plt.subplots(figsize=(6.0, 4.0))
    ax.semilogy(snrs, [max(r["ber_sim"], 1e-4) for r in ber], "s-", color=BLUE, label="SIM GsUD")
    ax.semilogy(snrs, [max(r["ber_zf"], 1e-4) for r in ber], "o--", color=RED, label="ZF")
    ax.set_xlabel("SNR (dB)")
    ax.set_ylabel("BER (uncoded 2×2 BPSK)")
    ax.set_title("SIM detection vs ZF (measured)")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "fig2_ber.svg")
    fig.savefig(FIG / "fig2_ber.png", dpi=150)
    plt.close(fig)

    synth = ROOT / "benchmarks" / "synth_freepdk45.json"
    if synth.is_file():
        s = json.loads(synth.read_text())
        names = [t["top"] for t in s["targets"]]
        areas = [t["area_um2"] for t in s["targets"]]
        fig, ax = plt.subplots(figsize=(6.2, 3.8))
        ax.bar(names, areas, color=BLUE)
        ax.set_ylabel("Area (µm²)")
        ax.set_title("FreePDK45 Yosys area")
        plt.xticks(rotation=15, ha="right")
        fig.tight_layout()
        fig.savefig(FIG / "fig3_synth.svg")
        fig.savefig(FIG / "fig3_synth.png", dpi=150)
        plt.close(fig)

    print(f"wrote figures under {FIG}")


if __name__ == "__main__":
    main()
