import React, { Suspense } from "react";
import type { Metadata } from "next";
import { GovernmentScoreDashboard } from "@/components/GovernmentScoreDashboard";
import { PromisesCatalog } from "@/components/PromisesCatalog";
import {
  HeroSection,
  ArchitectureBento,
  ContributeSection,
} from "@/components/landing";
import type { PromiseListItem } from "@/lib/api";

export const metadata: Metadata = {
  title: "Weryfikator Obietnic | Obywatelski Audyt AI Prawa RP",
  description:
    "Automatyczna weryfikacja obietnic wyborczych partii politycznych z projektami ustaw w Sejmie RP X Kadencji. System AI RAG + pgvector, Apache Airflow, FastAPI. Open Source · MIT.",
  keywords: [
    "obietnice wyborcze",
    "Sejm RP",
    "AI audyt",
    "transparentność",
    "civic tech",
    "open source",
  ],
  openGraph: {
    title: "Weryfikator Obietnic | Obywatelski Audyt AI Prawa RP",
    description:
      "Sprawdź, czy politycy dotrzymują obietnic. System AI weryfikuje deklaracje wyborcze z rzeczywistymi aktami prawnymi.",
    type: "website",
    locale: "pl_PL",
  },
};

import { SHOWCASE_PROMISES, SHOWCASE_ANALYTICS } from "@/lib/showcaseData";

/**
 * Pobiera listę obietnic bezpośrednio z backendu FastAPI po stronie serwera (SSR / ISR).
 * Podczas statycznego eksportu (GitHub Pages) lub niedostępności API zwraca
 * pełną Złotą Bazę Pokazową (12 realnych obietnic Sejmu RP X Kadencji).
 */
async function getPromises(): Promise<PromiseListItem[]> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!baseUrl || process.env.NEXT_EXPORT === "true") {
    return SHOWCASE_PROMISES;
  }

  try {
    const res = await fetch(`${baseUrl}/api/v1/promises`, {
      next: { revalidate: 60 }, // ISR: odświeżanie danych w tle co 60 sekund
    });

    if (!res.ok) {
      return SHOWCASE_PROMISES;
    }

    const data = await res.json();
    return Array.isArray(data) && data.length > 0 ? data : SHOWCASE_PROMISES;
  } catch {
    return SHOWCASE_PROMISES;
  }
}

/**
 * Strona główna — Landing Page + Dashboard Obywatelski
 *
 * Struktura:
 *   1. HeroSection      – hero animowany framer-motion + statystyki
 *   2. GovernmentScore  – panel analityczny efektywności rządu (#dashboard)
 *   3. PromisesCatalog  – wyszukiwarka + katalog obietnic (#katalog)
 *   4. ArchitectureBento– bento-grid z architekturą systemu (#architektura)
 *   5. ContributeSection– sekcja open-source / jak dołączyć (#contribute)
 */
export default async function HomePage() {
  const promises = await getPromises();

  return (
    <div className="space-y-0">
      {/* 1. Hero */}
      <HeroSection />

      {/* Divider */}
      <div className="h-px w-full bg-gradient-to-r from-transparent via-slate-700/50 to-transparent" />

      {/* 2. Government Score Dashboard */}
      <section id="dashboard" className="py-12 scroll-mt-20">
        <GovernmentScoreDashboard initialData={SHOWCASE_ANALYTICS} />
      </section>

      {/* Divider */}
      <div className="h-px w-full bg-gradient-to-r from-transparent via-slate-700/50 to-transparent" />

      {/* 3. Katalog Obietnic */}
      <section id="katalog" className="py-12 scroll-mt-20">
        <Suspense
          fallback={
            <div className="h-96 rounded-xl border border-slate-800 bg-slate-900/40 animate-pulse" />
          }
        >
          <PromisesCatalog initialPromises={promises} />
        </Suspense>
      </section>

      {/* Divider */}
      <div className="h-px w-full bg-gradient-to-r from-transparent via-slate-700/50 to-transparent" />

      {/* 4. Architecture Bento Grid */}
      <section id="architektura" className="scroll-mt-20">
        <ArchitectureBento />
      </section>

      {/* Divider */}
      <div className="h-px w-full bg-gradient-to-r from-transparent via-slate-700/50 to-transparent" />

      {/* 5. Contribute / Open Source */}
      <section id="contribute" className="scroll-mt-20">
        <ContributeSection />
      </section>

      {/* Footer */}
      <footer className="py-12 text-center">
        <p className="text-xs text-slate-500">
          Weryfikator Obietnic © 2025 · Licencja MIT ·{" "}
          <a
            href="https://github.com/FranekJemiolo/weryfikatorobietnic"
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-400 hover:text-white transition-colors"
          >
            GitHub
          </a>{" "}
          · Dane z API Sejmu RP, ISAP, RCL
        </p>
        <p className="mt-2 text-[10px] text-slate-600">
          System nie zastępuje oficjalnych źródeł prawa. Werdykty AI są wskazówką
          analityczną, nie interpretacją prawną.
        </p>
      </footer>
    </div>
  );
}
