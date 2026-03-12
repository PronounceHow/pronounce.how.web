"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";

interface SearchResult {
  word: string;
  slug: string;
  ipa: string;
}

interface SearchBarProps {
  onWordSelect?: (slug: string) => void;
}

export function SearchBar({ onWordSelect }: SearchBarProps = {}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState(-1);
  const [searchIndex, setSearchIndex] = useState<SearchResult[] | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  // Load search index on first focus
  const loadIndex = useCallback(async () => {
    if (searchIndex) return;
    try {
      const res = await fetch("/search-index.json");
      const raw = await res.json();
      // Support both compact array format [word, slug, ipa] and object format
      const data: SearchResult[] = Array.isArray(raw[0])
        ? raw.map((r: [string, string, string]) => ({ word: r[0], slug: r[1], ipa: r[2] }))
        : raw;
      setSearchIndex(data);
    } catch {
      // Search index not available yet
    }
  }, [searchIndex]);

  useEffect(() => {
    if (!searchIndex || !query.trim()) {
      setResults([]);
      return;
    }

    const q = query.toLowerCase().trim();
    const matches = searchIndex
      .filter((w) => w.word.startsWith(q) || w.slug.startsWith(q))
      .slice(0, 8);

    // If no prefix match, try includes
    if (matches.length === 0) {
      const includes = searchIndex
        .filter((w) => w.word.includes(q) || w.slug.includes(q))
        .slice(0, 8);
      setResults(includes);
    } else {
      setResults(matches);
    }
    setSelectedIdx(-1);
  }, [query, searchIndex]);

  const navigateToWord = (slug: string) => {
    setQuery("");
    setIsOpen(false);
    if (onWordSelect) {
      onWordSelect(slug);
    } else {
      router.push(`/${slug}`);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIdx((prev) => Math.min(prev + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIdx((prev) => Math.max(prev - 1, -1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (selectedIdx >= 0 && results[selectedIdx]) {
        navigateToWord(results[selectedIdx].slug);
      } else if (query.trim()) {
        navigateToWord(query.trim().toLowerCase().replace(/\s+/g, "-"));
      }
    } else if (e.key === "Escape") {
      setIsOpen(false);
      inputRef.current?.blur();
    }
  };

  // Close dropdown on click outside
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div className="relative" ref={dropdownRef}>
      <div className="relative">
        <svg
          className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => {
            loadIndex();
            setIsOpen(true);
          }}
          onKeyDown={handleKeyDown}
          placeholder="Search for a word..."
          className="w-full pl-10 pr-4 py-2 rounded-full border border-gray-200 bg-gray-50 text-sm
                     focus:outline-none focus:ring-2 focus:ring-brand-300 focus:border-brand-300
                     focus:bg-white transition-all"
        />
      </div>

      {/* Dropdown results */}
      {isOpen && results.length > 0 && (
        <div className="absolute top-full mt-2 w-full bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden z-50">
          {results.map((r, idx) => (
            <button
              key={r.slug}
              onClick={() => navigateToWord(r.slug)}
              className={`w-full px-4 py-3 flex items-center justify-between text-left transition-colors
                ${idx === selectedIdx ? "bg-brand-50" : "hover:bg-gray-50"}`}
            >
              <span className="font-medium text-gray-900">{r.word}</span>
              <span className="text-xs font-mono text-gray-400">{r.ipa}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
