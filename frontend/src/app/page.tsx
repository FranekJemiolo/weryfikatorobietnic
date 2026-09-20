import React from "react";
import type { Metadata } from "next";
import { Vote, FileCheck2, Sparkles, AlertCircle } from "lucide-react";
import { PromiseCard } from "@/components/PromiseCard";
import type { PromiseListItem } from "@/lib/api";

export const metadata: Metadata = {
  title: "Weryfikator Obietnic: Stan na dziś | Audyt Obywatelski",
  description:
    "Bieżący stan realizacji obietnic wyborczych partii politycznych w X Kadencji Sejmu RP. Weryfikacja projektów ustaw z wykorzystaniem RAG i analiz OSR.",
};

/**
 * Pobiera listę obietnic bezpośrednio z backendu FastAPI po stronie serwera (SSR / ISR).
 */
async function getPromises(): Promise<PromiseListItem[]> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  try {
    const res = await fetch(`${baseUrl}/api/v1/promises`, {
      next: { revalidate: 60 }, // ISR: odświeżanie danych w tle co 60 sekund
    });

    if (!res.ok) {
      console.error(`Nie udało się pobrać obietnic. Kod błędu: ${res.status}`);
      return [];
    }

    return res.json();
  } catch (error) {
    console.error("Błąd połączenia z API podczas renderowania po stronie serwera:", error);
    return [];
  }
}

/**
 * Asynchroniczny React Server Component (RSC) dla strony głównej.
 * Zapewnia natychmiastowe renderowanie HTML, pełne wsparcie SEO oraz optymalny czas First Contentful Paint (FCP).
 */
export default async function HomePage() {
  const promises = await getPromises();

  return (
    <div className="space-y-10 pb-16">
      {/* Sekcja Hero / Nagłówek Główny */}
      <section className="relative overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-900/90 to-indigo-950/40 p-6 sm:p-10 shadow-2xl">
        <div className="relative z-10 max-w-3xl space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-xs font-semibold text-indigo-300">
            <Vote className="h-3.5 w-3.5" />
            <span>X Kadencja Sejmu RP • Audytor AI</span>
          </div>

          <h1 className="text-2xl font-extrabold tracking-tight text-white sm:text-4xl">
            Weryfikator Obietnic:{" "}
            <span className="bg-gradient-to-r from-sky-400 to-indigo-400 bg-clip-text text-transparent">
              Stan na dziś
            </span>
          </h1>

          <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
            Automatyczny audyt legislacyjny zderzający deklaracje wyborcze z rzeczywistymi
            zapisami projektów ustaw procedowanych w polskim parlamencie.
          </p>

          <div className="flex flex-wrap items-center gap-4 pt-2 text-xs text-slate-400">
            <span className="flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
              Wnioskowanie RAG na pgvector
            </span>
            <span>•</span>
            <span className="flex items-center gap-1.5">
              <FileCheck2 className="h-3.5 w-3.5 text-emerald-400" />
              Wycena kosztów OSR w PLN
            </span>
          </div>
        </div>
      </section>

      {/* Katalog Obietnic (CSS Grid: 1 kolumna na mobile, 3 na desktopie) */}
      <section className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-white tracking-tight sm:text-2xl">
              Zarejestrowane Deklaracje Wyborcze
            </h2>
            <p className="text-xs sm:text-sm text-slate-400">
              Łącznie zarejestrowanych obietnic w systemie: {promises.length}
            </p>
          </div>
        </div>

        {promises.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {promises.map((promise) => (
              <PromiseCard
                key={promise.id}
                promiseId={promise.id}
                initialData={promise}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-12 text-center">
            <AlertCircle className="mx-auto h-8 w-8 text-slate-500 mb-3" />
            <h3 className="text-base font-semibold text-slate-200">
              Brak obietnic lub backend oczekuje na połączenie
            </h3>
            <p className="mt-1 text-xs text-slate-400 max-w-md mx-auto">
              Upewnij się, że usługa FastAPI działa na porcie 8000 lub uruchom środowisko lokalne
              za pomocą polecenia <code>docker compose up</code>.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
