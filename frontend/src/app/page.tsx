"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Vote,
  FileCheck2,
  TrendingUp,
  Search,
  Filter,
  Users,
  Building2,
} from "lucide-react";
import { api, type PromiseListItem } from "@/lib/api";
import { PromiseCard, PromiseCardSkeleton } from "@/components/PromiseCard";
import { MPActivityHeatmap } from "@/components/MPActivityHeatmap";

export default function HomePage() {
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedMpId, setSelectedMpId] = useState<string>("1");

  const { data: promises, isLoading, error } = useQuery<PromiseListItem[]>({
    queryKey: ["promises-list"],
    queryFn: () => api.getPromises(),
  });

  const categories = [
    "ALL",
    ...Array.from(new Set(promises?.map((p) => p.category) || [])),
  ];

  const filteredPromises = promises?.filter((p) => {
    const matchesCategory =
      selectedCategory === "ALL" || p.category === selectedCategory;
    const matchesSearch =
      p.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.party.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.id.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  return (
    <div className="space-y-10 pb-16">
      {/* Hero Banner */}
      <section className="relative overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-900/90 to-indigo-950/40 p-6 sm:p-10 shadow-2xl">
        <div className="relative z-10 max-w-3xl space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-xs font-semibold text-indigo-300">
            <Vote className="h-3.5 w-3.5" />
            <span>X Kadencja Sejmu RP • Audytor AI (RAG + pgvector)</span>
          </div>
          <h2 className="text-2xl font-extrabold tracking-tight text-white sm:text-4xl">
            Rozliczamy polityków na podstawie{" "}
            <span className="bg-gradient-to-r from-sky-400 to-indigo-400 bg-clip-text text-transparent">
              twardych faktów prawnych
            </span>
          </h2>
          <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
            Nasz system automatycznie analizuje projekty ustaw trafiające do Sejmu,
            porównuje je semantycznie z obietnicami partii i wylicza rzeczywistą zgodność
            oraz szacowane koszty w budżecie państwa (OSR).
          </p>
        </div>
      </section>

      {/* Widok Aktywności Poselskiej (Heatmapa) */}
      <section className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h3 className="flex items-center gap-2 text-lg font-bold text-white sm:text-xl">
              <Users className="h-5 w-5 text-sky-400" />
              <span>Dyscyplina i Frekwencja Poselska</span>
            </h3>
            <p className="text-xs sm:text-sm text-slate-400">
              Analiza indywidualnych głosowań z oficjalnego API Sejmu pod kątem lojalności klubowej.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Wybierz posła:</span>
            <select
              value={selectedMpId}
              onChange={(e) => setSelectedMpId(e.target.value)}
              className="rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs font-medium text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="1">Poseł Donald Tusk (KO)</option>
              <option value="42">Poseł Władysław Kosiniak-Kamysz (PSL)</option>
              <option value="120">Poseł Szymon Hołownia (PL2050)</option>
              <option value="205">Poseł Krzysztof Bosak (Konfederacja)</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto rounded-xl border border-slate-800/80 bg-slate-900/60 p-4 sm:p-6 shadow-md backdrop-blur-sm">
          <MPActivityHeatmap
            mpId={selectedMpId}
            mpName={
              selectedMpId === "1"
                ? "Donald Tusk"
                : selectedMpId === "42"
                ? "Władysław Kosiniak-Kamysz"
                : "Poseł na Sejm RP"
            }
            clubName={selectedMpId === "1" ? "Koalicja Obywatelska" : "Klub Parlamentarny"}
          />
        </div>
      </section>

      {/* Sekcja Obietnic Wyborczych */}
      <section className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h3 className="flex items-center gap-2 text-lg font-bold text-white sm:text-xl">
              <FileCheck2 className="h-5 w-5 text-indigo-400" />
              <span>Katalog Obietnic i Ewaluacji Ustaw</span>
            </h3>
            <p className="text-xs sm:text-sm text-slate-400">
              Weryfikacja deklaracji partii rządzących i opozycyjnych.
            </p>
          </div>

          {/* Wyszukiwarka i filtry */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative flex-1 sm:w-64">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
              <input
                type="text"
                placeholder="Szukaj obietnicy, partii..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-lg border border-slate-800 bg-slate-900 py-2 pl-9 pr-4 text-xs sm:text-sm text-slate-100 placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
          </div>
        </div>

        {/* Filtry kategorii */}
        <div className="flex flex-wrap items-center gap-2 overflow-x-auto pb-2">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
                selectedCategory === cat
                  ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                  : "bg-slate-900 border border-slate-800 text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              }`}
            >
              {cat === "ALL" ? "Wszystkie kategorie" : cat}
            </button>
          ))}
        </div>

        {/* Lista kart obietnic */}
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <PromiseCardSkeleton />
            <PromiseCardSkeleton />
            <PromiseCardSkeleton />
          </div>
        ) : error ? (
          <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 p-6 text-center">
            <p className="text-sm text-rose-300">
              Nie udało się połączyć z backendem FastAPI ({error.message}). Upewnij się, że serwer działa na porcie 8000.
            </p>
          </div>
        ) : filteredPromises && filteredPromises.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredPromises.map((promise) => (
              <PromiseCard
                key={promise.id}
                promiseId={promise.id}
                initialData={promise}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-12 text-center text-slate-400">
            Brak obietnic spełniających wybrane kryteria wyszukiwania.
          </div>
        )}
      </section>
    </div>
  );
}
