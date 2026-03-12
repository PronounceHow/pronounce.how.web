import type { Syllable } from "@/lib/types";

interface SyllableBreakdownProps {
  syllables: Syllable[];
}

export function SyllableBreakdown({ syllables }: SyllableBreakdownProps) {
  if (!syllables || syllables.length === 0) return null;

  return (
    <div className="flex items-center gap-1 flex-wrap">
      {syllables.map((syl, i) => (
        <span key={i} className="flex items-center">
          {i > 0 && <span className="text-gray-300 mx-1">·</span>}
          <span
            className={`px-2 py-1 rounded-md text-sm font-medium ${
              syl.stress === "primary"
                ? "bg-brand-100 text-brand-700 ring-1 ring-brand-200"
                : syl.stress === "secondary"
                ? "bg-amber-50 text-amber-700 ring-1 ring-amber-200"
                : "bg-gray-100 text-gray-600"
            }`}
          >
            <span className="block text-xs opacity-60 font-mono">{syl.ipa}</span>
            <span>{syl.text}</span>
          </span>
        </span>
      ))}
    </div>
  );
}
