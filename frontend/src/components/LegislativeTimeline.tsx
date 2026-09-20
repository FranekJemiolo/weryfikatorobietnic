"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, Clock, Calendar, AlertCircle, RefreshCw, GitCommit } from "lucide-react";
import { api, type TimelineEvent } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

export interface LegislativeTimelineProps {
  promiseId: string;
  initialData?: TimelineEvent[];
}

/**
 * Szkielet animacyjny (Skeleton) dla wertykalnej osi czasu.
 */
export function LegislativeTimelineSkeleton() {
  return (
    <div className="relative py-8" role="status" aria-label="Ładowanie osi czasu">
      {/* Linia pionowa */}
      <div className="absolute top-6 bottom-6 left-6 sm:left-1/2 -translate-x-1/2 w-0.5 bg-slate-800 animate-pulse" />

      <div className="space-y-10 sm:space-y-12">
        {[1, 2, 3, 4, 5].map((idx) => {
          const isEven = idx % 2 === 0;
          return (
            <div
              key={idx}
              className={`relative flex items-center ${
                isEven ? "sm:flex-row-reverse" : "sm:flex-row"
              }`}
            >
              {/* Węzeł skeleton */}
              <div className="absolute left-6 sm:left-1/2 -translate-x-1/2 flex h-9 w-9 items-center justify-center rounded-full border-2 border-slate-700 bg-slate-900 shadow-md">
                <div className="h-3.5 w-3.5 rounded-full bg-slate-700 animate-pulse" />
              </div>

              {/* Treść karty skeleton */}
              <div
                className={`ml-14 sm:ml-0 w-full sm:w-1/2 ${
                  isEven ? "sm:pl-10 text-left" : "sm:pr-10 sm:text-right"
                }`}
              >
                <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-4 shadow-lg space-y-2.5">
                  <div
                    className={`h-4 w-24 bg-slate-800 rounded animate-pulse ${
                      !isEven ? "sm:ml-auto" : ""
                    }`}
                  />
                  <div
                    className={`h-5 w-48 bg-slate-700/60 rounded animate-pulse ${
                      !isEven ? "sm:ml-auto" : ""
                    }`}
                  />
                  <div
                    className={`h-4 w-full bg-slate-800/70 rounded animate-pulse ${
                      !isEven ? "sm:ml-auto" : ""
                    }`}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Formatuje ciąg daty ISO na czytelny polski format (np. "15 maja 2024").
 */
function formatPolishDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return new Intl.DateTimeFormat("pl-PL", {
      day: "numeric",
      month: "long",
      year: "numeric",
    }).format(d);
  } catch {
    return dateStr;
  }
}

/**
 * Komponent wertykalnej osi czasu procesu legislacyjnego (Time-to-Delivery).
 * Na urządzeniach mobilnych oś przylega do lewej krawędzi, na desktopach jest elegancko wyśrodkowana.
 */
export function LegislativeTimeline({ promiseId, initialData }: LegislativeTimelineProps) {
  const {
    data: events,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["promise-timeline", promiseId],
    queryFn: () => api.getPromiseTimeline(promiseId),
    initialData,
    staleTime: 60 * 1000,
  });

  if (isLoading && !events) {
    return <LegislativeTimelineSkeleton />;
  }

  if (isError) {
    return (
      <div className="rounded-xl border border-red-900/50 bg-red-950/20 p-6 text-center space-y-3">
        <AlertCircle className="mx-auto h-8 w-8 text-red-400" />
        <p className="text-sm font-medium text-red-200">
          Nie udało się pobrać etapów osi czasu dla tej obietnicy.
        </p>
        <p className="text-xs text-red-400">
          {error instanceof Error ? error.message : "Błąd sieci lub serwera"}
        </p>
        <button
          onClick={() => refetch()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-red-800 bg-red-900/40 px-3 py-1.5 text-xs font-semibold text-red-200 hover:bg-red-800/60 transition"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Spróbuj ponownie
        </button>
      </div>
    );
  }

  if (!events || events.length === 0) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-8 text-center space-y-2">
        <GitCommit className="mx-auto h-8 w-8 text-slate-500" />
        <p className="text-sm text-slate-300 font-medium">
          Brak zarejestrowanych etapów legislacyjnych
        </p>
        <p className="text-xs text-slate-500 max-w-sm mx-auto">
          Dla tej obietnicy nie zainicjowano jeszcze formalnego druku w Sejmie ani nie powiązano projektu ustawy.
        </p>
      </div>
    );
  }

  const completedCount = events.filter((e) => e.is_completed).length;
  const progressPercent = Math.round((completedCount / events.length) * 100);

  return (
    <div className="space-y-6">
      {/* Pasek podsumowujący postęp procedury */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-900/50 px-4 py-3 text-xs sm:text-sm">
        <div className="flex items-center gap-2 text-slate-300 font-medium">
          <Clock className="h-4 w-4 text-sky-400" />
          <span>Postęp legislacyjny:</span>
          <span className="font-bold text-white">
            {completedCount} z {events.length} etapów ({progressPercent}%)
          </span>
        </div>
        <Badge
          variant={progressPercent === 100 ? "default" : "secondary"}
          className={
            progressPercent === 100
              ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
              : "bg-sky-500/10 text-sky-300 border-sky-500/20"
          }
        >
          {progressPercent === 100 ? "Proces Zakończony" : "Procedowanie w toku"}
        </Badge>
      </div>

      {/* Kontener pionowej osi czasu */}
      <div className="relative py-4">
        {/* Pionowa linia osi czasu: lewa strona na mobile, środek na desktopie */}
        <div
          className="absolute top-4 bottom-4 left-6 sm:left-1/2 -translate-x-1/2 w-0.5 bg-gradient-to-b from-emerald-500 via-sky-600/70 to-slate-800"
          aria-hidden="true"
        />

        <div className="space-y-8 sm:space-y-10">
          {events.map((event, index) => {
            const isCompleted = event.is_completed;
            const isEven = index % 2 === 0;

            return (
              <div
                key={`${event.stage_name}-${index}`}
                className={`relative flex items-start sm:items-center ${
                  isEven ? "sm:flex-row-reverse" : "sm:flex-row"
                } group`}
              >
                {/* Okrągły węzeł (kropka) osi czasu */}
                <div
                  className={`absolute left-6 sm:left-1/2 -translate-x-1/2 z-10 flex h-9 w-9 items-center justify-center rounded-full border-2 transition-all duration-300 ${
                    isCompleted
                      ? "border-emerald-400 bg-emerald-950 text-emerald-300 shadow-[0_0_12px_rgba(52,211,153,0.4)] group-hover:scale-110"
                      : "border-slate-700 bg-slate-900 text-slate-500 group-hover:border-slate-600"
                  }`}
                  title={isCompleted ? "Etap zrealizowany" : "Etap oczekujący / w toku"}
                >
                  {isCompleted ? (
                    <Check className="h-4 w-4 stroke-[3]" />
                  ) : (
                    <Clock className="h-3.5 w-3.5" />
                  )}
                </div>

                {/* Karta z zawartością etapu */}
                <div
                  className={`ml-14 sm:ml-0 w-full sm:w-1/2 ${
                    isEven
                      ? "sm:pl-10 sm:text-left"
                      : "sm:pr-10 sm:text-right"
                  }`}
                >
                  <div
                    className={`rounded-xl border p-4 sm:p-5 transition-all duration-200 ${
                      isCompleted
                        ? "border-slate-800/90 bg-slate-900/80 shadow-md hover:border-slate-700"
                        : "border-slate-800/50 bg-slate-950/40 opacity-75 hover:opacity-100 hover:border-slate-800"
                    }`}
                  >
                    {/* Data i status etapu */}
                    <div
                      className={`flex flex-wrap items-center gap-2 mb-1.5 ${
                        isEven ? "sm:justify-start" : "sm:justify-end"
                      }`}
                    >
                      <span className="inline-flex items-center gap-1 text-xs text-slate-400 font-mono">
                        <Calendar className="h-3 w-3 text-slate-500" />
                        <time dateTime={event.date}>{formatPolishDate(event.date)}</time>
                      </span>

                      <Badge
                        variant="outline"
                        className={`text-[10px] px-2 py-0.5 ${
                          isCompleted
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                            : "bg-slate-800 text-slate-400 border-slate-700"
                        }`}
                      >
                        {isCompleted ? "Zrealizowany" : "Oczekujący"}
                      </Badge>
                    </div>

                    {/* Nazwa etapu */}
                    <h3
                      className={`text-sm sm:text-base font-semibold tracking-tight ${
                        isCompleted ? "text-white" : "text-slate-400"
                      }`}
                    >
                      {event.stage_name}
                    </h3>

                    {/* Szczegółowy opis etapu */}
                    <p className="mt-1 text-xs sm:text-sm text-slate-300 leading-relaxed">
                      {event.description}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default LegislativeTimeline;
