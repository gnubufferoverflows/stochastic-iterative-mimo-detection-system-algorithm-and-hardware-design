// Stochastic signed addition (Table I, Eq. 6) on ternary stream bits {-1, 0, +1}
// encoded as 2-bit two's complement. `sat` is the one-bit saturation memory: it stores a
// carry when both inputs agree and is emitted on the next (1,-1), (-1,1) or (0,0) input.
`timescale 1ns/1ps

module sc_sat_add (
    input  wire signed [1:0] x,
    input  wire signed [1:0] y,
    input  wire signed [1:0] sat_prev,
    output reg  signed [1:0] z,
    output reg  signed [1:0] sat
);
    always @* begin
        if (x == 2'sd1 && y == 2'sd1) begin
            z = 2'sd1; sat = 2'sd1;
        end else if ((x == 2'sd1 && y == 2'sd0) || (x == 2'sd0 && y == 2'sd1)) begin
            z = 2'sd1; sat = 2'sd0;
        end else if ((x == -2'sd1 && y == 2'sd0) || (x == 2'sd0 && y == -2'sd1)) begin
            z = -2'sd1; sat = 2'sd0;
        end else if (x == -2'sd1 && y == -2'sd1) begin
            z = -2'sd1; sat = -2'sd1;
        end else begin
            // (1,-1), (-1,1) and (0,0): emit the stored value and clear it
            z = sat_prev; sat = 2'sd0;
        end
    end
endmodule
