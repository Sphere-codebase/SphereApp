import { cn } from "@/lib/utils";

import type { ReactNode } from "react";

export type DataTableColumn<T> = {
  key: string;
  header: string;
  cell: (row: T) => ReactNode;
  headerClassName?: string;
  cellClassName?: string;
};

type DataTableProps<T> = {
  columns: Array<DataTableColumn<T>>;
  rows: T[];
  emptyMessage?: string;
  getRowId?: (row: T, index: number) => string;
};

export default function DataTable<T>({
  columns,
  rows,
  emptyMessage = "No data yet.",
  getRowId,
}: DataTableProps<T>) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
            {columns.map((column) => (
              <th
                key={column.key}
                className={cn("py-2", column.headerClassName)}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td
                className="py-4 text-sm text-slate-500"
                colSpan={columns.length}
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row, index) => {
              const key = getRowId ? getRowId(row, index) : String(index);
              return (
              <tr
                key={key}
                className="border-t border-slate-100 dark:border-slate-800"
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={cn("py-3 align-top", column.cellClassName)}
                  >
                    {column.cell(row)}
                  </td>
                ))}
              </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
