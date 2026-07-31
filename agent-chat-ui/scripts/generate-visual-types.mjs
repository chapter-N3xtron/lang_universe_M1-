import { readFile, writeFile } from "node:fs/promises";
import process from "node:process";
import { compile } from "json-schema-to-typescript";

const schemaUrl = new URL(
  "../src/lib/visual/jasper-response.schema.json",
  import.meta.url,
);
const outputUrl = new URL(
  "../src/lib/visual/jasper-response.generated.ts",
  import.meta.url,
);

const schema = JSON.parse(await readFile(schemaUrl, "utf8"));
const generated = await compile(schema, "JasperResponse", {
  bannerComment:
    "/* Generated from backend/src/visual_models.py. Do not edit manually. */",
  format: true,
  unknownAny: false,
});

if (process.argv.includes("--check")) {
  const committed = await readFile(outputUrl, "utf8").catch(() => "");
  if (committed !== generated) {
    console.error(
      "Visual response types are stale. Run: pnpm visual-schema:generate",
    );
    process.exitCode = 1;
  }
} else {
  await writeFile(outputUrl, generated);
  console.log("src/lib/visual/jasper-response.generated.ts");
}
