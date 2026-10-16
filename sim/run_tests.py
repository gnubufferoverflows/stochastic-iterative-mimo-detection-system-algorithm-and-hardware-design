#!/usr/bin/env python3
"""Verification suite for the SIM detection system models and RTL.

Python checks:
1. SM (Fig. 2) and SA (Table I / Eq. 6) bit operations
2. Gray QAM mapping of 16-QAM and 64-QAM (Eq. 11, Fig. 7) in both mappers
3. Complex-to-real decomposition and TGn channel model C statistics
4. TDG (Eqs. 19-22): the 16 windows of every 10-bit magnitude carry exactly its value
5. Parallel LLR calculation (Eqs. 15-17) against brute-force distances
6. Turbo code: error-free decoding at high SNR
7. Soft detectors: Log-MAP extrinsic LLRs with perfect priors, MMSE-PIC vs Log-MAP
8. SIM GsUD with the true sample gives correct hard decisions at high SNR
9. A short coded JDD run executes end to end
RTL checks (Icarus Verilog, sim/run_icarus.sh):
10. Leaf modules and the full detector core bit-exact against src/sc_detector.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.channel_code import TurboCode, TurboDecoderState  # noqa: E402
from src.mimo_channel import TGnChannelC, complex_to_real_mimo, generate_channel, rayleigh_frame  # noqa: E402
from src.qam import hard_demap_qam, map_bits_to_qam  # noqa: E402
from src.sim_mimo import (  # noqa: E402
    Constellation,
    LogMapDetector,
    MmsePicDetector,
    SimDetector,
    SystemConfig,
    simulate_frames,
)
from src.tdg import debruijn_sequence, sc_sat_add_bits, sc_signed_mul_bits, tdg_window  # noqa: E402


def test_sm_sa() -> None:
    assert sc_signed_mul_bits(1, 0, 1, 1) == (1, 1)
    assert sc_signed_mul_bits(1, 1, 1, 1) == (1, 0)
    assert sc_signed_mul_bits(0, 0, 1, 1)[0] == 0
    table = {  # Table I: (x, y) -> (z, sat), z = sat_prev for the last two rows
        (1, 1): (1, 1), (1, 0): (1, 0), (0, 1): (1, 0), (-1, 0): (-1, 0),
        (0, -1): (-1, 0), (-1, -1): (-1, -1),
    }
    for (x, y), out in table.items():
        assert sc_sat_add_bits(x, y, 0) == out
    for sp in (-1, 0, 1):
        assert sc_sat_add_bits(1, -1, sp) == (sp, 0)
        assert sc_sat_add_bits(0, 0, sp) == (sp, 0)


def test_qam() -> None:
    rng = np.random.default_rng(1)
    for m in (16, 64):
        c = Constellation(m)
        bits = rng.integers(0, 2, (200, c.bits_per_vector))
        ref = np.array([map_bits_to_qam(b, m) for b in bits])
        np.testing.assert_allclose(c.map_complex(bits), ref)
        np.testing.assert_array_equal(np.array([hard_demap_qam(s, m) for s in ref]), bits)
    # Fig. 7 ordering of 64-QAM levels: 000 001 011 010 110 111 101 100 from -1 to +1
    c64 = Constellation(64)
    assert ["".join(map(str, l)) for l in c64.labels] == ["000", "001", "011", "010", "110", "111", "101", "100"]


def test_channel() -> None:
    rng = np.random.default_rng(2)
    H = generate_channel(rng=rng)
    s = map_bits_to_qam(rng.integers(0, 2, 16), 16)
    y = H @ s
    y_r, H_r, s_r = complex_to_real_mimo(y, H, s)
    np.testing.assert_allclose(H_r @ s_r, y_r, atol=1e-12)
    ch = TGnChannelC()
    Hs = np.concatenate([ch.frame(52, rng) for _ in range(300)])
    assert abs(np.mean(np.abs(Hs) ** 2) - 1.0) < 0.06


def test_tdg_exact() -> None:
    r6 = debruijn_sequence(6, 64, 1)
    r4s = debruijn_sequence(4, 16, 1)
    for mag in range(1024):
        assert sum(int(tdg_window(mag, r6, int(r4)).sum()) for r4 in r4s) == mag


def test_parallel_llr() -> None:
    rng = np.random.default_rng(3)
    c = Constellation(16)
    V = 50
    H = rayleigh_frame(V, rng)
    x = rng.integers(0, 2, (V, 16))
    y = np.einsum("vrc,vc->vr", H, c.map_complex(rng.integers(0, 2, (V, 16))))
    y_r, H_r, _ = complex_to_real_mimo(y, H)
    det = SimDetector(y_r, H_r, 0.1, c, rng)
    d1, d0 = det.hypothesis_distances(x)
    for j in range(16):
        for val, dist in ((1, d1), (0, d0)):
            xx = x.copy()
            xx[:, j] = val
            ref = np.sum((y_r - np.einsum("vij,vj->vi", H_r, c.map_real(xx))) ** 2, axis=1)
            np.testing.assert_allclose(dist[:, j], ref, rtol=1e-10, atol=1e-10)


def test_turbo() -> None:
    code = TurboCode.rate_half(1024)
    rng = np.random.default_rng(4)
    u = rng.integers(0, 2, (4, 1024))
    cw = code.encode(u).astype(float)
    llr = (2 * cw - 1) * 8.0
    post, app = TurboDecoderState(code, 4).iterate(llr, 2)
    np.testing.assert_array_equal((app > 0).astype(int), u)
    np.testing.assert_array_equal((post > 0).astype(int), cw.astype(int))


def test_soft_detectors() -> None:
    rng = np.random.default_rng(5)
    c = Constellation(16)
    V = 200
    b = rng.integers(0, 2, (V, 16))
    H = rayleigh_frame(V, rng)
    n0 = 4 * 10 ** (-16 / 10)
    y = np.einsum("vrc,vc->vr", H, c.map_complex(b)) + (rng.normal(size=(V, 4)) + 1j * rng.normal(size=(V, 4))) * np.sqrt(n0 / 2)
    y_r, H_r, _ = complex_to_real_mimo(y, H)
    prior = (2 * b - 1) * 15.0
    ll = LogMapDetector(y_r, H_r, n0, c).detect(prior)
    lm = MmsePicDetector(y_r, H_r, n0, c).detect(prior)
    assert np.mean((ll > 0) != b) < 0.05
    assert abs(np.mean((lm > 0) != b) - np.mean((ll > 0) != b)) < 0.02


def test_sim_gsud_true_sample() -> None:
    rng = np.random.default_rng(6)
    c = Constellation(16)
    V = 300
    b = rng.integers(0, 2, (V, 16))
    H = rayleigh_frame(V, rng)
    n0 = 4 * 10 ** (-30 / 10)
    y = np.einsum("vrc,vc->vr", H, c.map_complex(b)) + (rng.normal(size=(V, 4)) + 1j * rng.normal(size=(V, 4))) * np.sqrt(n0 / 2)
    y_r, H_r, _ = complex_to_real_mimo(y, H)
    det = SimDetector(y_r, H_r, n0, c, rng, cas_scope="iteration")
    lam = det.gsud(b, np.zeros((V, 16)))
    assert np.mean((lam > 0) != b) < 0.01


def test_coded_run() -> None:
    r = simulate_frames(SystemConfig("sim", n_outer=3, n_warmup=2), 30.0, 4, batch=4, seed=7)
    assert len(r["fer"]) == 3 and r["n_frames"] == 4


LEAF_RTL = [
    "sc_signed_mul.v", "sc_sat_add.v", "sc_tern_mul.v", "debruijn_gen.v", "tdg_sng.v",
    "sc_norm_unit.v", "tcs_converter.v", "sc_vector_norm.v", "sc_cas_unit.v", "llr_calculator.v",
]


def _icarus_tool(name: str) -> str:
    """Locate an Icarus tool: $IVERILOG_BIN, PATH, or the default Windows install."""
    if os.environ.get("IVERILOG_BIN"):
        return str(Path(os.environ["IVERILOG_BIN"]) / name)
    found = shutil.which(name)
    if found:
        return found
    win = Path("C:/iverilog/bin") / f"{name}.exe"
    if win.exists():
        return str(win)
    raise FileNotFoundError(f"{name} not found; install Icarus Verilog or set IVERILOG_BIN")


def test_icarus() -> None:
    """Same steps as sim/run_icarus.sh, driven from Python so it also runs on Windows."""
    sim = ROOT / "sim"
    hdl = ROOT / "hdl"
    leaf = [str(hdl / f) for f in LEAF_RTL]
    subprocess.check_call([sys.executable, str(sim / "gen_stim.py")], cwd=sim)
    benches = [("tb_units", leaf + [str(hdl / "tb_units.v")]),
               ("tb_core", leaf + [str(hdl / "sim_mimo_detector_core.v"), str(hdl / "tb_core.v")])]
    for name, files in benches:
        subprocess.check_call([_icarus_tool("iverilog"), "-g2012", "-o", f"{name}.vvp", *files], cwd=sim)
        out = subprocess.run([_icarus_tool("vvp"), "-n", f"{name}.vvp"], cwd=sim, capture_output=True, text=True)
        print("    " + "\n    ".join(l for l in out.stdout.splitlines() if "DONE" in l or "MISMATCH" in l))
        assert out.returncode == 0 and "mismatches=0" in out.stdout, out.stdout[-2000:]


TESTS = [
    ("SM / SA truth tables (Fig. 2, Table I)", test_sm_sa),
    ("16/64-QAM Gray mapping (Eq. 11, Fig. 7)", test_qam),
    ("Real decomposition and TGn-C channel power", test_channel),
    ("TDG windows carry the exact value (Eqs. 19-22)", test_tdg_exact),
    ("Parallel LLR distances (Eqs. 15-17)", test_parallel_llr),
    ("Turbo code error-free at high SNR", test_turbo),
    ("Log-MAP / MMSE-PIC soft outputs", test_soft_detectors),
    ("SIM GsUD with the true sample", test_sim_gsud_true_sample),
    ("Coded JDD run end to end", test_coded_run),
    ("Icarus: leaf modules and detector core vs bit-accurate model", test_icarus),
]


def main() -> None:
    for name, fn in TESTS:
        fn()
        print(f"  [PASS] {name}")
    print("\nALL TESTS PASSED")


if __name__ == "__main__":
    main()
