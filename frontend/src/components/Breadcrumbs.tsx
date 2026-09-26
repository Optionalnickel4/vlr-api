import Link from "next/link";

export function Breadcrumbs({ kind, label }: { kind: "match" | "team" | "player"; label: string }) {
  const parent = kind === "team" ? { href: "/rankings", label: "Rankings" }
    : kind === "player" ? { href: "/stats", label: "Stats" } : null;
  return (
    <nav aria-label="Breadcrumb" className="mb-6 font-body text-sm text-mut">
      <ol className="flex flex-wrap items-center gap-x-2 gap-y-1 break-words">
        <li><Link href="/" className="inline-flex min-h-11 items-center rounded px-1">Home</Link></li>
        {parent && <li className="flex items-center gap-2"><span aria-hidden="true">/</span><Link href={parent.href} className="inline-flex min-h-11 items-center rounded px-1">{parent.label}</Link></li>}
        <li className="flex min-w-0 items-center gap-2"><span aria-hidden="true">/</span><span aria-current="page" className="min-w-0 break-words">{label}</span></li>
      </ol>
    </nav>
  );
}
