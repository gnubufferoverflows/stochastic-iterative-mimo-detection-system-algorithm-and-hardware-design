// Stochastic SIM detector for one 4x4 16-QAM vector (Chen TCAS-I 2015, Figs. 4, 5, 7, 8).
// Bit-exact with src/sc_detector.py:StochasticDetector.
//
// One `start` runs one 64-cycle iteration:
//   RUN (64 cycles): TDG streams of H and y, bit-mapped symbol streams of the sample x,
//     d = y - H s (Eq. 15) and the 16 bit-flipped vectors d - H(:,k)(s_flip - s_k) (Eq. 17),
//     each through norm units, an SA cascade and a TCS converter.
//   EVAL (1 cycle): l = -count, CAS update (Eq. 18), lambda1^e = lmax+ - lmax- (Eq. 13), and
//     in warm-up mode the sample update x = [l+ - l- + R > 0] (Eq. 8).
// In GsUD mode the sample is loaded from the decoder bits at start (Eq. 10).
//
// Real-valued model: dimensions 0-3 are Re(s_0..s_3), 4-7 are Im(s_0..s_3). Bit j of x
// belongs to antenna j/4; bits 4i, 4i+1 are (b0, b1) of Re and 4i+2, 4i+3 of Im.
// b0 = 1 means a positive symbol; b1 = 0 the outer level (1), b1 = 1 the inner level (1/3).
`timescale 1ns/1ps

module sim_mimo_detector_core (
    input  wire              clk,
    input  wire              rst_n,
    input  wire              start,
    input  wire              mode_gsud,   // 0: warm-up, 1: GsUD
    input  wire              load_init,   // warm-up start: load init_bits into x
    input  wire              cas_clr,     // clear the CAS maxima (new detection)
    input  wire [2:0]        r_shift,     // Eq. (8): R_b = (rot(g6_{b%5}, b/5) - 32) >>> r_shift
    input  wire [15:0]       init_bits,
    input  wire [15:0]       dec_bits,
    input  wire [8*8*11-1:0] h_flat,      // entry (r, j) at [(r*8+j)*11 +: 11] = {sign, mag[9:0]}
    input  wire [8*11-1:0]   y_flat,      // entry r at [r*11 +: 11]
    output reg  [15:0]       x,
    output wire [16*8-1:0]   llr_flat,    // lambda1^e of bit j at [j*8 +: 8]
    output wire [16-1:0]     llr_stream_sign,
    output wire [16-1:0]     llr_stream_mag,
    output wire [17*7-1:0]   cnt_flat,    // index 0: current sample, 1 + j: bit j flipped
    output reg               busy,
    output reg               done
);
    localparam [1:0] S_IDLE = 2'd0, S_RUN = 2'd1, S_EVAL = 2'd2;

    reg  [1:0] state;
    reg  [5:0] t;
    reg  [1:0] phase3;
    wire       clr_iter = (state == S_IDLE) && start;  // clear per-iteration state at start
    wire       run = (state == S_RUN);

    // ------------------------------------------------------------------ generators
    wire [5:0] g6_0, g6_1, g6_2, g6_3, g6_4;
    wire [3:0] g4_0, g4_1, g4_2;
    wire       g4_en = run && (t == 6'd63);

    debruijn_gen #(.N(6), .SEED(1),  .TAP_HI(5), .TAP_LO(4)) u_g6_0 (.clk(clk), .rst_n(rst_n), .en(run), .state(g6_0));
    debruijn_gen #(.N(6), .SEED(13), .TAP_HI(5), .TAP_LO(4)) u_g6_1 (.clk(clk), .rst_n(rst_n), .en(run), .state(g6_1));
    debruijn_gen #(.N(6), .SEED(29), .TAP_HI(5), .TAP_LO(4)) u_g6_2 (.clk(clk), .rst_n(rst_n), .en(run), .state(g6_2));
    debruijn_gen #(.N(6), .SEED(47), .TAP_HI(5), .TAP_LO(4)) u_g6_3 (.clk(clk), .rst_n(rst_n), .en(run), .state(g6_3));
    debruijn_gen #(.N(6), .SEED(58), .TAP_HI(5), .TAP_LO(4)) u_g6_4 (.clk(clk), .rst_n(rst_n), .en(run), .state(g6_4));
    debruijn_gen #(.N(4), .SEED(1),  .TAP_HI(3), .TAP_LO(2)) u_g4_0 (.clk(clk), .rst_n(rst_n), .en(g4_en), .state(g4_0));
    debruijn_gen #(.N(4), .SEED(6),  .TAP_HI(3), .TAP_LO(2)) u_g4_1 (.clk(clk), .rst_n(rst_n), .en(g4_en), .state(g4_1));
    debruijn_gen #(.N(4), .SEED(11), .TAP_HI(3), .TAP_LO(2)) u_g4_2 (.clk(clk), .rst_n(rst_n), .en(g4_en), .state(g4_2));

    wire [23:0] g6_h = {g6_3, g6_2, g6_1, g6_0};  // H column j uses generator j % 4

    // ------------------------------------------------------------------ TDG inputs
    wire [8*8*2-1:0] h_bits;   // (r, j) at [(r*8+j)*2 +: 2]
    wire [8*2-1:0]   y_bits;
    genvar r, j;

    generate
        for (r = 0; r < 8; r = r + 1) begin : g_hr
            for (j = 0; j < 8; j = j + 1) begin : g_hc
                tdg_sng u_h (
                    .clk(clk), .rst_n(rst_n), .clr(clr_iter), .en(run),
                    .sign(h_flat[(r*8+j)*11 + 10]), .mag(h_flat[(r*8+j)*11 +: 10]),
                    .r6(g6_h[(j%4)*6 +: 6]), .r4(g4_0),
                    .out(h_bits[(r*8+j)*2 +: 2])
                );
            end
            tdg_sng u_y (
                .clk(clk), .rst_n(rst_n), .clr(clr_iter), .en(run),
                .sign(y_flat[r*11 + 10]), .mag(y_flat[r*11 +: 10]),
                .r6(g6_4), .r4(g4_1),
                .out(y_bits[r*2 +: 2])
            );
        end
    endgenerate

    // ------------------------------------------------------------------ bit mapping (Fig. 7)
    wire inner_on = (phase3 == 2'd0);

    function [1:0] sym_stream;
        input b0, b1, inner;
        reg mag;
        begin
            mag = b1 ? inner : 1'b1;
            sym_stream = !mag ? 2'b00 : (b0 ? 2'b01 : 2'b11);
        end
    endfunction

    wire [8*2-1:0] s_bits;
    genvar k;
    generate
        for (k = 0; k < 8; k = k + 1) begin : g_sym
            localparam integer BASE = (k % 4) * 4 + (k / 4) * 2;
            assign s_bits[k*2 +: 2] = sym_stream(x[BASE], x[BASE+1], inner_on);
        end
    endgenerate

    // ------------------------------------------------------------------ d calculator (Eq. 15)
    wire [8*2-1:0] d_bits;
    generate
        for (r = 0; r < 8; r = r + 1) begin : g_d
            wire [8*2-1:0] prod;
            for (j = 0; j < 8; j = j + 1) begin : g_p
                sc_tern_mul u_m (.a(h_bits[(r*8+j)*2 +: 2]), .b(s_bits[j*2 +: 2]), .z(prod[j*2 +: 2]));
            end
            wire [8*2-1:0] acc;
            assign acc[1:0] = prod[1:0];
            for (j = 1; j < 8; j = j + 1) begin : g_t
                reg  signed [1:0] sat;
                wire signed [1:0] z, sat_n;
                sc_sat_add u_sa (.x(acc[(j-1)*2 +: 2]), .y(prod[j*2 +: 2]), .sat_prev(sat), .z(z), .sat(sat_n));
                assign acc[j*2 +: 2] = z;
                always @(posedge clk or negedge rst_n) begin
                    if (!rst_n)        sat <= 2'sd0;
                    else if (clr_iter) sat <= 2'sd0;
                    else if (run)      sat <= sat_n;
                end
            end
            reg  signed [1:0] sat_d;
            wire signed [1:0] zd, sat_dn;
            wire signed [1:0] acc_last = acc[14 +: 2];
            sc_sat_add u_sd (.x(y_bits[r*2 +: 2]), .y(-acc_last), .sat_prev(sat_d), .z(zd), .sat(sat_dn));
            assign d_bits[r*2 +: 2] = zd;
            always @(posedge clk or negedge rst_n) begin
                if (!rst_n)        sat_d <= 2'sd0;
                else if (clr_iter) sat_d <= 2'sd0;
                else if (run)      sat_d <= sat_dn;
            end
        end
    endgenerate

    // ------------------------------------------------------------------ d+-k,b calculator (Eq. 17)
    wire [17*8*2-1:0] vec_bits;  // vector v element r at [(v*8+r)*2 +: 2]
    assign vec_bits[0 +: 16] = d_bits;

    genvar b;
    generate
        for (b = 0; b < 16; b = b + 1) begin : g_flip
            localparam integer KD   = (b >> 2) + 4 * ((b >> 1) & 1);
            localparam integer BASE = b & ~1;
            wire b0f = (b % 2 == 0) ? ~x[BASE]   : x[BASE];
            wire b1f = (b % 2 == 1) ? ~x[BASE+1] : x[BASE+1];
            wire signed [1:0] s_flip = sym_stream(b0f, b1f, inner_on);
            wire signed [1:0] s_cur  = s_bits[KD*2 +: 2];

            reg  signed [1:0] sat_dl;
            wire signed [1:0] delta, sat_dln;
            sc_sat_add u_dl (.x(s_flip), .y(-s_cur), .sat_prev(sat_dl), .z(delta), .sat(sat_dln));
            always @(posedge clk or negedge rst_n) begin
                if (!rst_n)        sat_dl <= 2'sd0;
                else if (clr_iter) sat_dl <= 2'sd0;
                else if (run)      sat_dl <= sat_dln;
            end

            for (r = 0; r < 8; r = r + 1) begin : g_row
                wire signed [1:0] p;
                sc_tern_mul u_m (.a(h_bits[(r*8+KD)*2 +: 2]), .b(delta), .z(p));
                reg  signed [1:0] sat_f;
                wire signed [1:0] zf, sat_fn;
                sc_sat_add u_sf (.x(d_bits[r*2 +: 2]), .y(-p), .sat_prev(sat_f), .z(zf), .sat(sat_fn));
                assign vec_bits[((b+1)*8+r)*2 +: 2] = zf;
                always @(posedge clk or negedge rst_n) begin
                    if (!rst_n)        sat_f <= 2'sd0;
                    else if (clr_iter) sat_f <= 2'sd0;
                    else if (run)      sat_f <= sat_fn;
                end
            end
        end
    endgenerate

    // ------------------------------------------------------------------ ||d|| and TCS counts
    genvar v;
    generate
        for (v = 0; v < 17; v = v + 1) begin : g_vn
            sc_vector_norm #(.N(8), .U(8)) u_vn (
                .clk(clk), .rst_n(rst_n), .clr(clr_iter), .en(run),
                .d(vec_bits[v*16 +: 16]), .count(cnt_flat[v*7 +: 7])
            );
        end
    endgenerate

    // ------------------------------------------------------------------ LLR calculators
    wire upd = (state == S_EVAL);
    wire [15:0] x_next;
    wire [29:0] g6_all = {g6_4, g6_3, g6_2, g6_1, g6_0};

    generate
        for (b = 0; b < 16; b = b + 1) begin : g_llr
            wire signed [7:0] l_pos, l_neg;
            llr_calculator u_llr (
                .clk(clk), .rst_n(rst_n), .cas_clr(cas_clr && clr_iter), .upd(upd),
                .x_bit(x[b]), .c_cur(cnt_flat[0 +: 7]), .c_flip(cnt_flat[(b+1)*7 +: 7]),
                .rnd(g6_4),
                .l_pos(l_pos), .l_neg(l_neg), .llr(llr_flat[b*8 +: 8]),
                .llr_sign(llr_stream_sign[b]), .llr_mag(llr_stream_mag[b])
            );
            // Eq. (8) random signal: generator b % 5 rotated left by b / 5, minus 32
            localparam integer GI  = b % 5;
            localparam integer ROT = b / 5;
            wire [5:0] g     = g6_all[GI*6 +: 6];
            wire [11:0] gg   = {g, g};
            wire [5:0] g_rot = gg[12-ROT-1 -: 6];
            wire signed [8:0] r_val = $signed({3'b000, g_rot}) - 9'sd32;
            wire signed [8:0] r_sh  = r_val >>> r_shift;
            wire signed [8:0] diff  = {l_pos[7], l_pos} - {l_neg[7], l_neg} + r_sh;
            assign x_next[b] = (diff > 0) ? 1'b1 : ((diff < 0) ? 1'b0 : g4_2[0]);
        end
    endgenerate

    // ------------------------------------------------------------------ control
    reg mode_q;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state    <= S_IDLE;
            t        <= 6'd0;
            phase3   <= 2'd0;
            x        <= 16'd0;
            mode_q   <= 1'b0;
            busy     <= 1'b0;
            done     <= 1'b0;
        end else begin
            done     <= 1'b0;
            case (state)
                S_IDLE: if (start) begin
                    mode_q   <= mode_gsud;
                    if (mode_gsud)      x <= dec_bits;
                    else if (load_init) x <= init_bits;
                    busy     <= 1'b1;
                    t        <= 6'd0;
                    phase3   <= 2'd0;
                    state    <= S_RUN;
                end
                S_RUN: begin
                    t      <= t + 1'b1;
                    phase3 <= (phase3 == 2'd2) ? 2'd0 : phase3 + 1'b1;
                    if (t == 6'd63) state <= S_EVAL;
                end
                S_EVAL: begin
                    if (!mode_q) x <= x_next;
                    busy  <= 1'b0;
                    done  <= 1'b1;
                    state <= S_IDLE;
                end
                default: state <= S_IDLE;
            endcase
        end
    end
endmodule
