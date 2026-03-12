export interface Syllable {
  text: string;
  ipa: string;
  stress: "primary" | "secondary" | "unstressed";
}

export interface Variant {
  region: "US" | "UK" | "CA" | "AU";
  ipa: string;
  phonemes: string[];
  syllables: Syllable[];
  respelling: string;
  source_type: string;
  source_detail: string;
  confidence: number;
  confidence_reason: string;
  review?: string;
  derived_from?: string;
}

export interface CommonMistake {
  wrong_ipa: string;
  correct_ipa: string;
  description: string;
}

export interface RelatedWord {
  slug: string;
  relationship: "commonly_confused" | "us_uk_spelling" | "word_family";
}

export interface WordData {
  word: string;
  slug: string;
  lang: string;
  pos: string;
  priority: string;
  status: string;
  categories?: string[];
  variants: Variant[];
  context_sentence?: string;
  common_mistakes?: CommonMistake[];
  alternates?: Array<{ ipa: string; note?: string }>;
  related_words?: RelatedWord[];
  etymology_note?: string;
  updated_at: string;
  created_at: string;
  cross_validation?: {
    cmu_match: boolean;
    britfone_match: boolean;
    espeak_match: boolean;
  };
}

export const CATEGORY_LABELS: Record<string, string> = {
  medical: "Medical",
  legal: "Legal",
  culinary: "Food & Cooking",
  animals: "Animals",
  technology: "Technology",
  music: "Music",
  science: "Science",
  sports: "Sports",
  business: "Business",
  education: "Education",
  clothing: "Fashion",
};

export const RELATIONSHIP_LABELS: Record<string, string> = {
  commonly_confused: "Commonly confused with",
  us_uk_spelling: "Spelling variant",
  word_family: "Related word",
};

export interface WordSummary {
  word: string;
  slug: string;
  pos: string;
  ipa: string;
  priority: string;
}

export const REGION_FLAGS: Record<string, string> = {
  US: "\u{1F1FA}\u{1F1F8}",
  UK: "\u{1F1EC}\u{1F1E7}",
  CA: "\u{1F1E8}\u{1F1E6}",
  AU: "\u{1F1E6}\u{1F1FA}",
};

export const REGION_NAMES: Record<string, string> = {
  US: "American",
  UK: "British",
  CA: "Canadian",
  AU: "Australian",
};
