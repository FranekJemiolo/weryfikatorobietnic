"use client";

import React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { SearchX } from "lucide-react";
import { PromiseCard } from "@/components/PromiseCard";
import { FilterBar } from "@/components/FilterBar";
import type { PromiseListItem } from "@/lib/api";

export interface PromisesCatalogProps {
  initialPromises?: PromiseListItem[];
}

/**
 * Interaktywny katalog obietnic wyborczych zintegrowany z paskiem wyszukiwania FilterBar.
 */
export function PromisesCatalog({ initialPromises = [] }: PromisesCatalogProps) {
  const searchParams = useSearchParams();

  const [filters, setFilters] = React.useState(() => ({
    q: searchParams?.get("q") || "",
    party: searchParams?.get("party") || "ALL",
    status: searchParams?.get("status") || "ALL",
    category: searchParams?.get("category") || "ALL",
  }));

  const { q, party, status, category } = filters;

  const isFiltering = Boolean(
    q.trim() ||
      (party && party !== "ALL") ||
      (status && status !== "ALL") ||
      (category && category !== "ALL")
  );

  const clientFiltered = React.useMemo(() => {
    return initialPromises.filter((p) => {
      if (q.trim()) {
        const query = q.toLowerCase();
        const matchTitle = p.title.toLowerCase().includes(query);
        const matchCat = p.category.toLowerCase().includes(query);
        const matchParty = p.party.toLowerCase().includes(query);
        if (!matchTitle && !matchCat && !matchParty) return false;
      }
      if (party !== "ALL" && p.party !== party) return false;
      if (status !== "ALL") {
        const match = p.status === status || p.latest_alignment_status === status;
        if (!match) return false;
      }
      if (category !== "ALL" && p.category !== category) return false;
      return true;
    });
  }, [initialPromises, q, party, status, category]);

  const displayPromises: PromiseListItem[] = isFiltering
    ? clientFiltered
    : initialPromises;

  const totalCount = displayPromises.length;

  return (
    <section className="space-y-6">
      {/* Pasek wyszukiwania i filtrów ze stanem URL */}
      <FilterBar onFiltersChange={setFilters} />

      {/* Nagłówek wyników ze wskaźnikiem liczby znalezionych pozycji */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-1">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
              {isFiltering ? "Wyniki Wyszukiwania" : "Katalog Deklaracji Wyborczych"}
            </h2>
            <span className="rounded border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-300">
              Demo • Mock Data po ETL
            </span>
          </div>
          <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
            {isFiltering
              ? `Znaleziono ${totalCount} obietnic spełniających kryteria filtrów (przykładowy zbiór demonstracyjny)`
              : `Zestaw demonstracyjny 12 przykładowych obietnic ilustrujących klasyfikację RAG i statusy po załadowaniu danych przez ETL.`}
          </p>
        </div>
      </div>

      {/* Siatka kart obietnic */}
      {displayPromises.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {displayPromises.map((promise) => (
            <Link
              key={promise.id}
              href={`/promises/${promise.id}`}
              className="block transition-transform hover:-translate-y-1 focus:outline-none focus:ring-2 focus:ring-indigo-500 rounded-xl"
            >
              <PromiseCard promiseId={promise.id} initialData={promise} />
            </Link>
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-12 text-center space-y-3">
          <SearchX className="mx-auto h-8 w-8 text-slate-500" />
          <h3 className="text-base font-semibold text-slate-200">
            Brak wyników spełniających kryteria
          </h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            Nie znaleziono żadnej deklaracji dla podanych filtrów. Spróbuj zmienić frazę
            wyszukiwania lub zresetować filtry komitetu i statusu.
          </p>
        </div>
      )}
    </section>
  );
}

export default PromisesCatalog;
