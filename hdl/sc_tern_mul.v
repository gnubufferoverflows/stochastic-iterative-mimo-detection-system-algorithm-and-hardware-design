// Stochastic signed multiplier (Fig. 2) on a ternary stream bit {-1, 0, +1}
// encoded as 2-bit two's complement. Wraps the AND/XOR multiplier of sc_signed_mul.
`timescale 1ns/1ps

module sc_tern_mul (
    input  wire signed [1:0] a,
    input  wire signed [1:0] b,
    output wire signed [1:0] z
);
    wire z_mag, z_sign;

    sc_signed_mul u_sm (
        .a_mag(a != 2'sd0), .a_sign(a[1]),
        .b_mag(b != 2'sd0), .b_sign(b[1]),
        .z_mag(z_mag), .z_sign(z_sign)
    );

    assign z = !z_mag ? 2'sd0 : (z_sign ? -2'sd1 : 2'sd1);
endmodule
