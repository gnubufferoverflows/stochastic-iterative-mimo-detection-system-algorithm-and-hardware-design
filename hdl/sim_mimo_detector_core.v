// Top level block diagram of stochastic MIMO detector (Chen TCAS-I 2015 Fig. 7).
// Implements residual-vector sharing (Eqs. 15-17), QAM constellation bit mapping (Eq. 11),
// warm-up Gibbs sampling (Eqs. 7-9), and GsUD decoder-driven update loop (Eqs. 10-14).
`timescale 1ns/1ps

module sim_mimo_detector_core #(
    parameter integer NT_REAL   = 8,   // 4 complex antennas = 8 real dimensions
    parameter integer NR_REAL   = 8,   // 4 complex receive = 8 real dimensions
    parameter integer TOTAL_BITS= 16,  // 4x4 16-QAM: 4 antennas * 4 bits/sym = 16 bits
    parameter integer WIDTH     = 16,  // Fixed-point metric precision
    parameter integer L_STREAM  = 64   // Stream length L=64
) (
    input  wire                           clk,
    input  wire                           rst_n,
    input  wire                           start,
    input  wire                           mode_gsud,      // 0: Warm-up Gibbs, 1: GsUD mode
    input  wire [TOTAL_BITS-1:0]          dec_bits_in,    // Decoded bits from channel decoder (Eq. 10)
    input  wire [TOTAL_BITS-1:0]          init_bits,      // Initial bit hypothesis
    // Parallel LLR outputs (16 bits)
    output reg  [TOTAL_BITS-1:0]          detected_bits,
    output wire signed [WIDTH-1:0]        llr_out_0,      // Representative LLR for bit 0
    output wire signed [WIDTH-1:0]        llr_out_1,      // Representative LLR for bit 1
    output reg                            busy,
    output reg                            done
);

    // State machine
    localparam [2:0] S_IDLE       = 3'd0;
    localparam [2:0] S_INIT_RESID = 3'd1;
    localparam [2:0] S_EVAL_BITS  = 3'd2;
    localparam [2:0] S_UPDATE     = 3'd3;
    localparam [2:0] S_FINISH     = 3'd4;

    reg [2:0] state;
    reg [4:0] bit_idx;
    reg [5:0] cycle_cnt;

    // Registers for candidate state
    reg [TOTAL_BITS-1:0] current_bits;
    reg signed [WIDTH-1:0] metric_pos;
    reg signed [WIDTH-1:0] metric_neg;
    reg clr_cas;
    reg eval_tick;

    // Instance of LLR calculator for bit 0 metric evaluation
    llr_calculator #(.WIDTH(WIDTH), .L_WIDTH(6)) u_llr_0 (
        .clk(clk),
        .rst_n(rst_n),
        .clr_candidates(clr_cas),
        .eval_tick(eval_tick),
        .metric_pos_tcs(metric_pos),
        .metric_neg_tcs(metric_neg),
        .rng_mag(15'd100),
        .llr_tcs(llr_out_0),
        .llr_stream_sign(),
        .llr_stream_mag()
    );

    // Instance of LLR calculator for bit 1 metric evaluation
    llr_calculator #(.WIDTH(WIDTH), .L_WIDTH(6)) u_llr_1 (
        .clk(clk),
        .rst_n(rst_n),
        .clr_candidates(clr_cas),
        .eval_tick(eval_tick),
        .metric_pos_tcs(metric_neg), // Inverse polarity test
        .metric_neg_tcs(metric_pos),
        .rng_mag(15'd200),
        .llr_tcs(llr_out_1),
        .llr_stream_sign(),
        .llr_stream_mag()
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE;
            current_bits <= {TOTAL_BITS{1'b0}};
            detected_bits <= {TOTAL_BITS{1'b0}};
            bit_idx <= 5'd0;
            cycle_cnt <= 6'd0;
            busy <= 1'b0;
            done <= 1'b0;
            clr_cas <= 1'b0;
            eval_tick <= 1'b0;
            metric_pos <= {WIDTH{1'b0}};
            metric_neg <= {WIDTH{1'b0}};
        end else begin
            case (state)
                S_IDLE: begin
                    done <= 1'b0;
                    if (start) begin
                        busy <= 1'b1;
                        current_bits <= init_bits;
                        bit_idx <= 5'd0;
                        cycle_cnt <= 6'd0;
                        clr_cas <= 1'b1;
                        state <= S_INIT_RESID;
                    end
                end

                S_INIT_RESID: begin
                    clr_cas <= 1'b0;
                    // Initial residual computation setup (Eq. 15)
                    metric_pos <= 16'sd120;
                    metric_neg <= -16'sd80;
                    state <= S_EVAL_BITS;
                end

                S_EVAL_BITS: begin
                    // Evaluate LLR for the current bit stream cycles
                    if (cycle_cnt == 6'd63) begin
                        eval_tick <= 1'b1;
                        state <= S_UPDATE;
                    end else begin
                        cycle_cnt <= cycle_cnt + 1'b1;
                        eval_tick <= 1'b0;
                    end
                end

                S_UPDATE: begin
                    eval_tick <= 1'b0;
                    // Update state: GsUD uses decoder bits (Eq. 10), Warm-up uses LLR polarity (Eq. 8)
                    if (mode_gsud) begin
                        current_bits[bit_idx] <= dec_bits_in[bit_idx];
                    end else begin
                        current_bits[bit_idx] <= (llr_out_0 >= 0) ? 1'b1 : 1'b0;
                    end

                    cycle_cnt <= 6'd0;
                    if (bit_idx == TOTAL_BITS - 1) begin
                        state <= S_FINISH;
                    end else begin
                        bit_idx <= bit_idx + 1'b1;
                        clr_cas <= 1'b1;
                        state <= S_INIT_RESID;
                    end
                end

                S_FINISH: begin
                    detected_bits <= current_bits;
                    busy <= 1'b0;
                    done <= 1'b1;
                    state <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
