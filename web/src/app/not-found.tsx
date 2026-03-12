import Link from "next/link";

export default function NotFound() {
  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-24 text-center">
      <div className="text-6xl mb-4">🤔</div>
      <h1 className="text-3xl font-extrabold text-gray-900 mb-3">
        Word Not Found
      </h1>
      <p className="text-gray-500 mb-6">
        We don&apos;t have a pronunciation entry for this word yet.
      </p>
      <div className="flex justify-center gap-3">
        <Link
          href="/"
          className="px-4 py-2 rounded-lg bg-brand-500 text-white text-sm font-medium hover:bg-brand-600 transition-colors"
        >
          Search for a word
        </Link>
        <Link
          href="/browse"
          className="px-4 py-2 rounded-lg bg-gray-100 text-gray-700 text-sm font-medium hover:bg-gray-200 transition-colors"
        >
          Browse all words
        </Link>
      </div>
    </div>
  );
}
