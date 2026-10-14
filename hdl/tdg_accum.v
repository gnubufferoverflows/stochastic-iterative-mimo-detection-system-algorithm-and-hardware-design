// TDG accumulate one cycle: reg += a_bit*L + b_bit  (Fig. 5 principle).
module tdg_accum #(
    parameter integer K = 5
) (
    input  wire               a_bit,
    input  wire               b_bit,
    input  wire [2*K:0]       reg_in,
    output wire [2*K:0]       reg_out
);
    localparam integer L = 1 << K;
    assign reg_out = reg_in + (a_bit ? L : 0) + (b_bit ? 1 : 0);
endmodule
