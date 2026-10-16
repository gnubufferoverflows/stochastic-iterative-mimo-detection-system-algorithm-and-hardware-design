// TCS converter of Fig. 8: counts the ones of a stream over one L-cycle window (Eq. 5).
`timescale 1ns/1ps

module tcs_converter #(
    parameter integer W = 7
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         clr,   // reset each L cycles
    input  wire         en,
    input  wire         in,
    output reg  [W-1:0] count
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)         count <= {W{1'b0}};
        else if (clr)       count <= {W{1'b0}};
        else if (en && in)  count <= count + 1'b1;
    end
endmodule
