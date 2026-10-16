// Norm unit of Fig. 8: integrator with threshold U. Emits 1 and subtracts U (toward zero)
// whenever |x| >= U, so the output rate is |d| / U. U = 8 ~ sqrt(L) for L = 64.
`timescale 1ns/1ps

module sc_norm_unit #(
    parameter integer U = 8
) (
    input  wire              clk,
    input  wire              rst_n,
    input  wire              clr,
    input  wire              en,
    input  wire signed [1:0] in,
    output wire              out
);
    reg  signed [4:0] integ;
    wire signed [4:0] sum  = integ + {{3{in[1]}}, in};
    wire              fire = (sum >= U) || (sum <= -U);

    assign out = fire;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)    integ <= 5'sd0;
        else if (clr)  integ <= 5'sd0;
        else if (en)   integ <= !fire ? sum : (sum[4] ? sum + U : sum - U);
    end
endmodule
