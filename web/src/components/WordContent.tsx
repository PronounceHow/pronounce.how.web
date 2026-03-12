"use client";

import { useState } from "react";
import Link from "next/link";
import type { WordData } from "@/lib/types";
import { REGION_FLAGS, REGION_NAMES, CATEGORY_LABELS, RELATIONSHIP_LABELS } from "@/lib/types";
import { RegionTabs } from "./RegionTabs";
import { AudioPlayer } from "./AudioPlayer";
import { SyllableBreakdown } from "./SyllableBreakdown";
import { ConfidenceBadge } from "./ConfidenceBadge";

interface WordContentProps {
  data: WordData;
  isComparison?: boolean;
}

export function WordContent({ data, isComparison = false }: WordContentProps) {
  const regions = data.variants.map((v) => v.region) as string[];
  const [activeRegion, setActiveRegion] = useState<string>(regions[0] || "US");
  const variant = data.variants.find((v) => v.region === activeRegion) || data.variants[0];

  if (!variant) return null;

  return (
    <div className="flex flex-col gap-6">
      {/* Word header */}
      <div>
        <div className="flex items-baseline gap-3 mb-2">
          <h2 className={`font-extrabold text-gray-900 ${isComparison ? "text-2xl sm:text-3xl" : "text-4xl sm:text-5xl"}`}>
            {data.word}
          </h2>
          {data.pos && data.pos !== "other" && (
            <span className="px-2 py-0.5 rounded-full bg-gray-100 text-xs font-medium text-gray-500 uppercase">
              {data.pos}
            </span>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          {data.status && data.status !== "standard" && (
            <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
              data.status === "regional"
                ? "bg-blue-50 text-blue-700"
                : data.status === "disputed"
                ? "bg-amber-50 text-amber-700"
                : "bg-gray-100 text-gray-600"
            }`}>
              {data.status}
            </span>
          )}
          {data.categories?.map((cat) => (
            <span
              key={cat}
              className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-purple-50 text-purple-700"
            >
              {CATEGORY_LABELS[cat] || cat}
            </span>
          ))}
        </div>
      </div>

      {/* Region tabs */}
      <div>
        <RegionTabs
          regions={regions}
          activeRegion={activeRegion}
          onRegionChange={setActiveRegion}
        />
      </div>

      {/* Main pronunciation card */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
        {/* Audio + IPA */}
        <div className="flex flex-col sm:flex-row sm:items-center gap-4 mb-6">
          <AudioPlayer slug={data.slug} region={activeRegion} />
          <div>
            <div className="ipa-text text-gray-700">{variant.ipa}</div>
            <div className="respelling-text text-gray-900 mt-1">
              {variant.respelling}
            </div>
          </div>
        </div>

        {/* Syllable breakdown */}
        <div className="mb-6">
          <h3 className="text-xs uppercase tracking-wider text-gray-400 font-semibold mb-3">
            Syllable Breakdown
          </h3>
          <SyllableBreakdown syllables={variant.syllables} />
        </div>

        {/* Confidence / source */}
        <div>
          <h3 className="text-xs uppercase tracking-wider text-gray-400 font-semibold mb-2">
            Source
          </h3>
          <ConfidenceBadge
            confidence={variant.confidence}
            sourceType={variant.source_type}
            sourceDetail={variant.source_detail}
            derivedFrom={variant.derived_from}
          />
        </div>
      </div>

      {/* All variants comparison */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-base font-bold text-gray-900 mb-4">All Variants</h3>
        <div className="grid grid-cols-1 gap-3">
          {data.variants.map((v) => (
            <button
              key={v.region}
              onClick={() => setActiveRegion(v.region)}
              className={`p-3 rounded-xl border text-left transition-all ${
                v.region === activeRegion
                  ? "border-brand-300 bg-brand-50 ring-1 ring-brand-200"
                  : "border-gray-200 hover:border-gray-300 hover:bg-gray-50"
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="text-base">{REGION_FLAGS[v.region]}</span>
                <span className="font-semibold text-xs text-gray-900">
                  {REGION_NAMES[v.region]}
                </span>
              </div>
              <div className="font-mono text-xs text-gray-600">{v.ipa}</div>
              <div className="text-sm font-medium text-gray-800 mt-1">
                {v.respelling}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Context sentence */}
      {!isComparison && data.context_sentence && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-base font-bold text-gray-900 mb-3">Example</h3>
          <p className="text-gray-600 italic text-base">
            &ldquo;{data.context_sentence}&rdquo;
          </p>
        </div>
      )}

      {/* Common mistakes */}
      {!isComparison && data.common_mistakes && data.common_mistakes.length > 0 && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-base font-bold text-gray-900 mb-4">
            Common Mistakes
          </h3>
          <div className="space-y-3">
            {data.common_mistakes.map((m, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-red-50">
                <span className="text-red-500 mt-0.5">✗</span>
                <div>
                  <div className="font-mono text-sm">
                    <span className="text-red-600 line-through">{m.wrong_ipa}</span>
                    <span className="mx-2 text-gray-400">→</span>
                    <span className="text-emerald-600">{m.correct_ipa}</span>
                  </div>
                  <p className="text-sm text-gray-600 mt-1">{m.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Related words */}
      {!isComparison && data.related_words && data.related_words.length > 0 && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-base font-bold text-gray-900 mb-4">Related Words</h3>
          <div className="flex flex-wrap gap-2">
            {data.related_words.map((rw) => (
              <Link
                key={rw.slug}
                href={`/${rw.slug}`}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-gray-50 border border-gray-200 hover:border-brand-300 hover:bg-brand-50 transition-all"
              >
                <span className="font-medium text-gray-900">{rw.slug}</span>
                <span className="text-xs text-gray-400">
                  {RELATIONSHIP_LABELS[rw.relationship] || rw.relationship}
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
