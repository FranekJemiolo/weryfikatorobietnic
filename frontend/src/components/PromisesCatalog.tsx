"use client";

import React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, SearchX, Loader2 } from "lucide-react";
import { PromiseCard } from "@/components/PromiseCard";
import { FilterBar } from "@/components/FilterBar";
import { api, type PromiseListItem } from "@/lib/api";

export interface PromisesCatalogProps {
  initialPromises?: PromiseListItem[];
}

/**
 * Interaktywny katalog obietnic wyborczych zintegrowany z paskiem wyszukiwania FilterBar
 * oraz dynamicznym odpytywaniem endpointu /api/v1/promises/search via React Query.
 */
export function PromisesCatalog({ initialPromises = [] }: PromisesCatalogProps) {
  const searchParams = useSearchParams();

  const q = searchParams?.get("q") || "";
  const party = searchParams?.get("party") || "ALL";
  const status = searchParams?.get("status") || "ALL";
  const category = searchParams?.get("category") || "ALL";

  const isFiltering = Boolean(
    q.trim() ||
      (party && party !== "ALL") ||
      (status && status !== "ALL") ||
      (category && category !== "ALL")
  );

  // Pobieranie przefiltrowanej listy z wyszukiwarki API
  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["promises-search", q, party, status, category],
    queryFn: () =>
      api.searchPromises({
        q: q.trim() || undefined,
        party: party !== "ALL" ? party : undefined,
        status: status !== "ALL" ? status : undefined,
        category: category !== "ALL" ? category : undefined,
        limit: 50,
      }),
    enabled: isFiltering,
    staleTime: 30 * 1000,
  });

  const displayPromises: PromiseListItem[] = isFiltering
    ? data?.items || []
    : initialPromises;

  const totalCount = isFiltering ? data?.total ?? displayPromises.length : initialPromises.length;

  return (
    <section className="space-y-6">
      {/* Pasek wyszukiwania i filtrów ze stanem URL */}
      <FilterBar />

      {/* Nagłówek wyników ze wskaźnikiem liczby znalezionych pozycji */}
      <div className="flex items-center justify-between px-1">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
            {isFiltering ? "Wyniki Wyszukiwania" : "Zarejestrowane Deklaracje Wyborcze"}
          </h2>
          <p className="text-xs sm:text-sm text-slate-400">
            {isFiltering
              ? `Znaleziono ${totalCount} obietnic spełniających kryteria filtrów`
              : `Łącznie zarejestrowanych obietnic w systemie: ${totalCount}`}
          </p>
        </div>

        {isFetching && (
          <div className="flex items-center gap-1.5 text-xs text-indigo-400 animate-pulse">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            <span>Aktualizowanie...</span>
          </div>
        )}
      </div>

      {/* Siatka kart obietnic */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="h-64 rounded-xl border border-slate-800 bg-slate-900/50 animate-pulse p-6 space-y-4"
            >
              <div className="h-4 w-24 bg-slate-800 rounded" />
              <div className="h-6 w-3/4 bg-slate-800 rounded" />
              <div className="h-16 w-full bg-slate-800/60 rounded" />
            </div>
          ))}
        </div>
      ) : displayPromises.length > 0 ? (
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
