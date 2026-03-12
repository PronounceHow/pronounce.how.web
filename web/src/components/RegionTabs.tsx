"use client";

import { REGION_FLAGS, REGION_NAMES } from "@/lib/types";

interface RegionTabsProps {
  regions: string[];
  activeRegion: string;
  onRegionChange: (region: string) => void;
}

export function RegionTabs({ regions, activeRegion, onRegionChange }: RegionTabsProps) {
  return (
    <div className="flex gap-2 flex-wrap">
      {regions.map((region) => (
        <button
          key={region}
          onClick={() => onRegionChange(region)}
          className={`region-tab ${
            activeRegion === region ? "region-tab-active" : "region-tab-inactive"
          }`}
        >
          <span className="mr-1">{REGION_FLAGS[region]}</span>
          {REGION_NAMES[region] || region}
        </button>
      ))}
    </div>
  );
}
