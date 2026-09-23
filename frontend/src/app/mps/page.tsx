"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";
import {
  User,
  Search,
  SearchX,
  FileText,
  CheckCircle2,
  ArrowRight,
  Shield,
  FlaskConical,
  Users,
} from "lucide-react";
import { SHOWCASE_MPS_LIST } from "@/lib/showcaseData";
import { SubscribeButton } from "@/components/SubscribeButton";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/card";

const CLUBS = [
  { id: "ALL", label: "Wszystkie kluby" },
  { id: "Koalicja Obywatelska", label: "Koalicja Obywatelska" },
  { id: "Prawo i Sprawiedliwość", label: "Prawo i Sprawiedliwość" },
  { id: "Trzecia Droga", label: "Trzecia Droga" },
  { id: "Nowa Lewica", label: "Lewica" },
  { id: "Konfederacja", label: "Konfederacja" },
  { id: "Razem", label: "Razem" },
];

export default function MPsDirectoryPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedClub, setSelectedClub] = useState("ALL");

  const filteredMPs = useMemo(() => {
    return SHOWCASE_MPS_LIST.filter((mp) => {
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const fullName = `${mp.first_name} ${mp.last_name}`.toLowerCase();
        const matchName = fullName.includes(q);
        const matchClub = mp.club.toLowerCase().includes(q);
        if (!matchName && !matchClub) return false;
      }

      if (selectedClub !== "ALL") {
        if (!mp.club.toLowerCase().includes(selectedClub.toLowerCase())) {
          return false;
        }
      }

      return true;
    });
  }, [searchQuery, selectedClub]);

  return (
    <div className="space-y-8 pb-16">
      {/* Nagłówek sekcji Sprawdź Posła */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-xs font-semibold text-indigo-300">
            <Users className="h-3.5 w-3.5" />
            Sejm RP X Kadencja • Baza Parlamentarzystów
          </span>
          <span className="rounded border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-300">
            Demo • Mock Data po ETL
          </span>
        </div>

        <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
          Sprawdź Posła — Obywatelski Rejestr Aktywności
        </h1>
        <p className="max-w-3xl text-sm sm:text-base text-slate-400">
          Wyszukaj parlamentarzystę, zweryfikuj jego obecność na posiedzeniach, lojalność wobec programu
          wyborczego oraz historię składanych interpelacji poselskich.
        </p>
      </div>

      {/* Panel filtrów i wyszukiwania */}
      <div className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 sm:p-6 backdrop-blur-md shadow-xl">
        <div className="relative">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Szukaj posła po imieniu, nazwisku lub klubie..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-xl border border-slate-700/80 bg-slate-950/80 pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 transition"
          />
        </div>

        {/* Filtr klubów */}
        <div className="flex flex-wrap gap-2">
          {CLUBS.map((club) => {
            const active = selectedClub === club.id;
            return (
              <button
                key={club.id}
                onClick={() => setSelectedClub(club.id)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                  active
                    ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/30"
                    : "border border-slate-800 bg-slate-800/40 text-slate-300 hover:bg-slate-800 hover:text-white"
                }`}
              >
                {club.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Licznik wyników */}
      <div className="flex items-center justify-between px-1 text-xs text-slate-400">
        <span>Znaleziono posłów: {filteredMPs.length}</span>
        {searchQuery && (
          <button
            onClick={() => setSearchQuery("")}
            className="text-indigo-400 hover:text-indigo-300 underline"
          >
            Wyczyść wyszukiwanie
          </button>
        )}
      </div>

      {/* Siatka kart posłów */}
      {filteredMPs.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredMPs.map((mp) => {
            const initials = `${mp.first_name[0]}${mp.last_name[0]}`;
            return (
              <Card
                key={mp.id}
                className="group relative overflow-hidden border-slate-800/80 bg-slate-900/70 shadow-lg backdrop-blur-sm transition-all duration-200 hover:border-slate-700 hover:shadow-indigo-500/10 hover:shadow-xl"
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 to-sky-500 font-bold text-white shadow-md shadow-indigo-500/20 group-hover:scale-105 transition-transform">
                        {initials}
                      </div>
                      <div>
                        <CardTitle className="text-base sm:text-lg text-white group-hover:text-indigo-300 transition-colors">
                          {mp.first_name} {mp.last_name}
                        </CardTitle>
                        <p className="text-xs text-slate-400 mt-0.5 line-clamp-1">{mp.club}</p>
                      </div>
                    </div>
                    <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[9px] font-bold text-amber-300/80 border border-amber-500/20">
                      Mock ETL
                    </span>
                  </div>
                </CardHeader>

                <CardContent className="space-y-3 pb-3 text-xs">
                  <div className="flex items-center justify-between rounded-lg border border-slate-800/80 bg-slate-950/40 p-2.5">
                    <span className="text-slate-400">Mandat poselski</span>
                    <span className="inline-flex items-center gap-1 font-medium text-emerald-400">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Aktywny poseł
                    </span>
                  </div>

                  <div className="flex items-center justify-between rounded-lg border border-slate-800/80 bg-slate-950/40 p-2.5">
                    <span className="text-slate-400">Złożone interpelacje</span>
                    <span className="inline-flex items-center gap-1 font-semibold text-slate-200">
                      <FileText className="h-3.5 w-3.5 text-indigo-400" />
                      {mp.interpellations_count || 0}
                    </span>
                  </div>
                </CardContent>

                <CardFooter className="pt-2 flex items-center justify-between gap-2 border-t border-slate-800/60">
                  <SubscribeButton
                    targetType="MP"
                    targetId={String(mp.id)}
                    label="Śledź posła"
                    size="sm"
                  />
                  <Link
                    href={`/mps/${mp.id}`}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-400 hover:text-indigo-300 group-hover:translate-x-0.5 transition"
                  >
                    <span>Profil i frekwencja</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </CardFooter>
              </Card>
            );
          })}
        </div>
      ) : (
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-12 text-center space-y-3">
          <SearchX className="mx-auto h-8 w-8 text-slate-500" />
          <h3 className="text-base font-semibold text-slate-200">
            Nie znaleziono parlamentarzysty
          </h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            Brak posłów spełniających podane kryteria. Spróbuj zmienić filtr klubu lub wprowadzić
            inną frazę w wyszukiwarce.
          </p>
        </div>
      )}
    </div>
  );
}
