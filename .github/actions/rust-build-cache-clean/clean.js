const {spawnSync} = require("child_process");
const path = require("path");

const result = spawnSync("python3", [path.join(__dirname, "clean.py")], {
  stdio: "inherit",
});

if (result.error) {
  throw result.error;
}
process.exit(result.status ?? 1);
