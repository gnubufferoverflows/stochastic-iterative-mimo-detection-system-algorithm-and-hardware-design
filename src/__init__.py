"""Chen et al. TCAS-I 2015 — Stochastic Iterative MIMO (SIM) Detection System."""

from .channel_code import TurboCode, TurboDecoderState, bcjr_maxlog
from .mimo_channel import TGnChannelC, complex_to_real_mimo, compute_noise_var, generate_channel, mmse_detect, zf_detect
from .qam import get_constellation, hard_demap_qam, map_bits_to_qam
from .sim_mimo import (
    Constellation,
    KBestDetector,
    LogMapDetector,
    MmsePicDetector,
    SimDetector,
    SystemConfig,
    simulate_frames,
)
from .tdg import (
    dsc_multiply,
    random_sc_multiply,
    run_table2_benchmark,
    sc_sat_add_bits,
    sc_signed_mul_bits,
    snr_db,
    swg_multiply,
    tdg_multiply,
    tdg_window,
)
