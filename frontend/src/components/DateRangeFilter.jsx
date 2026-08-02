import React from "react";
import { CalendarRange, GitCompareArrows } from "lucide-react";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";

export const RANGES = [
  { key: "7d", label: "Last 7 days", days: 7 },
  { key: "30d", label: "Last 30 days", days: 30 },
  { key: "90d", label: "Last 90 days", days: 90 },
  { key: "all", label: "All time", days: null },
];

export function rangeToDates(key) {
  const r = RANGES.find((x) => x.key === key) || RANGES[1];
  if (r.days == null) return { start: undefined, end: undefined };
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - (r.days - 1));
  const fmt = (d) => d.toISOString().slice(0, 10);
  return { start: fmt(start), end: fmt(end) };
}

export default function DateRangeFilter({ value, onChange, compare, onCompareChange }) {
  const canCompare = value !== "all";
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="w-[160px] gap-2" data-testid="date-range-select">
          <CalendarRange className="h-4 w-4 text-muted-foreground" />
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {RANGES.map((r) => (
            <SelectItem key={r.key} value={r.key} data-testid={`range-option-${r.key}`}>
              {r.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {onCompareChange && (
        <Button
          variant={compare && canCompare ? "default" : "outline"}
          size="sm"
          className="gap-2"
          disabled={!canCompare}
          onClick={() => onCompareChange(!compare)}
          data-testid="compare-toggle-btn"
        >
          <GitCompareArrows className="h-4 w-4" />
          Compare
        </Button>
      )}
    </div>
  );
}
