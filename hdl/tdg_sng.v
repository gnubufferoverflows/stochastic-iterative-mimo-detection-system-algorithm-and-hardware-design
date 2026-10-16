// Two Divisions Generator stream source (Fig. 5(b), Eqs. 19-22), k1 = 6, k2 = 4.
// Coarse comparator: x^{k1} > r6 every cycle. Fine comparator: x^{k2} > r4, switched in once
// per 64-cycle window in the cycle where r6 = 63. The coarse bit is always 0 in that cycle,
// so the Table I adder never drops the fine bit. The output ternary bit carries the sign.
`timescale 1ns/1ps

module tdg_sng (
    input  wire              clk,
    input  wire              rst_n,
    input  wire              clr,    // clear the adder memory (iteration start)
    input  wire              en,
    input  wire              sign,
    input  wire [9:0]        mag,
    input  wire [5:0]        r6,
    input  wire [3:0]        r4,
    output wire signed [1:0] out
);
    wire coarse = (mag[9:4] > r6);
    wire fine   = (mag[3:0] > r4) && (r6 == 6'h3F);

    reg  signed [1:0] sat;
    wire signed [1:0] z, sat_n;

    sc_sat_add u_sa (
        .x({1'b0, coarse}), .y({1'b0, fine}), .sat_prev(sat), .z(z), .sat(sat_n)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)     sat <= 2'sd0;
        else if (clr)   sat <= 2'sd0;
        else if (en)    sat <= sat_n;
    end

    assign out = sign ? -z : z;
endmodule
