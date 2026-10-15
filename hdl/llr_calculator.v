// Sub-block diagram of the LLR calculator (Chen TCAS-I 2015 Fig. 8, Eq. 9, Eq. 18).
// Integrates stochastic norms, TCS conversion, CAS max-log metric tracking,
// LLR subtraction, and output stochastic stream generation.
`timescale 1ns/1ps

module llr_calculator #(
    parameter integer WIDTH = 16,
    parameter integer L_WIDTH = 6 // L=64 default
) (
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire                     clr_candidates, // Reset max metrics for new bit
    input  wire                     eval_tick,      // End of L-cycle stream evaluation
    input  wire signed [WIDTH-1:0]  metric_pos_tcs, // Evaluated +1 hypothesis metric
    input  wire signed [WIDTH-1:0]  metric_neg_tcs, // Evaluated -1 hypothesis metric
    input  wire [WIDTH-2:0]         rng_mag,        // Unsigned uniform RNG for stream gen
    output wire signed [WIDTH-1:0]  llr_tcs,        // Two's complement LLR: l_pos_max - l_neg_max
    output wire                     llr_stream_sign,// Sign stream bit
    output wire                     llr_stream_mag  // Magnitude stream bit
);
    wire signed [WIDTH-1:0] l_pos_max;
    wire signed [WIDTH-1:0] l_neg_max;

    // CAS for +1 hypothesis
    sc_cas_unit #(.WIDTH(WIDTH)) u_cas_pos (
        .clk(clk),
        .rst_n(rst_n),
        .clr(clr_candidates),
        .en(eval_tick),
        .in_val(metric_pos_tcs),
        .max_out(l_pos_max)
    );

    // CAS for -1 hypothesis
    sc_cas_unit #(.WIDTH(WIDTH)) u_cas_neg (
        .clk(clk),
        .rst_n(rst_n),
        .clr(clr_candidates),
        .en(eval_tick),
        .in_val(metric_neg_tcs),
        .max_out(l_neg_max)
    );

    // Max-log LLR: lambda = l_pos_max - l_neg_max (Eq. 9)
    assign llr_tcs = l_pos_max - l_neg_max;

    // Stream Generator (Fig. 1 & Fig. 8)
    // Sign bit: 1 if negative, 0 if positive
    assign llr_stream_sign = llr_tcs[WIDTH-1];

    // Absolute value of LLR for magnitude stream
    wire [WIDTH-2:0] abs_llr = llr_tcs[WIDTH-1] ? (~llr_tcs[WIDTH-2:0] + 1'b1) : llr_tcs[WIDTH-2:0];

    // Magnitude stream: 1 if abs(LLR) > RNG
    assign llr_stream_mag = (abs_llr > rng_mag);

endmodule
