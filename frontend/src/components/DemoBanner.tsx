"use client";

import React, { useState } from "react";
import { FlaskConical, Database, ArrowRight, X, Sparkles } from "lucide-react";

export function DemoBanner() {
  const [closed, setClosed] = useState(false);
  const isDemo = process.env.NEXT_PUBLIC_IS_DEMO === "true";

  if (!isDemo || closed) {
    if (!isDemo) return null;
    return (
      <aside aria-label="Wskaźnik trybu demonstracyjnego" className="border-b border-amber-500/30 bg-amber-950/40 px-4 py-1.5 text-center text-xs text-amber-300">
        <span className="font-semibold">⚠️ TRYB DEMO:</span> Prezentowane dane są sztuczne (Mock Data po ETL).{" "}
        <button
          onClick={() => setClosed(false)}
          className="underline hover:text-amber-100 ml-2 font-medium"
        >
          Rozwiń szczegóły
        </button>
      </aside>
    );
  }

  return (
    <aside aria-label="Komunikat trybu demonstracyjnego" className="relative z-50 border-b border-amber-500/40 bg-gradient-to-r from-amber-950/90 via-slate-950 to-amber-950/90 px-4 py-2.5 text-amber-200 shadow-md">
      <div className="container mx-auto flex max-w-7xl flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs sm:text-sm">
        <div className="flex items-start sm:items-center gap-2.5">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-amber-500/20 text-amber-400 border border-amber-500/30">
            <FlaskConical className="h-4 w-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-block rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-300 border border-amber-500/30">
                GitHub Pages Demo
              </span>
              <span className="font-bold text-amber-200">
                Wersja Pokazowa • Sztuczne Dane (Mock Data)
              </span>
            </div>
            <p className="mt-0.5 text-xs text-amber-300/80 leading-snug">
              Ta strona jest <strong>interaktywnym demo</strong>. Wszystkie obietnice, wskaźniki i projekty ustaw to <strong>dane syntetyczne</strong>, które pokazują docelowy wygląd i funkcjonalność aplikacji <strong>po załadowaniu danych z potoku ETL</strong> (Apache Airflow + Sejm OpenAPI / RCL + RAG pgvector).
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0 self-end sm:self-center">
          <a
            href="#architektura"
            className="inline-flex items-center gap-1 text-xs font-semibold text-amber-300 hover:text-amber-100 transition-colors"
          >
            <Database className="h-3.5 w-3.5" />
            <span>Jak działa ETL?</span>
            <ArrowRight className="h-3 w-3" />
          </a>
          <button
            onClick={() => setClosed(true)}
            aria-label="Zwiń baner demo"
            className="rounded p-1 text-amber-400 hover:bg-amber-500/20 hover:text-amber-200 transition"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
