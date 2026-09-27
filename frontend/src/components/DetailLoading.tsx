import { PageContainer } from "./PageContainer";

export function DetailLoading({ kind }: { kind: "match" | "team" | "player" }) {
  return <PageContainer width="home">
    <div role="status" className="rounded border border-line bg-panel p-6 text-ink">
      <h1 className="font-display text-2xl">Loading {kind}…</h1>
      <p className="mt-3 text-mut">Checking the latest available {kind} data. You can keep using the navigation while this loads.</p>
    </div>
  </PageContainer>;
}
