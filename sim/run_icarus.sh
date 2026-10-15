#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/sim"
python3 gen_stim.py
iverilog -g2012 -o tb_sim.vvp \
  "$ROOT/hdl/sc_signed_mul.v" \
  "$ROOT/hdl/sc_sat_add.v" \
  "$ROOT/hdl/tdg_accum.v" \
  "$ROOT/hdl/tdg_accum_k5.v" \
  "$ROOT/hdl/sc_cas_unit.v" \
  "$ROOT/hdl/llr_calculator.v" \
  "$ROOT/hdl/sim_mimo_detector_core.v" \
  "$ROOT/hdl/tb_sim.v"
vvp tb_sim.vvp
grep -q 'mismatches=0' tb_counts.txt
echo "Icarus parity OK: 0 mismatches across all units!"
