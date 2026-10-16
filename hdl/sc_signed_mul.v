// Stochastic signed multiplier (Chen TCAS-I 2015 Fig. 2).
// Magnitude: AND; sign: XOR.
`timescale 1ns/1ps

module sc_signed_mul (
    input  wire a_mag,
    input  wire a_sign,
    input  wire b_mag,
    input  wire b_sign,
    output wire z_mag,
    output wire z_sign
);
    assign z_mag  = a_mag & b_mag;
    assign z_sign = a_sign ^ b_sign;
endmodule
