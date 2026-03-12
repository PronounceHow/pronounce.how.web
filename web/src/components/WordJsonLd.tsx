import type { WordData } from "@/lib/types";
import { REGION_NAMES } from "@/lib/types";

interface WordJsonLdProps {
  data: WordData;
}

export function WordJsonLd({ data }: WordJsonLdProps) {
  const usVariant = data.variants.find((v) => v.region === "US");
  const ukVariant = data.variants.find((v) => v.region === "UK");
  const primaryVariant = usVariant || data.variants[0];

  // HowTo schema — "How to pronounce X"
  const howToSteps = data.variants.map((v, i) => ({
    "@type": "HowToStep",
    position: i + 1,
    name: `${REGION_NAMES[v.region] || v.region} English pronunciation`,
    text: `${REGION_NAMES[v.region] || v.region}: ${v.ipa} — ${v.respelling}`,
  }));

  const howTo = {
    "@context": "https://schema.org",
    "@type": "HowTo",
    name: `How to Pronounce "${data.word}"`,
    description: `Learn the correct pronunciation of "${data.word}" in ${data.variants
      .map((v) => REGION_NAMES[v.region] || v.region)
      .join(", ")} English with IPA transcriptions and audio.`,
    step: howToSteps,
    ...(primaryVariant && {
      about: {
        "@type": "DefinedTerm",
        name: data.word,
        description: `English word "${data.word}" — IPA: ${primaryVariant.ipa}`,
        inDefinedTermSet: {
          "@type": "DefinedTermSet",
          name: "English Pronunciation Dictionary",
        },
      },
    }),
  };

  // WebPage schema
  const webPage = {
    "@context": "https://schema.org",
    "@type": "WebPage",
    name: `How to Pronounce "${data.word}" | pronounce.how`,
    description: `Pronunciation guide for "${data.word}" with IPA, audio, and syllable breakdown for US, UK, Canadian, and Australian English.`,
    url: `https://pronounce.how/${data.slug}`,
    isPartOf: {
      "@type": "WebSite",
      name: "pronounce.how",
      url: "https://pronounce.how",
    },
    dateModified: data.updated_at,
    datePublished: data.created_at,
    inLanguage: "en",
  };

  // FAQPage schema for "how do you pronounce X" queries
  const faq = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: [
      {
        "@type": "Question",
        name: `How do you pronounce "${data.word}"?`,
        acceptedAnswer: {
          "@type": "Answer",
          text: data.variants
            .map(
              (v) =>
                `In ${REGION_NAMES[v.region] || v.region} English: ${v.ipa} (${v.respelling})`
            )
            .join(". ") + ".",
        },
      },
      ...(usVariant && ukVariant && usVariant.ipa !== ukVariant.ipa
        ? [
            {
              "@type": "Question",
              name: `Is "${data.word}" pronounced differently in American and British English?`,
              acceptedAnswer: {
                "@type": "Answer",
                text: `Yes. In American English it's pronounced ${usVariant.ipa} (${usVariant.respelling}), while in British English it's ${ukVariant.ipa} (${ukVariant.respelling}).`,
              },
            },
          ]
        : []),
    ],
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(howTo) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(webPage) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faq) }}
      />
    </>
  );
}
