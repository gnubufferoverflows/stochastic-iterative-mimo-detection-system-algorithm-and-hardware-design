// Leaf-module testbench: drives one random stimulus line per clock cycle and checks
// combinational outputs before the edge and registered outputs after it against the
// golden values produced by sim/gen_stim.py.
`timescale 1ns/1ps

module tb_units;
    reg clk = 0, rst_n = 1;
    always #5 clk = ~clk;

    integer fs, fg, code, n, mism;
    integer a_mag, a_sign, b_mag, b_sign, sx, sy, sp, g6_en, tdg_clr, tdg_sign, tdg_mag, r6, r4;
    integer n_clr, n_in, cas_clr, cas_en, cas_in, l_clr, l_upd, x_bit, c_cur, c_flip, rnd;
    integer e_zm, e_zs, e_z, e_sat, e_tdg, e_fire, e_lpos, e_lneg, e_g6, e_cas, e_llr, e_lsign, e_lmag;

    reg        i_a_mag, i_a_sign, i_b_mag, i_b_sign;
    reg signed [1:0] i_sx, i_sy, i_sp, i_nin;
    reg        i_g6_en, i_tdg_clr, i_tdg_sign, i_n_clr, i_cas_clr, i_cas_en, i_l_clr, i_l_upd, i_x_bit;
    reg [9:0]  i_tdg_mag;
    reg [5:0]  i_r6, i_rnd;
    reg [3:0]  i_r4;
    reg signed [7:0] i_cas_in;
    reg [6:0]  i_c_cur, i_c_flip;

    wire z_mag, z_sign, n_out, lsign, lmag;
    wire signed [1:0] z, sat, tdg_out;
    wire [5:0] g6;
    wire signed [7:0] cas_max, l_pos, l_neg, llr;

    sc_signed_mul u_mul (.a_mag(i_a_mag), .a_sign(i_a_sign), .b_mag(i_b_mag), .b_sign(i_b_sign), .z_mag(z_mag), .z_sign(z_sign));
    sc_sat_add    u_sa  (.x(i_sx), .y(i_sy), .sat_prev(i_sp), .z(z), .sat(sat));
    debruijn_gen #(.N(6), .SEED(1), .TAP_HI(5), .TAP_LO(4)) u_g6 (.clk(clk), .rst_n(rst_n), .en(i_g6_en), .state(g6));
    tdg_sng       u_tdg (.clk(clk), .rst_n(rst_n), .clr(i_tdg_clr), .en(1'b1), .sign(i_tdg_sign), .mag(i_tdg_mag), .r6(i_r6), .r4(i_r4), .out(tdg_out));
    sc_norm_unit  u_nrm (.clk(clk), .rst_n(rst_n), .clr(i_n_clr), .en(1'b1), .in(i_nin), .out(n_out));
    sc_cas_unit #(.WIDTH(8)) u_cas (.clk(clk), .rst_n(rst_n), .clr(i_cas_clr), .en(i_cas_en), .in_val(i_cas_in), .max_out(cas_max));
    llr_calculator u_llr (.clk(clk), .rst_n(rst_n), .cas_clr(i_l_clr), .upd(i_l_upd), .x_bit(i_x_bit), .c_cur(i_c_cur), .c_flip(i_c_flip),
                          .rnd(i_rnd), .l_pos(l_pos), .l_neg(l_neg), .llr(llr), .llr_sign(lsign), .llr_mag(lmag));

    task check(input integer got, input integer exp, input [8*8-1:0] name);
        begin
            if (got !== exp) begin
                mism = mism + 1;
                if (mism <= 10) $display("MISMATCH cycle %0d %0s: got %0d expected %0d", n, name, got, exp);
            end
        end
    endtask

    initial begin
        mism = 0; n = 0;
        {i_a_mag, i_a_sign, i_b_mag, i_b_sign, i_g6_en, i_tdg_clr, i_tdg_sign} = 0;
        {i_n_clr, i_cas_clr, i_cas_en, i_l_clr, i_l_upd, i_x_bit} = 0;
        i_sx = 0; i_sy = 0; i_sp = 0; i_nin = 0; i_tdg_mag = 0; i_r6 = 0; i_r4 = 0;
        i_cas_in = 0; i_c_cur = 0; i_c_flip = 0; i_rnd = 0;
        fs = $fopen("units_stim.txt", "r");
        fg = $fopen("units_gold.txt", "r");
        if (fs == 0 || fg == 0) begin $display("ERROR: cannot open unit vectors"); $finish; end
        #1 rst_n = 0;
        #11 rst_n = 1;
        while (!$feof(fs)) begin
            code = $fscanf(fs, "%d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d\n",
                a_mag, a_sign, b_mag, b_sign, sx, sy, sp, g6_en, tdg_clr, tdg_sign, tdg_mag, r6, r4,
                n_clr, n_in, cas_clr, cas_en, cas_in, l_clr, l_upd, x_bit, c_cur, c_flip, rnd);
            if (code == 24) begin
                code = $fscanf(fg, "%d %d %d %d %d %d %d %d %d %d %d %d %d\n",
                    e_zm, e_zs, e_z, e_sat, e_tdg, e_fire, e_lpos, e_lneg, e_g6, e_cas, e_llr, e_lsign, e_lmag);
                @(negedge clk);
                i_a_mag = a_mag; i_a_sign = a_sign; i_b_mag = b_mag; i_b_sign = b_sign;
                i_sx = sx; i_sy = sy; i_sp = sp; i_g6_en = g6_en;
                i_tdg_clr = tdg_clr; i_tdg_sign = tdg_sign; i_tdg_mag = tdg_mag; i_r6 = r6; i_r4 = r4;
                i_n_clr = n_clr; i_nin = n_in; i_cas_clr = cas_clr; i_cas_en = cas_en; i_cas_in = cas_in;
                i_l_clr = l_clr; i_l_upd = l_upd; i_x_bit = x_bit; i_c_cur = c_cur; i_c_flip = c_flip; i_rnd = rnd;
                #1;
                check(z_mag, e_zm, "sm_mag"); check(z_sign, e_zs, "sm_sign");
                check(z, e_z, "sa_z"); check(sat, e_sat, "sa_sat");
                check(tdg_out, e_tdg, "tdg"); check(n_out, e_fire, "norm");
                check(l_pos, e_lpos, "l_pos"); check(l_neg, e_lneg, "l_neg");
                @(posedge clk); #1;
                check(g6, e_g6, "debruijn"); check(cas_max, e_cas, "cas");
                check(llr, e_llr, "llr"); check(lsign, e_lsign, "llr_sgn"); check(lmag, e_lmag, "llr_mag");
                n = n + 1;
            end
        end
        $display("UNITS DONE cycles=%0d mismatches=%0d", n, mism);
        if (mism != 0) $fatal(1, "unit mismatches");
        $finish;
    end
endmodule
