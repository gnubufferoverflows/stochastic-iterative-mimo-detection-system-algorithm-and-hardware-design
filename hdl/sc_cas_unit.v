// Compare-and-Select (CAS) Unit (Chen TCAS-I 2015 Fig. 8, Eq. 18).
// Computes running maximum over Gibbs candidate evaluations.
`timescale 1ns/1ps

module sc_cas_unit #(
    parameter integer WIDTH = 16
) (
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire                     clr,     // Clear / initialize running max
    input  wire                     en,      // Compare enable
    input  wire signed [WIDTH-1:0]  in_val,  // Candidate metric
    output wire signed [WIDTH-1:0]  max_out  // Running maximum
);
    localparam signed [WIDTH-1:0] MIN_VAL = -{1'b0, {(WIDTH-1){1'b1}}};

    reg signed [WIDTH-1:0] r_max;

    wire signed [WIDTH-1:0] diff = in_val - r_max;
    // When in_val >= r_max, diff is positive (MSB / sign is 0)
    wire take_cand = ~diff[WIDTH-1];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            r_max <= MIN_VAL;
        end else if (clr) begin
            r_max <= in_val;
        end else if (en) begin
            if (take_cand)
                r_max <= in_val;
        end
    end

    assign max_out = r_max;

endmodule
