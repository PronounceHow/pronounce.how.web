"use client";

import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

const LETTERS = "abcdefghijklmnopqrstuvwxyz".split("");

interface WordEntry {
  word: string;
  slug: string;
  ipa: string;
  pos: string;
}

export function BrowseClient() {
  const searchParams = useSearchParams();
  const letterParam = searchParams.get("letter")?.toLowerCase() || "a";
  const [activeLetter, setActiveLetter] = useState(letterParam);
  const [words, setWords] = useState<WordEntry[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [cache, setCache] = useState<Record<string, WordEntry[]>>({});

  // Load counts once
  useEffect(() => {
    fetch("/browse-data/counts.json")
      .then((res) => res.json())
      .then((data) => setCounts(data))
      .catch(() => {});
  }, []);

  // Load letter data
  const loadLetter = useCallback(
    async (letter: string) => {
      if (cache[letter]) {
        setWords(cache[letter]);
        setLoading(false);
        return;
      }

      setLoading(true);
      try {
        const res = await fetch(`/browse-data/${letter}.json`);
        const data: WordEntry[] = await res.json();
        setCache((prev) => ({ ...prev, [letter]: data }));
        setWords(data);
      } catch {
        setWords([]);
      }
      setLoading(false);
    },
    [cache]
  );

  // Load on mount and letter change
  useEffect(() => {
    loadLetter(activeLetter);
  }, [activeLetter, loadLetter]);

  // Sync with URL query param changes
  useEffect(() => {
    const l = searchParams.get("letter")?.toLowerCase();
    if (l && l !== activeLetter && LETTERS.includes(l)) {
      setActiveLetter(l);
    }
  }, [searchParams, activeLetter]);

  return (
    <>
      {/* Letter tabs */}
      <div className="flex flex-wrap gap-2 mb-8">
        {LETTERS.map((letter) => (
          <button
            key={letter}
            onClick={() => setActiveLetter(letter)}
            className={`w-12 h-12 flex items-center justify-center rounded-xl text-base font-bold
                         transition-all uppercase ${
                           activeLetter === letter
                             ? "bg-brand-500 text-white shadow-md"
                             : "bg-white border border-gray-200 text-gray-700 hover:bg-gray-50"
                         }`}
          >
            {letter}
          </button>
        ))}
      </div>

      {/* Count */}
      <p className="text-sm text-gray-500 mb-4">
        {counts[activeLetter] || 0} words starting with &ldquo;{activeLetter.toUpperCase()}&rdquo;
      </p>

      {/* Word list */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="w-6 h-6 border-2 border-brand-300 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {words.map((w) => (
            <Link
              key={w.slug}
              href={`/${w.slug}`}
              className="group flex items-center justify-between p-3 rounded-xl bg-white border border-gray-200
                         hover:border-brand-300 hover:shadow-sm transition-all"
            >
              <div>
                <span className="font-medium text-gray-900 group-hover:text-brand-600 transition-colors">
                  {w.word}
                </span>
                {w.pos && w.pos !== "other" && (
                  <span className="ml-2 text-xs text-gray-400">{w.pos}</span>
                )}
              </div>
              <span className="font-mono text-xs text-gray-400">{w.ipa}</span>
            </Link>
          ))}
        </div>
      )}

      {!loading && words.length === 0 && (
        <p className="text-gray-500 py-8 text-center">
          No words found for this letter.
        </p>
      )}
    </>
  );
}
