// Detector-core testbench: runs warm-up and GsUD iterations on quantized channels from
// sim/gen_stim.py and checks x, lambda1^e and all 17 TCS counts after every iteration
// against the bit-accurate model src/sc_detector.py.
`timescale 1ns/1ps

module tb_core;
    reg clk = 0, rst_n = 1;
    always #5 clk = ~clk;

    reg              start = 0, mode_gsud = 0, load_init = 0, cas_clr = 0;
    reg  [2:0]       r_shift = 0;
    reg  [15:0]      init_bits = 0, dec_bits = 0;
    reg  [8*8*11-1:0] h_flat = 0;
    reg  [8*11-1:0]  y_flat = 0;
    wire [15:0]      x;
    wire [16*8-1:0]  llr_flat;
    wire [15:0]      lsgn, lmag;
    wire [17*7-1:0]  cnt_flat;
    wire             busy, done;

    sim_mimo_detector_core dut (
        .clk(clk), .rst_n(rst_n), .start(start), .mode_gsud(mode_gsud), .load_init(load_init),
        .cas_clr(cas_clr), .r_shift(r_shift), .init_bits(init_bits), .dec_bits(dec_bits),
        .h_flat(h_flat), .y_flat(y_flat), .x(x), .llr_flat(llr_flat),
        .llr_stream_sign(lsgn), .llr_stream_mag(lmag), .cnt_flat(cnt_flat), .busy(busy), .done(done)
    );

    integer fs, fg, code, i, n_it, mism, cyc, t0;
    integer rst, mode, rsh, init, dec, val, ex, e_val;

    task load_signmag(input integer idx, input integer v, input integer is_h);
        reg [10:0] w;
        begin
            w = (v < 0) ? {1'b1, 10'(-v)} : {1'b0, 10'(v)};
            if (is_h) h_flat[idx*11 +: 11] = w;
            else      y_flat[idx*11 +: 11] = w;
        end
    endtask

    initial begin
        mism = 0; n_it = 0;
        fs = $fopen("core_stim.txt", "r");
        fg = $fopen("core_gold.txt", "r");
        if (fs == 0 || fg == 0) begin $display("ERROR: cannot open core vectors"); $finish; end
        while (!$feof(fs)) begin
            code = $fscanf(fs, "%d %d %d %d %d %d %d", rst, mode, load_init, cas_clr, rsh, init, dec);
            if (code == 7) begin
                for (i = 0; i < 64; i = i + 1) begin code = $fscanf(fs, "%d", val); load_signmag(i, val, 1); end
                for (i = 0; i < 8;  i = i + 1) begin code = $fscanf(fs, "%d", val); load_signmag(i, val, 0); end
                if (rst) begin
                    rst_n = 1; #1; rst_n = 0; #11; rst_n = 1;
                end
                @(negedge clk);
                mode_gsud = mode; r_shift = rsh; init_bits = init; dec_bits = dec; start = 1;
                t0 = $time;
                @(negedge clk);
                start = 0;
                cyc = 1;
                while (!done) begin @(negedge clk); cyc = cyc + 1; end
                // golden: x, 16 LLRs, 17 counts
                code = $fscanf(fg, "%d", ex);
                if (x !== ex[15:0]) begin
                    mism = mism + 1;
                    if (mism <= 10) $display("MISMATCH it %0d x: got %h expected %h", n_it, x, ex[15:0]);
                end
                for (i = 0; i < 16; i = i + 1) begin
                    code = $fscanf(fg, "%d", e_val);
                    if ($signed(llr_flat[i*8 +: 8]) !== e_val) begin
                        mism = mism + 1;
                        if (mism <= 10) $display("MISMATCH it %0d llr[%0d]: got %0d expected %0d", n_it, i, $signed(llr_flat[i*8 +: 8]), e_val);
                    end
                end
                for (i = 0; i < 17; i = i + 1) begin
                    code = $fscanf(fg, "%d", e_val);
                    if (cnt_flat[i*7 +: 7] !== e_val) begin
                        mism = mism + 1;
                        if (mism <= 10) $display("MISMATCH it %0d cnt[%0d]: got %0d expected %0d", n_it, i, cnt_flat[i*7 +: 7], e_val);
                    end
                end
                n_it = n_it + 1;
            end
        end
        $display("CORE DONE iterations=%0d cycles_per_iteration=%0d mismatches=%0d", n_it, cyc, mism);
        if (mism != 0) $fatal(1, "core mismatches");
        $finish;
    end
endmodule
