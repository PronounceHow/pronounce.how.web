import { Suspense } from "react";
import type { Metadata } from "next";
import { BrowseClient } from "./BrowseClient";

export const metadata: Metadata = {
  title: "Browse Words",
  description: "Browse all pronunciation entries by letter on pronounce.how.",
  alternates: {
    canonical: "https://pronounce.how/browse",
  },
};

export default function BrowsePage() {
  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
      <h1 className="text-3xl font-extrabold text-gray-900 mb-6">Browse Words</h1>

      <Suspense fallback={<div>Loading...</div>}>
        <BrowseClient />
      </Suspense>
    </div>
  );
}
