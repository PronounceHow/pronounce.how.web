/**
 * Generate a lightweight search index JSON file for client-side search.
 * Run: npx ts-node --esm scripts/generate-search-index.ts
 * Or: npx tsx scripts/generate-search-index.ts
 */
import fs from "fs";
import path from "path";

const DATA_DIR = path.resolve(__dirname, "..", "..", "..", "pronounce-how-data", "data", "words");
const OUTPUT = path.resolve(__dirname, "..", "public", "search-index.json");

interface Entry {
  word: string;
  slug: string;
  ipa: string;
}

function main() {
  const entries: Entry[] = [];
  const letters = fs.readdirSync(DATA_DIR).filter((d) => {
    return fs.statSync(path.join(DATA_DIR, d)).isDirectory() && /^[a-z]$/.test(d);
  });

  for (const letter of letters.sort()) {
    const letterDir = path.join(DATA_DIR, letter);
    const files = fs.readdirSync(letterDir).filter((f) => f.endsWith(".json"));

    for (const file of files.sort()) {
      const raw = fs.readFileSync(path.join(letterDir, file), "utf-8");
      const data = JSON.parse(raw);

      const usVariant = data.variants?.find((v: any) => v.region === "US");
      entries.push({
        word: data.word,
        slug: data.slug,
        ipa: usVariant?.ipa || data.variants?.[0]?.ipa || "",
      });
    }
  }

  fs.writeFileSync(OUTPUT, JSON.stringify(entries));
  console.log(`Search index: ${entries.length} entries → ${OUTPUT}`);
  console.log(`Size: ${(fs.statSync(OUTPUT).size / 1024).toFixed(1)} KB`);
}

main();
