"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from "recharts";

import type { DailyActivity } from "@/lib/api/types";
import { formatDayLong, formatDayShort } from "@/lib/format";

/** Fixed categorical order (validated for colour-vision deficiencies): never reorder by rank. */
const SERIES = [
  { key: "residents", label: "Membres du foyer", color: "var(--series-1)" },
  { key: "guests", label: "Invités", color: "var(--series-2)" },
  { key: "unrecognised", label: "Non reconnus", color: "var(--series-3)" },
  { key: "animals", label: "Animaux", color: "var(--series-4)" },
] as const;

type Row = { day: string } & Record<(typeof SERIES)[number]["key"], number>;

function toRows(data: DailyActivity[]): Row[] {
  return data.map((d) => ({
    day: d.day,
    residents: d.residents,
    guests: d.guests,
    unrecognised: d.unknown + d.visitors,
    animals: d.animals,
  }));
}

function ChartTooltip({ active, payload, label }: TooltipContentProps) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload as Row;
  return (
    <div className="rounded-lg border border-border bg-surface-1 px-3 py-2 text-xs shadow-lg">
      <p className="mb-1.5 font-medium text-ink">{formatDayLong(String(label))}</p>
      {[...SERIES].reverse().map((s) => (
        <p key={s.key} className="flex items-center gap-2 text-ink-muted">
          <span className="size-2.5 rounded-sm" style={{ background: s.color }} aria-hidden />
          <span className="flex-1">{s.label}</span>
          <span className="font-medium tabular-nums text-ink">{row[s.key]}</span>
        </p>
      ))}
    </div>
  );
}

export function ActivityChart({ data }: { data: DailyActivity[] }) {
  const [asTable, setAsTable] = useState(false);
  const rows = toRows(data);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted" aria-label="Légende">
          {SERIES.map((s) => (
            <li key={s.key} className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-sm" style={{ background: s.color }} aria-hidden />
              {s.label}
            </li>
          ))}
        </ul>
        <button
          type="button"
          onClick={() => setAsTable((v) => !v)}
          className="text-xs font-medium text-accent hover:underline"
        >
          {asTable ? "Voir le graphique" : "Voir le tableau"}
        </button>
      </div>

      {asTable ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-ink-muted">
                <th className="py-2 pr-4 font-medium">Jour</th>
                {SERIES.map((s) => (
                  <th key={s.key} className="py-2 pr-4 text-right font-medium">
                    {s.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.day} className="border-b border-border last:border-0">
                  <td className="py-2 pr-4 text-ink">{formatDayShort(row.day)}</td>
                  {SERIES.map((s) => (
                    <td key={s.key} className="py-2 pr-4 text-right tabular-nums text-ink">
                      {row[s.key]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="h-64" role="img" aria-label="Passages détectés par jour sur 7 jours">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 4, right: 4, bottom: 0, left: -20 }} barCategoryGap="30%">
              <CartesianGrid vertical={false} stroke="var(--border)" />
              <XAxis
                dataKey="day"
                tickFormatter={formatDayShort}
                tickLine={false}
                axisLine={false}
                tick={{ fill: "var(--ink-muted)", fontSize: 12 }}
              />
              <YAxis
                allowDecimals={false}
                tickLine={false}
                axisLine={false}
                tick={{ fill: "var(--ink-muted)", fontSize: 12 }}
              />
              <Tooltip content={ChartTooltip} cursor={{ fill: "var(--surface-2)" }} />
              {SERIES.map((s, index) => (
                <Bar
                  key={s.key}
                  dataKey={s.key}
                  name={s.label}
                  stackId="activity"
                  fill={s.color}
                  stroke="var(--surface-1)"
                  strokeWidth={2}
                  radius={index === SERIES.length - 1 ? [4, 4, 0, 0] : 0}
                  isAnimationActive={false}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
