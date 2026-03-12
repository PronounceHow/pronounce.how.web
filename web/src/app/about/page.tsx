import type { Metadata } from "next";
import { getStats } from "@/lib/data";

export const metadata: Metadata = {
  title: "About",
  description:
    "About pronounce.how — an open-source English pronunciation guide.",
};

export default function AboutPage() {
  const stats = getStats();

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-12">
      <h1 className="text-3xl font-extrabold text-gray-900 mb-6">About</h1>

      <div className="prose prose-gray max-w-none">
        <p className="text-lg text-gray-600 leading-relaxed">
          <strong>pronounce.how</strong> is an open-source English pronunciation
          guide that provides IPA transcriptions, audio, and syllable breakdowns
          for {stats.totalWords.toLocaleString()} words across four major English
          dialects: American, British, Canadian, and Australian.
        </p>

        <h2 className="text-xl font-bold text-gray-900 mt-8 mb-4">
          Why This Exists
        </h2>
        <p className="text-gray-600 leading-relaxed">
          Most pronunciation resources focus on a single dialect or lack the
          transparency to show where their data comes from. pronounce.how is
          built on the belief that pronunciation data should be open, verifiable,
          and comprehensive across regions. Every entry shows its source,
          confidence level, and whether it&apos;s been verified by native speakers.
        </p>

        <h2 className="text-xl font-bold text-gray-900 mt-8 mb-4">
          Data Sources
        </h2>
        <div className="space-y-3">
          {[
            {
              icon: "📘",
              name: "CMU Pronouncing Dictionary",
              desc: "~134k American English pronunciations in ARPAbet notation. The gold standard for US pronunciation data.",
            },
            {
              icon: "📗",
              name: "Britfone",
              desc: "~16k British English pronunciations in IPA. Curated phonetic dictionary for Received Pronunciation.",
            },
            {
              icon: "🔊",
              name: "eSpeak NG",
              desc: "Open-source speech synthesizer used for Australian English pronunciation and gap-filling.",
            },
            {
              icon: "📖",
              name: "Wiktionary (via Wiktextract)",
              desc: "Cross-validation source for IPA transcriptions and part-of-speech data.",
            },
          ].map((source) => (
            <div
              key={source.name}
              className="flex gap-3 p-4 rounded-xl bg-white border border-gray-200"
            >
              <span className="text-2xl shrink-0">{source.icon}</span>
              <div>
                <div className="font-semibold text-gray-900">{source.name}</div>
                <p className="text-sm text-gray-500 mt-0.5">{source.desc}</p>
              </div>
            </div>
          ))}
        </div>

        <h2 className="text-xl font-bold text-gray-900 mt-8 mb-4">
          How Confidence Works
        </h2>
        <p className="text-gray-600 leading-relaxed">
          Every pronunciation variant has a confidence score from 0 to 1. This
          reflects how trustworthy we believe the transcription to be:
        </p>
        <ul className="mt-3 space-y-2 text-gray-600">
          <li className="flex items-start gap-2">
            <span className="text-emerald-500 font-bold">90%+</span>
            <span>Primary dictionary source (CMU Dict, Britfone), confirmed by cross-validation</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-amber-500 font-bold">60-89%</span>
            <span>Secondary source, derived variant, or partial cross-validation</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-red-500 font-bold">&lt;60%</span>
            <span>eSpeak gap-fill or unverified derivation. Help us verify these!</span>
          </li>
        </ul>

        <h2 className="text-xl font-bold text-gray-900 mt-8 mb-4">
          Open Source
        </h2>
        <p className="text-gray-600 leading-relaxed">
          All pronunciation data is open source and available on GitHub under CC
          BY-SA 4.0. The website code is also open source. We welcome
          contributions — especially native speaker verifications for Canadian and
          Australian English.
        </p>
        <div className="flex gap-3 mt-4">
          <a
            href="https://github.com/PronounceHow/pronounce.how"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-900 text-white text-sm font-medium hover:bg-gray-800 transition-colors"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 16 16">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
            </svg>
            Data Repository
          </a>
        </div>

        <h2 className="text-xl font-bold text-gray-900 mt-8 mb-4">License</h2>
        <p className="text-gray-600 leading-relaxed">
          Pronunciation data: CC BY-SA 4.0. Website code: MIT. Please see
          individual source attributions in the data repository.
        </p>
      </div>
    </div>
  );
}
