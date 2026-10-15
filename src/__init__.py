"""Chen et al. TCAS-I 2015 — Stochastic Iterative MIMO (SIM) Detection System."""

from .mimo_channel import complex_to_real_mimo, compute_noise_var, generate_channel, mmse_detect, zf_detect
from .qam import get_constellation, hard_demap_qam, map_bits_to_qam
from .sim_mimo import (
    gibbs_mimo_detect,
    maxlog_llr_qam,
    sc_sat_add_bits,
    sc_signed_mul,
    sim_mimo_detect,
    snr_db,
    tdg_multiply,
    tdg_multiply_stream,
    traditional_sc_multiply,
)
from .tdg import (
    dsc_multiply,
    random_sc_multiply,
    run_table2_benchmark,
    swg_multiply,
)

__all__ = [
    "generate_channel",
    "complex_to_real_mimo",
    "compute_noise_var",
    "zf_detect",
    "mmse_detect",
    "map_bits_to_qam",
    "hard_demap_qam",
    "get_constellation",
    "sim_mimo_detect",
    "gibbs_mimo_detect",
    "maxlog_llr_qam",
    "tdg_multiply",
    "tdg_multiply_stream",
    "traditional_sc_multiply",
    "random_sc_multiply",
    "dsc_multiply",
    "swg_multiply",
    "sc_signed_mul",
    "sc_sat_add_bits",
    "snr_db",
    "run_table2_benchmark",
]
