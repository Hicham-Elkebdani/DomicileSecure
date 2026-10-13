import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-3 px-4 text-center">
      <p className="text-sm font-medium text-ink-muted">Erreur 404</p>
      <h1 className="text-2xl font-semibold text-ink">Page introuvable</h1>
      <Link href="/" className="text-sm font-medium text-accent hover:underline">
        Retour au tableau de bord
      </Link>
    </main>
  );
}
