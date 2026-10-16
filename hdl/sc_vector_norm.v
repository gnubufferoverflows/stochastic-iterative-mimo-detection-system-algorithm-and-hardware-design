// ||d|| path of Fig. 8 for one 2Nr = 8 element stream vector: norm units, a cascade of
// two-input stochastic adders (Table I) and the TCS converter.
`timescale 1ns/1ps

module sc_vector_norm #(
    parameter integer N = 8,
    parameter integer U = 8
) (
    input  wire           clk,
    input  wire           rst_n,
    input  wire           clr,
    input  wire           en,
    input  wire [2*N-1:0] d,      // N ternary stream bits, element r at [2r+1:2r]
    output wire [6:0]     count
);
    wire [N-1:0] nrm;
    genvar r;

    generate
        for (r = 0; r < N; r = r + 1) begin : g_norm
            sc_norm_unit #(.U(U)) u_n (
                .clk(clk), .rst_n(rst_n), .clr(clr), .en(en),
                .in(d[2*r+1:2*r]), .out(nrm[r])
            );
        end
    endgenerate

    // SA cascade: acc_r = SA(acc_{r-1}, nrm_r)
    wire [2*N-1:0] acc;
    assign acc[1:0] = {1'b0, nrm[0]};

    generate
        for (r = 1; r < N; r = r + 1) begin : g_sum
            reg  signed [1:0] sat;
            wire signed [1:0] z, sat_n;

            sc_sat_add u_sa (
                .x(acc[2*r-1:2*r-2]), .y({1'b0, nrm[r]}), .sat_prev(sat), .z(z), .sat(sat_n)
            );
            assign acc[2*r+1:2*r] = z;

            always @(posedge clk or negedge rst_n) begin
                if (!rst_n)    sat <= 2'sd0;
                else if (clr)  sat <= 2'sd0;
                else if (en)   sat <= sat_n;
            end
        end
    endgenerate

    tcs_converter #(.W(7)) u_tcs (
        .clk(clk), .rst_n(rst_n), .clr(clr), .en(en),
        .in(acc[2*N-1:2*N-2] == 2'sd1), .count(count)
    );
endmodule
