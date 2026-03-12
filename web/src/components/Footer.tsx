import Link from "next/link";

export function Footer() {
  return (
    <footer className="bg-white border-t border-gray-200 mt-16">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Brand */}
          <div>
            <Link href="/" className="flex items-center gap-2">
              <span className="text-xl">🗣️</span>
              <span className="font-bold text-lg text-gray-900">
                pronounce<span className="text-brand-500">.how</span>
              </span>
            </Link>
            <p className="mt-3 text-sm text-gray-500">
              Open-source English pronunciation guide with IPA transcriptions,
              audio, and regional variants.
            </p>
          </div>

          {/* Links */}
          <div>
            <h3 className="font-semibold text-sm text-gray-900 uppercase tracking-wider">
              Explore
            </h3>
            <ul className="mt-3 space-y-2">
              <li>
                <Link href="/browse" className="text-sm text-gray-500 hover:text-gray-900">
                  Browse Words
                </Link>
              </li>
              <li>
                <Link href="/about" className="text-sm text-gray-500 hover:text-gray-900">
                  About
                </Link>
              </li>
            </ul>
          </div>

          {/* Community */}
          <div>
            <h3 className="font-semibold text-sm text-gray-900 uppercase tracking-wider">
              Community
            </h3>
            <ul className="mt-3 space-y-2">
              <li>
                <a
                  href="https://github.com/PronounceHow/pronounce.how"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-gray-500 hover:text-gray-900"
                >
                  GitHub Data Repo
                </a>
              </li>
              <li>
                <a
                  href="https://github.com/PronounceHow/pronounce.how/issues/new"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-gray-500 hover:text-gray-900"
                >
                  Report an Issue
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-8 pt-6 border-t border-gray-100">
          <p className="text-xs text-gray-400 text-center">
            Data sourced from CMU Pronouncing Dictionary, Britfone, eSpeak NG, and Wiktionary.
            Licensed under CC BY-SA 4.0.
          </p>
        </div>
      </div>
    </footer>
  );
}
