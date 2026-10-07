const {spawnSync} = require("child_process");
const path = require("path");

const mount = process.env.RUST_CACHE_OVERLAY_MOUNT;
const lower = process.env.RUST_CACHE_OVERLAY_LOWER;
const upper = process.env.RUST_CACHE_OVERLAY_UPPER;
const tool = process.env.RUST_CACHE_OVERLAY_TOOL;
const save = process.env.INPUT_SAVE === "true";
let failed = false;

function run(command, args) {
  const result = spawnSync(command, args, {stdio: "inherit"});
  if (result.error) {
    throw result.error;
  }
  return result.status ?? 1;
}

if (save && run("python3", [path.join(__dirname, "clean.py")]) !== 0) {
  failed = true;
}

if (mount) {
  const mounted = spawnSync("mountpoint", ["-q", mount]);
  if (mounted.error) {
    throw mounted.error;
  }
  if (mounted.status === 0 && run("sudo", ["umount", mount]) !== 0) {
    failed = true;
  }
}

if (save && !failed) {
  if (!tool || !lower || !upper) {
    throw new Error("Rust cache overlay paths are missing");
  }
  if (run("sudo", [tool, "merge", "-l", lower, "-u", upper, "-r", "-f"]) !== 0) {
    failed = true;
  }
}

process.exit(failed ? 1 : 0);
