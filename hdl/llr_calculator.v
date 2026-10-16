// LLR calculator sub-block of Fig. 8 for one bit x_{k,b}.
// The DEC multiplexer of Fig. 7 routes the counts of the current sample and of the
// bit-flipped sample to the + and - hypotheses. l = -count is the L1 approximation of
// -||d||^2 / sigma^2. Two CAS units keep the maxima (Eq. 18), lambda1^e = lmax+ - lmax-
// (Eq. 13), and the stream generator converts it back to a stochastic stream.
`timescale 1ns/1ps

module llr_calculator (
    input  wire              clk,
    input  wire              rst_n,
    input  wire              cas_clr,
    input  wire              upd,       // end-of-iteration strobe
    input  wire              x_bit,     // current sample bit
    input  wire [6:0]        c_cur,     // count of the current sample's d vector
    input  wire [6:0]        c_flip,    // count of the bit-flipped d vector
    input  wire [5:0]        rnd,       // random number for the stream generator
    output wire signed [7:0] l_pos,     // l+ of this iteration
    output wire signed [7:0] l_neg,     // l- of this iteration
    output wire signed [7:0] llr,       // lambda1^e
    output wire              llr_sign,
    output wire              llr_mag
);
    wire [6:0] c_pos = x_bit ? c_cur  : c_flip;
    wire [6:0] c_neg = x_bit ? c_flip : c_cur;

    assign l_pos = -$signed({1'b0, c_pos});
    assign l_neg = -$signed({1'b0, c_neg});

    wire signed [7:0] lmax_pos, lmax_neg;

    sc_cas_unit #(.WIDTH(8)) u_cas_pos (
        .clk(clk), .rst_n(rst_n), .clr(cas_clr), .en(upd), .in_val(l_pos), .max_out(lmax_pos)
    );
    sc_cas_unit #(.WIDTH(8)) u_cas_neg (
        .clk(clk), .rst_n(rst_n), .clr(cas_clr), .en(upd), .in_val(l_neg), .max_out(lmax_neg)
    );

    assign llr = lmax_pos - lmax_neg;

    // Stream generator (Fig. 1): sign bit and (|lambda| > random number), |lambda| saturated to 63
    wire [7:0] abs_llr = llr[7] ? -llr : llr;
    wire [5:0] abs_sat = (abs_llr > 8'd63) ? 6'd63 : abs_llr[5:0];

    assign llr_sign = llr[7];
    assign llr_mag  = (abs_sat > rnd);
endmodule
