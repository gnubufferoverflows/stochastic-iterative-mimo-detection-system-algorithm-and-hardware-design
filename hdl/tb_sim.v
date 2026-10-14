`timescale 1ns/1ps

module tb_sim;
    integer fd_s, fd_g, fd_o, code, mism, n_vec, done_flag;
    reg a_mag, a_sign, b_mag, b_sign;
    wire z_mag, z_sign;
    reg signed [1:0] sx, sy, sat_p;
    wire signed [1:0] sz, sat_o;
    reg a_tdg, b_tdg;
    reg [10:0] reg_in;
    wire [10:0] reg_out;
    reg [31:0] stim;
    reg [31:0] gold;

    sc_signed_mul u_mul (
        .a_mag(a_mag), .a_sign(a_sign), .b_mag(b_mag), .b_sign(b_sign),
        .z_mag(z_mag), .z_sign(z_sign)
    );
    sc_sat_add u_add (.x(sx), .y(sy), .sat_prev(sat_p), .z(sz), .sat(sat_o));
    tdg_accum_k5 u_tdg (.a_bit(a_tdg), .b_bit(b_tdg), .reg_in(reg_in), .reg_out(reg_out));

    initial begin
        mism = 0; n_vec = 0; done_flag = 0;
        fd_s = $fopen("stim_sim.hex", "r");
        fd_g = $fopen("gold_sim.hex", "r");
        fd_o = $fopen("tb_counts.txt", "w");
        if (fd_s == 0 || fd_g == 0) begin $display("ERROR open"); $finish; end
        while (!done_flag) begin
            code = $fscanf(fd_s, "%h\n", stim);
            if (code != 1) done_flag = 1;
            else begin
                code = $fscanf(fd_g, "%h\n", gold);
                if (code != 1) begin $display("gold short"); $finish; end
                a_mag = stim[31]; a_sign = stim[30];
                b_mag = stim[29]; b_sign = stim[28];
                sx = stim[27:26]; sy = stim[25:24]; sat_p = stim[23:22];
                a_tdg = stim[21]; b_tdg = stim[20];
                reg_in = stim[19:9];
                #1;
                if (z_mag !== gold[31] || z_sign !== gold[30] ||
                    sz !== gold[29:28] || sat_o !== gold[27:26] ||
                    reg_out !== gold[25:15]) begin
                    mism = mism + 1;
                    if (mism <= 8)
                        $display("MISM t=%0d stim=%08h gold=%08h", n_vec, stim, gold);
                end
                n_vec = n_vec + 1;
            end
        end
        $fwrite(fd_o, "n_vec=%0d mismatches=%0d\n", n_vec, mism);
        $display("TB DONE n_vec=%0d mismatches=%0d", n_vec, mism);
        $fclose(fd_s); $fclose(fd_g); $fclose(fd_o);
        if (mism != 0) $fatal(1);
        $finish;
    end
endmodule
