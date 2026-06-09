import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface TableColumn {
  /** Column heading text (rendered uppercase). Empty string for an unlabeled
   *  column (e.g. an agent icon). */
  label: string;
  /** Numeric/stat columns sit right; identity columns sit left (default). */
  align?: "left" | "right";
  className?: string;
}

/**
 * TableShell — the broadcast stat table: uppercase, wide-tracked dim column
 * heads over a hairline rule; tight rows with mono, right-aligned numerics and
 * a faint hover lift. The frame + header come from `columns`; the body is the
 * caller's <tr>/<td> rows. Base cell padding + row separators are applied here
 * via child selectors so callers only add `text-right font-mono` on stat cells.
 */
export function TableShell({
  columns,
  children,
  className,
}: {
  columns: TableColumn[];
  children: ReactNode;
  className?: string;
}) {
  return (
    <table
      className={cn(
        "w-full border-collapse text-left",
        // base body-cell rhythm + row separators + hover, applied once here
        "[&_tbody_td]:border-t [&_tbody_td]:border-line/60 [&_tbody_td]:px-3 [&_tbody_td]:py-2",
        "[&_tbody_tr:hover]:bg-ink/[0.03]",
        className,
      )}
    >
      <thead>
        <tr>
          {columns.map((col, i) => (
            <th
              key={`${col.label}-${i}`}
              scope="col"
              className={cn(
                "px-3 pb-2 font-display text-[11px] font-semibold uppercase tracking-[0.1em] text-dim",
                col.align === "right" ? "text-right" : "text-left",
                col.className,
              )}
            >
              {col.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>{children}</tbody>
    </table>
  );
}
