module tdg_accum_k5 (
    input  wire        a_bit,
    input  wire        b_bit,
    input  wire [10:0] reg_in,
    output wire [10:0] reg_out
);
    tdg_accum #(.K(5)) u (
        .a_bit(a_bit), .b_bit(b_bit), .reg_in(reg_in), .reg_out(reg_out)
    );
endmodule
