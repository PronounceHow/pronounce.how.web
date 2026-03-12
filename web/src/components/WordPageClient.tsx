"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import type { WordData } from "@/lib/types";
import { AdUnit } from "./AdUnit";
import { SearchBar } from "./SearchBar";
import { WordContent } from "./WordContent";

const LETTERS = "abcdefghijklmnopqrstuvwxyz".split("");

interface WordPageClientProps {
  data: WordData;
}

export function WordPageClient({ data }: WordPageClientProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const compareSlug = searchParams.get("compare");
  const [compareData, setCompareData] = useState<WordData | null>(null);
  const [showCompareSearch, setShowCompareSearch] = useState(false);

  useEffect(() => {
    if (!compareSlug) {
      setCompareData(null);
      return;
    }
    fetch(`/word-data/${compareSlug[0]}/${compareSlug}.json`)
      .then((r) => r.ok ? r.json() : null)
      .then((d) => setCompareData(d))
      .catch(() => setCompareData(null));
  }, [compareSlug]);

  const handleCompareSearch = (word: string) => {
    router.push(`/${data.slug}?compare=${word}`);
  };

  const clearComparison = () => {
    router.push(`/${data.slug}`);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
      {/* Search bar */}
      <div className="mb-6 max-w-3xl mx-auto">
        <SearchBar />
      </div>

      {/* Comparison header or Compare button */}
      {compareData ? (
        <div className="bg-brand-50 border border-brand-200 rounded-2xl p-4 mb-6 max-w-3xl mx-auto">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-gray-700">Comparing:</span>
              <span className="font-bold text-gray-900">{data.word}</span>
              <span className="text-gray-400">vs.</span>
              <span className="font-bold text-gray-900">{compareData.word}</span>
            </div>
            <button
              onClick={clearComparison}
              className="text-gray-400 hover:text-gray-600 transition-colors"
              aria-label="Clear comparison"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      ) : (
        <div className="mb-6 max-w-3xl mx-auto">
          {showCompareSearch ? (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-gray-900">Compare with another word</h3>
                <button
                  onClick={() => setShowCompareSearch(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              <SearchBar onWordSelect={handleCompareSearch} />
            </div>
          ) : (
            <button
              onClick={() => setShowCompareSearch(true)}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2 rounded-xl bg-brand-50 border border-brand-200 text-brand-700 hover:bg-brand-100 transition-colors font-medium"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
              </svg>
              Compare with another word
            </button>
          )}
        </div>
      )}

      {/* Main content: Single word or comparison */}
      {compareData ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div>
            <WordContent data={data} isComparison={true} />
          </div>
          <div>
            <WordContent data={compareData} isComparison={true} />
          </div>
        </div>
      ) : (
        <div className="max-w-3xl mx-auto mb-6">
          <WordContent data={data} isComparison={false} />
        </div>
      )}

      {/* Ad: after main content */}
      <div className="max-w-3xl mx-auto mb-6">
        <AdUnit format="horizontal" />
      </div>

      {/* Ad: before footer links */}
      <div className="max-w-3xl mx-auto mb-6">
        <AdUnit format="auto" />
      </div>

      {/* Browse by Letter */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 mb-6 max-w-3xl mx-auto">
        <h2 className="text-lg font-bold text-gray-900 mb-4">Browse by Letter</h2>
        <div className="flex flex-wrap gap-2 justify-center">
          {LETTERS.map((letter) => (
            <Link
              key={letter}
              href={`/browse?letter=${letter}`}
              className={`w-12 h-12 flex items-center justify-center rounded-xl border text-base font-bold
                         transition-all uppercase ${
                           letter === data.slug[0]
                             ? "bg-brand-50 border-brand-300 text-brand-600 ring-1 ring-brand-200"
                             : "bg-gray-50 border-gray-200 text-gray-700 hover:bg-brand-50 hover:border-brand-300 hover:text-brand-600"
                         }`}
            >
              {letter}
            </Link>
          ))}
        </div>
      </div>

      {/* Links */}
      <div className="flex flex-wrap gap-3 text-sm max-w-3xl mx-auto">
        <a
          href={`https://github.com/PronounceHow/pronounce.how/blob/main/data/words/${data.slug[0]}/${data.slug}.json`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors"
        >
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 16 16">
            <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
          </svg>
          Edit on GitHub
        </a>
        <a
          href={`https://github.com/PronounceHow/pronounce.how/issues/new?title=Pronunciation+issue:+${data.word}`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors"
        >
          Report an issue
        </a>
      </div>

      {/* Last updated */}
      <p className="text-xs text-gray-400 mt-6 max-w-3xl mx-auto">
        Last updated: {data.updated_at}
      </p>
    </div>
  );
}
