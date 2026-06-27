// Legacy esbuild helper retained only as a migration reference.
// The active production build is `npm run build`, backed by Vite.
import { mkdir, cp, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "esbuild";

const frontendDir = fileURLToPath(new URL(".", import.meta.url));
const distDir = resolve(frontendDir, "dist");
const assetsDir = resolve(distDir, "assets");

await rm(distDir, { recursive: true, force: true });
await mkdir(assetsDir, { recursive: true });

await build({
  entryPoints: [resolve(frontendDir, "src/app.mjs")],
  bundle: true,
  minify: true,
  format: "esm",
  sourcemap: false,
  entryNames: "assets/app-[hash]",
  outdir: distDir
});

await cp(resolve(frontendDir, "src/locales"), resolve(distDir, "src/locales"), { recursive: true });
await cp(resolve(frontendDir, "styles.css"), resolve(distDir, "styles.css"));

const index = await readFile(resolve(frontendDir, "index.html"), "utf8");
const assets = await readdir(assetsDir);
const appAsset = assets.find((name) => /^app-[A-Z0-9]+\.js$/.test(name));
if (!appAsset) {
  throw new Error("Unable to find built app asset.");
}
await writeFile(
  resolve(distDir, "index.html"),
  index.replace('/src/app.mjs', `/assets/${appAsset}`),
  "utf8"
);
