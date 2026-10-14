// Stochastic saturating adder (Table I), ternary via 2-bit {sign,mag} but
// lab uses 2's encoding: in_x/in_y in {-1,0,+1} as signed 2-bit.
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
        end else if ((x == 2'sd1 && y == -2'sd1) || (x == -2'sd1 && y == 2'sd1)) begin
            z = sat_prev; sat = 2'sd0;
        end else begin
            z = sat_prev; sat = 2'sd0;
        end
    end
endmodule
