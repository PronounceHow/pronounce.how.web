import Link from "next/link";
import type { Metadata } from "next";
import { getStats, getRandomWord } from "@/lib/data";
import { REGION_FLAGS, REGION_NAMES } from "@/lib/types";
import { SearchBar } from "@/components/SearchBar";

export const metadata: Metadata = {
  alternates: {
    canonical: "https://pronounce.how",
  },
};

function HomeJsonLd({ totalWords }: { totalWords: number }) {
  const websiteSchema = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "pronounce.how",
    url: "https://pronounce.how",
    description: `Open-source English pronunciation guide with ${totalWords.toLocaleString()} words, IPA transcriptions, audio, and regional variants.`,
    potentialAction: {
      "@type": "SearchAction",
      target: {
        "@type": "EntryPoint",
        urlTemplate: "https://pronounce.how/{search_term_string}",
      },
      "query-input": "required name=search_term_string",
    },
  };

  const orgSchema = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "pronounce.how",
    url: "https://pronounce.how",
    logo: "https://pronounce.how/favicon.svg",
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(orgSchema) }}
      />
    </>
  );
}

export default function HomePage() {
  const stats = getStats();
  const wordOfDay = getRandomWord();

  const letters = "abcdefghijklmnopqrstuvwxyz".split("");

  return (
    <div>
      <HomeJsonLd totalWords={stats.totalWords} />
      {/* Hero */}
      <section className="bg-gradient-to-br from-brand-50 via-white to-amber-50 py-16 sm:py-24">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 text-center">
          <h1 className="text-4xl sm:text-6xl font-extrabold text-gray-900 mb-4">
            Learn how to
            <br />
            <span className="text-brand-500">pronounce</span> it right
          </h1>
          <p className="text-lg text-gray-500 mb-8 max-w-xl mx-auto">
            {stats.totalWords.toLocaleString()} English words with IPA transcriptions,
            audio, and regional variants for US, UK, Canadian, and Australian English.
          </p>

          {/* Search */}
          <div className="max-w-md mx-auto">
            <SearchBar />
          </div>
        </div>
      </section>

      {/* Word of the Day */}
      {wordOfDay && (
        <section className="max-w-3xl mx-auto px-4 sm:px-6 -mt-8">
          <Link href={`/${wordOfDay.slug}`}>
            <div className="bg-white rounded-2xl shadow-md border border-gray-200 p-6 hover:shadow-lg transition-shadow">
              <div className="text-xs uppercase tracking-wider text-gray-400 font-semibold mb-2">
                Word of the Day
              </div>
              <div className="flex items-baseline gap-3">
                <span className="text-3xl font-bold text-gray-900">
                  {wordOfDay.word}
                </span>
                <span className="font-mono text-gray-500">
                  {wordOfDay.variants[0]?.ipa}
                </span>
              </div>
              <div className="text-lg font-medium text-brand-600 mt-1">
                {wordOfDay.variants[0]?.respelling}
              </div>
              <div className="flex gap-2 mt-3">
                {wordOfDay.variants.map((v) => (
                  <span
                    key={v.region}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-100 text-xs text-gray-600"
                  >
                    {REGION_FLAGS[v.region]} {REGION_NAMES[v.region]}
                  </span>
                ))}
              </div>
            </div>
          </Link>
        </section>
      )}

      {/* Stats */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 py-12">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
            <div className="text-2xl font-bold text-gray-900">
              {stats.totalWords.toLocaleString()}
            </div>
            <div className="text-xs text-gray-500 mt-1">Words</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
            <div className="text-2xl font-bold text-gray-900">
              {stats.totalVariants.toLocaleString()}
            </div>
            <div className="text-xs text-gray-500 mt-1">Pronunciations</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
            <div className="text-2xl font-bold text-gray-900">4</div>
            <div className="text-xs text-gray-500 mt-1">Regions</div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
            <div className="text-2xl font-bold text-gray-900">
              {(stats.byPriority["high"] || 0).toLocaleString()}
            </div>
            <div className="text-xs text-gray-500 mt-1">High Priority</div>
          </div>
        </div>
      </section>

      {/* Browse by Letter */}
      <section className="max-w-3xl mx-auto px-4 sm:px-6 pb-12">
        <h2 className="text-xl font-bold text-gray-900 mb-4">Browse by Letter</h2>
        <div className="flex flex-wrap gap-2 justify-center">
          {letters.map((letter) => (
            <Link
              key={letter}
              href={`/browse?letter=${letter}`}
              className="w-12 h-12 flex items-center justify-center rounded-xl bg-white border border-gray-200
                         text-base font-bold text-gray-700 hover:bg-brand-50 hover:border-brand-300
                         hover:text-brand-600 transition-all uppercase"
            >
              {letter}
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
