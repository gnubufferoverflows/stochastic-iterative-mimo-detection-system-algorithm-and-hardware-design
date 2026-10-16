// n-bit de Bruijn random number generator (LFSR with the all-zero state spliced in).
// Visits every n-bit value once per 2^n steps; used as the 6-bit and 4-bit random sources
// of the stream generators (Sec. V-A). Matches src/tdg.py:debruijn_next.
`timescale 1ns/1ps

module debruijn_gen #(
    parameter integer N      = 6,
    parameter integer SEED   = 1,
    parameter integer TAP_HI = 5,
    parameter integer TAP_LO = 4
) (
    input  wire         clk,
    input  wire         rst_n,
    input  wire         en,
    output reg  [N-1:0] state
);
    wire fb = state[TAP_HI] ^ state[TAP_LO] ^ (state[N-2:0] == {(N-1){1'b0}});

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            state <= SEED[N-1:0];
        else if (en)
            state <= {state[N-2:0], fb};
    end
endmodule
