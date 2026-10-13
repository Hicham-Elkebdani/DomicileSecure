import type { LucideIcon } from "lucide-react";
import Link from "next/link";

import { Card } from "@/components/ui/card";

export function StatTile({
  label,
  value,
  hint,
  icon: Icon,
  href,
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon: LucideIcon;
  href?: string;
}) {
  const content = (
    <Card className="h-full p-5 transition hover:border-ink-faint">
      <div className="flex items-center justify-between text-ink-muted">
        <span className="text-sm">{label}</span>
        <Icon className="size-4" aria-hidden />
      </div>
      <p className="mt-2 text-3xl font-semibold tracking-tight tabular-nums text-ink">{value}</p>
      {hint && <p className="mt-1 text-xs text-ink-muted">{hint}</p>}
    </Card>
  );
  return href ? <Link href={href}>{content}</Link> : content;
}
