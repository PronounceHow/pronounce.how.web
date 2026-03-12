interface ConfidenceBadgeProps {
  confidence: number;
  sourceType: string;
  sourceDetail: string;
  derivedFrom?: string;
}

const SOURCE_ICONS: Record<string, string> = {
  cmu_dict: "📘",
  britfone: "📗",
  espeak: "🔊",
  wiktionary: "📖",
  manual: "✏️",
};

export function ConfidenceBadge({
  confidence,
  sourceType,
  sourceDetail,
  derivedFrom,
}: ConfidenceBadgeProps) {
  const pct = Math.round(confidence * 100);
  const level =
    confidence >= 0.8 ? "high" : confidence >= 0.6 ? "medium" : "low";

  const colorClasses = {
    high: "text-emerald-700 bg-emerald-50 ring-emerald-200",
    medium: "text-amber-700 bg-amber-50 ring-amber-200",
    low: "text-red-700 bg-red-50 ring-red-200",
  };

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ring-1 ${colorClasses[level]}`}
      >
        <span>{pct}%</span>
        confidence
      </span>

      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-600 ring-1 ring-gray-200">
        {SOURCE_ICONS[sourceType] || "📄"} {sourceDetail}
      </span>

      {derivedFrom && (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-blue-50 text-blue-700 ring-1 ring-blue-200">
          🔄 Based on {derivedFrom}
        </span>
      )}
    </div>
  );
}
