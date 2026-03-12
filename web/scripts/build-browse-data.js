#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

// Find data directory (same logic as data.ts)
const localDataDir = path.resolve(__dirname, '..', 'data', 'words');
const siblingDataDir = path.resolve(__dirname, '..', '..', '..', 'pronounce-how-data', 'data', 'words');
const DATA_DIR = fs.existsSync(localDataDir) ? localDataDir : siblingDataDir;

const outDir = path.resolve(__dirname, '..', 'public', 'browse-data');

console.log('Building browse data from:', DATA_DIR);
console.log('Output:', outDir);

if (!fs.existsSync(DATA_DIR)) {
  console.error('ERROR: Data directory not found');
  process.exit(1);
}

fs.mkdirSync(outDir, { recursive: true });

const letters = 'abcdefghijklmnopqrstuvwxyz'.split('');
const counts = {};

for (const letter of letters) {
  const letterDir = path.join(DATA_DIR, letter);
  if (!fs.existsSync(letterDir)) {
    counts[letter] = 0;
    fs.writeFileSync(path.join(outDir, `${letter}.json`), '[]');
    continue;
  }

  const files = fs.readdirSync(letterDir).filter(f => f.endsWith('.json'));
  const words = [];

  for (const file of files) {
    try {
      const raw = fs.readFileSync(path.join(letterDir, file), 'utf-8');
      const data = JSON.parse(raw);
      const usVariant = data.variants?.find(v => v.region === 'US');
      words.push({
        word: data.word,
        slug: data.slug,
        ipa: usVariant?.ipa || data.variants?.[0]?.ipa || '',
        pos: data.pos || '',
      });
    } catch {
      // Skip invalid files
    }
  }

  words.sort((a, b) => a.word.localeCompare(b.word));
  counts[letter] = words.length;

  fs.writeFileSync(
    path.join(outDir, `${letter}.json`),
    JSON.stringify(words)
  );
}

// Write counts file
fs.writeFileSync(
  path.join(outDir, 'counts.json'),
  JSON.stringify(counts)
);

const totalWords = Object.values(counts).reduce((a, b) => a + b, 0);
console.log(`✓ Generated browse data for ${totalWords} words across 26 letters`);
