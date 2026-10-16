// Run Yosys (YoWASP WebAssembly build, npm package @yowasp/yosys) on local files.
// Usage: node synth/yosys_wasm.mjs <out_dir> <script.ys> <input files...>
// Inputs are mounted by basename in the virtual filesystem root; every file Yosys writes
// is copied to <out_dir>. Set YOWASP_YOSYS_DIR to the folder holding node_modules.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { basename, join, resolve } from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const [outDir, script, ...inputs] = process.argv.slice(2);
const base = process.env.YOWASP_YOSYS_DIR || resolve("node_modules");
const require = createRequire(join(base, "noop.js"));
const entry = require.resolve("@yowasp/yosys");
const { runYosys } = await import(pathToFileURL(entry).href);

const files = { [basename(script)]: readFileSync(script) };
for (const f of inputs) files[basename(f)] = readFileSync(f);

const out = await runYosys(["-q", "-s", basename(script)], files, {
  stdout: (b) => b && process.stdout.write(b),
  stderr: (b) => b && process.stderr.write(b),
});

mkdirSync(outDir, { recursive: true });
for (const [name, data] of Object.entries(out)) {
  if (name in files || typeof data === "object" && !(data instanceof Uint8Array)) continue;
  writeFileSync(join(outDir, name), data);
}
