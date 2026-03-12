import fs from "fs";
import path from "path";
import type { WordData, WordSummary } from "./types";

// Try local data directory first (for Vercel deployment), then fall back to sibling repo (for local dev)
const localDataDir = path.resolve(process.cwd(), "data", "words");
const siblingDataDir = path.resolve(process.cwd(), "..", "..", "pronounce-how-data", "data", "words");

const DATA_DIR = fs.existsSync(localDataDir) ? localDataDir : siblingDataDir;

export function getWordSlugs(): string[] {
  const slugs: string[] = [];
  const letters = fs.readdirSync(DATA_DIR).filter((d) => {
    const full = path.join(DATA_DIR, d);
    return fs.statSync(full).isDirectory() && /^[a-z]$/.test(d);
  });

  for (const letter of letters) {
    const letterDir = path.join(DATA_DIR, letter);
    const files = fs.readdirSync(letterDir).filter((f) => f.endsWith(".json"));
    for (const file of files) {
      slugs.push(file.replace(".json", ""));
    }
  }

  return slugs.sort();
}

export function getWordData(slug: string): WordData | null {
  const firstLetter = slug[0].toLowerCase();
  const filePath = path.join(DATA_DIR, firstLetter, `${slug}.json`);

  if (!fs.existsSync(filePath)) {
    return null;
  }

  const raw = fs.readFileSync(filePath, "utf-8");
  return JSON.parse(raw) as WordData;
}

export function getAllWords(): WordSummary[] {
  const slugs = getWordSlugs();
  const words: WordSummary[] = [];

  for (const slug of slugs) {
    const data = getWordData(slug);
    if (!data) continue;

    const usVariant = data.variants.find((v) => v.region === "US");
    words.push({
      word: data.word,
      slug: data.slug,
      pos: data.pos,
      ipa: usVariant?.ipa || data.variants[0]?.ipa || "",
      priority: data.priority,
    });
  }

  return words;
}

export function getWordsByLetter(letter: string): WordSummary[] {
  const letterDir = path.join(DATA_DIR, letter.toLowerCase());
  if (!fs.existsSync(letterDir)) return [];

  const files = fs.readdirSync(letterDir).filter((f) => f.endsWith(".json"));
  const words: WordSummary[] = [];

  for (const file of files) {
    const slug = file.replace(".json", "");
    const data = getWordData(slug);
    if (!data) continue;

    const usVariant = data.variants.find((v) => v.region === "US");
    words.push({
      word: data.word,
      slug: data.slug,
      pos: data.pos,
      ipa: usVariant?.ipa || data.variants[0]?.ipa || "",
      priority: data.priority,
    });
  }

  return words.sort((a, b) => a.word.localeCompare(b.word));
}

export function getStats(): {
  totalWords: number;
  totalVariants: number;
  byRegion: Record<string, number>;
  byPriority: Record<string, number>;
} {
  const slugs = getWordSlugs();
  let totalVariants = 0;
  const byRegion: Record<string, number> = {};
  const byPriority: Record<string, number> = {};

  for (const slug of slugs) {
    const data = getWordData(slug);
    if (!data) continue;

    byPriority[data.priority] = (byPriority[data.priority] || 0) + 1;

    for (const v of data.variants) {
      totalVariants++;
      byRegion[v.region] = (byRegion[v.region] || 0) + 1;
    }
  }

  return {
    totalWords: slugs.length,
    totalVariants,
    byRegion,
    byPriority,
  };
}

export function getRandomWord(): WordData | null {
  const slugs = getWordSlugs();
  if (slugs.length === 0) return null;

  // Use date as seed for "word of the day"
  const today = new Date().toISOString().slice(0, 10);
  let hash = 0;
  for (let i = 0; i < today.length; i++) {
    hash = (hash * 31 + today.charCodeAt(i)) | 0;
  }
  const idx = Math.abs(hash) % slugs.length;
  return getWordData(slugs[idx]);
}
