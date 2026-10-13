import { Button } from "@/components/ui/button";

export function Pagination({
  total,
  limit,
  offset,
  onChange,
}: {
  total: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
}) {
  if (total <= limit) return null;
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.ceil(total / limit);
  return (
    <div className="flex items-center justify-between border-t border-border px-5 py-3 text-sm text-ink-muted">
      <span>
        Page {page} / {pages} · {total} résultats
      </span>
      <div className="flex gap-2">
        <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => onChange(offset - limit)}>
          Précédent
        </Button>
        <Button size="sm" variant="secondary" disabled={page >= pages} onClick={() => onChange(offset + limit)}>
          Suivant
        </Button>
      </div>
    </div>
  );
}
