#!/usr/bin/env python3
"""Synthesize the RTL targets of synth/targets.json with Yosys and record cell counts and area.

Yosys is taken from $YOSYS (a native binary) or, if unset, from the YoWASP WebAssembly build
run through synth/yosys_wasm.mjs ($YOWASP_YOSYS_DIR points at the node_modules folder).
With --liberty, cells are mapped to that library (e.g. NanGate45 / FreePDK45) and the area is
reported; without it, the technology-independent Yosys gate count is reported.

Results go to benchmarks/synth_results.json; netlists and logs to synth/out/.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "synth" / "out"
NAND2_X1_AREA_UM2 = 0.798  # NanGate45 NAND2_X1, used for gate equivalents


def yosys_cmd(script: Path, inputs: list[Path], out_dir: Path) -> list[str]:
    native = os.environ.get("YOSYS")
    if native:
        return [native, "-q", "-s", str(script)]
    node = shutil.which("node") or "node"
    return [node, "--experimental-wasm-exnref", str(ROOT / "synth" / "yosys_wasm.mjs"),
            str(out_dir), str(script), *map(str, inputs)]


def synth_target(top: str, files: list[str], liberty: Path | None) -> dict:
    out_dir = OUT / top
    out_dir.mkdir(parents=True, exist_ok=True)
    native = bool(os.environ.get("YOSYS"))
    srcs = [ROOT / f for f in files]
    name = (lambda p: str(p)) if native else (lambda p: p.name)
    lines = [f"read_verilog {' '.join(name(s) for s in srcs)}", f"synth -flatten -top {top}",
             "delete t:$scopeinfo", "opt_clean"]
    lib = name(liberty) if liberty else None
    stat_file = name(out_dir / "stat.txt") if native else "stat.txt"
    netlist = name(out_dir / "netlist.v") if native else "netlist.v"
    if lib:
        lines += [f"dfflibmap -liberty {lib}", f"abc -liberty {lib}", "opt_clean",
                  f"tee -q -o {stat_file} stat -liberty {lib}"]
    else:
        lines += [f"tee -q -o {stat_file} stat"]
    lines += [f"write_verilog -noattr {netlist}"]
    script = out_dir / "synth.ys"
    script.write_text("\n".join(lines) + "\n")
    inputs = srcs + ([liberty] if liberty else [])
    if native:
        subprocess.check_call(yosys_cmd(script, inputs, out_dir))
    else:
        subprocess.check_call(yosys_cmd(script, inputs, out_dir), cwd=out_dir)
    stat = (out_dir / "stat.txt").read_text()
    cells = re.findall(r"Number of cells:\s+(\d+)", stat) or re.findall(r"^\s+(\d+)\s+cells$", stat, re.M)
    res = {"top": top, "cells": int(cells[-1]) if cells else None}
    flops = sum(int(n) for n in re.findall(r"^\s+(\d+)\s+\$_(?:S?DFF\w*)_?\s*$", stat, re.M))
    res["flip_flops"] = flops
    area = re.findall(r"Chip area for (?:top )?module.*?:\s+([\d.]+)", stat)
    if area:
        res["area_um2"] = float(area[-1])
        res["gate_equivalents_nand2"] = round(float(area[-1]) / NAND2_X1_AREA_UM2, 1)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--liberty", type=Path, default=None)
    args = ap.parse_args()
    targets = json.loads((ROOT / "synth" / "targets.json").read_text())["targets"]
    results = []
    for t in targets:
        r = synth_target(t["top"], t["files"], args.liberty)
        results.append(r)
        print(r, flush=True)
    payload = {
        "tool": "Yosys (YoWASP build)" if not os.environ.get("YOSYS") else "Yosys",
        "liberty": args.liberty.name if args.liberty else None,
        "flow": "synth -flatten; dfflibmap + abc to the liberty" if args.liberty else "synth -flatten (generic gates)",
        "note": "Logic synthesis only; no placement, routing or timing. Gate equivalents use NAND2_X1 = 0.798 um^2.",
        "targets": results,
    }
    (ROOT / "benchmarks" / "synth_results.json").write_text(json.dumps(payload, indent=1) + "\n")


if __name__ == "__main__":
    main()
