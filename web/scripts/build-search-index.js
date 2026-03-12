#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

// Find data directory
const localDataDir = path.resolve(__dirname, '..', 'data', 'words');
const siblingDataDir = path.resolve(__dirname, '..', '..', '..', 'pronounce-how-data', 'data', 'words');
const DATA_DIR = fs.existsSync(localDataDir) ? localDataDir : siblingDataDir;

const OUTPUT = path.resolve(__dirname, '..', 'public', 'search-index.json');

console.log('Building search index from:', DATA_DIR);

if (!fs.existsSync(DATA_DIR)) {
  console.error('ERROR: Data directory not found');
  process.exit(1);
}

const entries = [];
const letters = fs.readdirSync(DATA_DIR)
  .filter(d => fs.statSync(path.join(DATA_DIR, d)).isDirectory() && /^[a-z]$/.test(d))
  .sort();

for (const letter of letters) {
  const letterDir = path.join(DATA_DIR, letter);
  const files = fs.readdirSync(letterDir).filter(f => f.endsWith('.json')).sort();

  for (const file of files) {
    try {
      const raw = fs.readFileSync(path.join(letterDir, file), 'utf-8');
      const data = JSON.parse(raw);
      const usVariant = data.variants?.find(v => v.region === 'US');

      // Compact format: [word, slug, ipa]
      // Using arrays instead of objects saves ~30% JSON overhead
      entries.push([
        data.word,
        data.slug,
        usVariant?.ipa || data.variants?.[0]?.ipa || '',
      ]);
    } catch {
      // Skip invalid files
    }
  }
}

fs.writeFileSync(OUTPUT, JSON.stringify(entries));
const sizeKB = (fs.statSync(OUTPUT).size / 1024).toFixed(1);
console.log(`✓ Search index: ${entries.length} entries, ${sizeKB} KB`);
