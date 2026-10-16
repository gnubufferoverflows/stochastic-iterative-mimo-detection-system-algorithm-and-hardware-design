#!/usr/bin/env bash
# Build stimulus from the Python models and run both Icarus testbenches.
# IVERILOG_BIN can point at the Icarus bin directory (e.g. /c/iverilog/bin on Windows).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python
IV="${IVERILOG_BIN:+$IVERILOG_BIN/}iverilog"
VVP="${IVERILOG_BIN:+$IVERILOG_BIN/}vvp"
H="$ROOT/hdl"
LEAF="$H/sc_signed_mul.v $H/sc_sat_add.v $H/sc_tern_mul.v $H/debruijn_gen.v $H/tdg_sng.v \
      $H/sc_norm_unit.v $H/tcs_converter.v $H/sc_vector_norm.v $H/sc_cas_unit.v $H/llr_calculator.v"

cd "$ROOT/sim"
"$PY" gen_stim.py
"$IV" -g2012 -Wall -o tb_units.vvp $LEAF "$H/tb_units.v"
"$VVP" -n tb_units.vvp
"$IV" -g2012 -Wall -o tb_core.vvp $LEAF "$H/sim_mimo_detector_core.v" "$H/tb_core.v"
"$VVP" -n tb_core.vvp
echo "Icarus: unit and core testbenches passed with 0 mismatches"
