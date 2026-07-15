import { readFileSync } from "node:fs";
import { timingSafeEqual } from "node:crypto";
import { fileURLToPath } from "node:url";

const canonical = readFileSync(fileURLToPath(new URL("../../scripts/install-from-github.ps1", import.meta.url)));
const bundled = readFileSync(fileURLToPath(new URL("../lib/install-from-github.ps1", import.meta.url)));
if (canonical.length !== bundled.length || !timingSafeEqual(canonical, bundled)) {
  throw new Error("npm/lib/install-from-github.ps1 is out of sync with scripts/install-from-github.ps1");
}
console.log("Bundled bootstrap is synchronized with the canonical installer.");
