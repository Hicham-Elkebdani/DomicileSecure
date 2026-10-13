import { AlertOctagon, AlertTriangle, Info, ShieldAlert, ShieldCheck } from "lucide-react";

import { cn } from "@/components/ui/cn";
import type { Severity } from "@/lib/api/types";
import { SEVERITY_LABEL } from "@/lib/format";

/** Status colour + icon + label: severity is never conveyed by colour alone. */
const STYLE: Record<Severity, { icon: typeof Info; dot: string }> = {
  critical: { icon: AlertOctagon, dot: "text-critical" },
  high: { icon: ShieldAlert, dot: "text-critical" },
  medium: { icon: AlertTriangle, dot: "text-serious" },
  low: { icon: Info, dot: "text-warning" },
  info: { icon: ShieldCheck, dot: "text-ink-faint" },
};

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  const { icon: Icon, dot } = STYLE[severity];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-border bg-surface-2 px-2 py-0.5 text-xs font-medium text-ink",
        className,
      )}
    >
      <Icon className={cn("size-3.5", dot)} aria-hidden />
      {SEVERITY_LABEL[severity]}
    </span>
  );
}
