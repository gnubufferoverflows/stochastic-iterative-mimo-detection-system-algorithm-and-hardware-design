`timescale 1ns/1ps

module tb_sim;
    reg clk;
    reg rst_n;

    integer fd_s, fd_g, fd_o, code, mism, n_vec, done_flag;
    reg a_mag, a_sign, b_mag, b_sign;
    wire z_mag, z_sign;
    reg signed [1:0] sx, sy, sat_p;
    wire signed [1:0] sz, sat_o;
    reg a_tdg, b_tdg;
    reg [10:0] reg_in;
    wire [10:0] reg_out;

    // CAS test signals
    reg cas_clr, cas_en;
    reg signed [15:0] cas_in;
    wire signed [15:0] cas_max;

    // LLR calculator test signals
    reg llr_clr, llr_eval;
    reg signed [15:0] m_pos, m_neg;
    reg [14:0] rng_val;
    wire signed [15:0] llr_val;
    wire llr_sign, llr_mag;

    // Core test signals
    reg core_start, core_mode;
    reg [15:0] core_dec_bits, core_init_bits;
    wire [15:0] core_det_bits;
    wire signed [15:0] core_llr0, core_llr1;
    wire core_busy, core_done;

    // Vectors
    reg [63:0] stim_lo, stim_hi;
    reg [63:0] gold_lo, gold_hi;

    // DUT instances
    sc_signed_mul u_mul (
        .a_mag(a_mag), .a_sign(a_sign), .b_mag(b_mag), .b_sign(b_sign),
        .z_mag(z_mag), .z_sign(z_sign)
    );

    sc_sat_add u_add (
        .x(sx), .y(sy), .sat_prev(sat_p), .z(sz), .sat(sat_o)
    );

    tdg_accum_k5 u_tdg (
        .a_bit(a_tdg), .b_bit(b_tdg), .reg_in(reg_in), .reg_out(reg_out)
    );

    sc_cas_unit #(.WIDTH(16)) u_cas (
        .clk(clk),
        .rst_n(rst_n),
        .clr(cas_clr),
        .en(cas_en),
        .in_val(cas_in),
        .max_out(cas_max)
    );

    llr_calculator #(.WIDTH(16), .L_WIDTH(6)) u_llr (
        .clk(clk),
        .rst_n(rst_n),
        .clr_candidates(llr_clr),
        .eval_tick(llr_eval),
        .metric_pos_tcs(m_pos),
        .metric_neg_tcs(m_neg),
        .rng_mag(rng_val),
        .llr_tcs(llr_val),
        .llr_stream_sign(llr_sign),
        .llr_stream_mag(llr_mag)
    );

    sim_mimo_detector_core #(
        .NT_REAL(8),
        .NR_REAL(8),
        .TOTAL_BITS(16),
        .WIDTH(16),
        .L_STREAM(64)
    ) u_core (
        .clk(clk),
        .rst_n(rst_n),
        .start(core_start),
        .mode_gsud(core_mode),
        .dec_bits_in(core_dec_bits),
        .init_bits(core_init_bits),
        .detected_bits(core_det_bits),
        .llr_out_0(core_llr0),
        .llr_out_1(core_llr1),
        .busy(core_busy),
        .done(core_done)
    );

    // Clock generator
    always #5 clk = ~clk;

    initial begin
        clk = 0;
        rst_n = 0;
        mism = 0;
        n_vec = 0;
        done_flag = 0;
        cas_clr = 0;
        cas_en = 0;
        cas_in = 0;
        llr_clr = 0;
        llr_eval = 0;
        m_pos = 0;
        m_neg = 0;
        rng_val = 0;
        core_start = 0;
        core_mode = 0;
        core_dec_bits = 0;
        core_init_bits = 0;

        #20 rst_n = 1;

        fd_s = $fopen("stim_sim.hex", "r");
        fd_g = $fopen("gold_sim.hex", "r");
        fd_o = $fopen("tb_counts.txt", "w");
        if (fd_s == 0 || fd_g == 0) begin
            $display("ERROR opening stimulus files");
            $finish;
        end

        while (!done_flag) begin
            code = $fscanf(fd_s, "%h %h\n", stim_hi, stim_lo);
            if (code != 2) begin
                done_flag = 1;
            end else begin
                code = $fscanf(fd_g, "%h %h\n", gold_hi, gold_lo);
                if (code != 2) begin
                    $display("gold short");
                    $finish;
                end

                // Unpack stimulus
                a_mag   = stim_lo[0];
                a_sign  = stim_lo[1];
                b_mag   = stim_lo[2];
                b_sign  = stim_lo[3];
                sx      = stim_lo[5:4];
                sy      = stim_lo[7:6];
                sat_p   = stim_lo[9:8];
                a_tdg   = stim_lo[10];
                b_tdg   = stim_lo[11];
                reg_in  = stim_lo[22:12];

                cas_clr = stim_lo[23];
                cas_en  = stim_lo[24];
                cas_in  = stim_lo[40:25];

                llr_clr  = stim_lo[41];
                llr_eval = stim_lo[42];
                m_pos    = stim_hi[15:0];
                m_neg    = stim_hi[31:16];
                rng_val  = stim_hi[46:32];

                @(posedge clk);
                #1;

                // Check basic blocks
                if (z_mag !== gold_lo[0] || z_sign !== gold_lo[1] ||
                    sz !== gold_lo[3:2] || sat_o !== gold_lo[5:4] ||
                    reg_out !== gold_lo[16:6]) begin
                    mism = mism + 1;
                    if (mism <= 8)
                        $display("MISM basic t=%0d stim=%h gold=%h", n_vec, stim_lo, gold_lo);
                end

                // Check CAS unit
                if (cas_max !== gold_lo[32:17]) begin
                    mism = mism + 1;
                    if (mism <= 8)
                        $display("MISM CAS t=%0d max=%d gold=%d", n_vec, cas_max, $signed(gold_lo[32:17]));
                end

                // Check LLR output
                if (llr_val !== gold_hi[15:0] || llr_sign !== gold_hi[16] || llr_mag !== gold_hi[17]) begin
                    mism = mism + 1;
                    if (mism <= 8)
                        $display("MISM LLR t=%0d llr=%d gold=%d", n_vec, llr_val, $signed(gold_hi[15:0]));
                end

                n_vec = n_vec + 1;
            end
        end

        // Functional test for sim_mimo_detector_core in GsUD mode
        @(posedge clk);
        core_init_bits = 16'hA5A5;
        core_dec_bits  = 16'h5A5A;
        core_mode      = 1'b1; // GsUD mode: updates bits from decoder
        core_start     = 1'b1;
        @(posedge clk);
        core_start     = 1'b0;

        // Wait for core completion
        while (!core_done) begin
            @(posedge clk);
        end

        if (core_det_bits !== 16'h5A5A) begin
            $display("MISM Core GsUD detected=%h gold=%h", core_det_bits, 16'h5A5A);
            mism = mism + 1;
        end else begin
            $display("PASS Core GsUD detected=%h correctly matched decoder bits!", core_det_bits);
        end

        $fwrite(fd_o, "n_vec=%0d mismatches=%0d\n", n_vec, mism);
        $display("TB DONE n_vec=%0d mismatches=%0d", n_vec, mism);
        $fclose(fd_s);
        $fclose(fd_g);
        $fclose(fd_o);
        if (mism != 0) $fatal(1);
        $finish;
    end
endmodule
