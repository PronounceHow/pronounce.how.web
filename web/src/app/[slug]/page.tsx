import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { getWordData, getWordSlugs } from "@/lib/data";
import { REGION_FLAGS, REGION_NAMES } from "@/lib/types";
import { WordPageClient } from "@/components/WordPageClient";
import { WordJsonLd } from "@/components/WordJsonLd";

interface PageProps {
  params: { slug: string };
  searchParams: { compare?: string };
}

// Reserved paths that have their own routes — exclude from dynamic [slug]
const RESERVED_SLUGS = new Set(["browse", "about", "robots", "sitemap", "favicon", "ads"]);

export async function generateStaticParams() {
  const slugs = getWordSlugs().filter((s) => !RESERVED_SLUGS.has(s));
  return slugs.map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const data = getWordData(params.slug);
  if (!data) return { title: "Word not found" };

  const regions = data.variants.map((v) => REGION_NAMES[v.region] || v.region);
  const ipaHints = data.variants
    .filter((v) => v.ipa)
    .slice(0, 2)
    .map((v) => `${REGION_NAMES[v.region] || v.region} (${v.ipa})`)
    .join(", ");

  const regionList = regions.length > 1
    ? regions.slice(0, -1).join(", ") + ", and " + regions[regions.length - 1]
    : regions[0] || "";

  const description = `Learn how to pronounce "${data.word}" in ${regionList} English${ipaHints ? ` — ${ipaHints}` : ""}. With IPA, audio, and syllable breakdown.`;

  return {
    title: `How to Pronounce "${data.word}"`,
    description,
    alternates: {
      canonical: `https://pronounce.how/${data.slug}`,
    },
    openGraph: {
      title: `How to Pronounce "${data.word}" — ${regions.join(", ")} English`,
      description,
      url: `https://pronounce.how/${data.slug}`,
      type: "article",
    },
    twitter: {
      card: "summary",
      title: `How to Pronounce "${data.word}"`,
      description: `${data.variants.map((v) => `${REGION_FLAGS[v.region]} ${v.respelling}`).join("  ")}`,
    },
  };
}

export default function WordPage({ params, searchParams }: PageProps) {
  const data = getWordData(params.slug);
  if (!data) notFound();

  const compareSlug = searchParams.compare;
  const compareData = compareSlug ? getWordData(compareSlug) : null;

  return (
    <>
      <WordJsonLd data={data} />
      <WordPageClient data={data} compareData={compareData} />
    </>
  );
}
