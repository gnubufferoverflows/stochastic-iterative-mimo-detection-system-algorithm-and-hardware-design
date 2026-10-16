// Compare-and-select unit (Eq. 18, Fig. 8): keeps the running maximum of its input.
// Uses a direct signed comparison, so it cannot overflow the way a subtract-and-check-MSB
// comparator does at the ends of the range.
`timescale 1ns/1ps

module sc_cas_unit #(
    parameter integer WIDTH = 8
) (
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire                     clr,     // load the minimum value
    input  wire                     en,      // compare enable
    input  wire signed [WIDTH-1:0]  in_val,
    output wire signed [WIDTH-1:0]  max_out
);
    localparam signed [WIDTH-1:0] MIN_VAL = -{1'b0, {(WIDTH-1){1'b1}}};

    reg signed [WIDTH-1:0] r_max;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            r_max <= MIN_VAL;
        else if (clr)
            r_max <= MIN_VAL;
        else if (en && (in_val > r_max))
            r_max <= in_val;
    end

    assign max_out = r_max;
endmodule
