import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/**
 * Kontrakt pojedynczego dnia aktywności posła zwracany przez FastAPI:
 * GET /api/v1/mps/{mp_id}/daily-activity
 */
export interface DailyActivity {
  date: string; // YYYY-MM-DD
  total_votes: number;
  attendance_rate: number; // 0.0 - 1.0
  rebellion_rate: number; // 0.0 - 1.0 (% głosowań wbrew większości klubu)
  dominant_status: "LOYAL" | "REBELLIOUS" | "ABSENT" | "MIXED" | "NO_VOTES";
}

export interface MPActivityHeatmapProps {
  mpId: string;
  mpName?: string;
  clubName?: string;
  apiBaseUrl?: string;
  useMock?: boolean;
  className?: string;
}

/**
 * Konfiguracja kolorów Tailwind CSS i etykiet dla poszczególnych statusów
 */
const STATUS_STYLES: Record<
  DailyActivity["dominant_status"],
  {
    bgClass: string;
    label: string;
    description: string;
  }
> = {
  LOYAL: {
    bgClass: "bg-emerald-500 hover:bg-emerald-600 dark:bg-emerald-500 dark:hover:bg-emerald-400",
    label: "Lojalny",
    description: "Głosowanie w pełnej zgodności z większością klubu",
  },
  REBELLIOUS: {
    bgClass: "bg-rose-500 hover:bg-rose-600 dark:bg-rose-500 dark:hover:bg-rose-400",
    label: "Bunt",
    description: "Głosowanie wbrew dyscyplinie lub linii klubu",
  },
  MIXED: {
    bgClass: "bg-yellow-400 hover:bg-yellow-500 dark:bg-yellow-400 dark:hover:bg-yellow-300",
    label: "Mieszany",
    description: "Wstrzymanie się od głosu lub zróżnicowane decyzje",
  },
  ABSENT: {
    bgClass: "bg-slate-800 hover:bg-slate-900 dark:bg-slate-700 dark:hover:bg-slate-600",
    label: "Nieobecny",
    description: "Nieobecność na większości zarządzonych głosowań",
  },
  NO_VOTES: {
    bgClass:
      "bg-slate-100 border border-slate-200 hover:bg-slate-200 dark:bg-slate-800/40 dark:border-slate-800 dark:hover:bg-slate-800",
    label: "Brak posiedzeń",
    description: "Dzień wolny od obrad plenarnych Sejmu",
  },
};

/**
 * Generator zamockowanych danych z ostatnich 30 dni posiedzeń
 * Umożliwia natychmiastowe testowanie wizualizacji bez aktywnego backendu.
 */
export const fetchMockDailyActivity = async (mpId: string): Promise<DailyActivity[]> => {
  // Symulacja opóźnienia sieciowego (300ms)
  await new Promise((resolve) => setTimeout(resolve, 300));

  const days: DailyActivity[] = [];
  const today = new Date();

  for (let i = 29; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const dateStr = d.toISOString().split("T")[0];
    const dayOfWeek = d.getDay(); // 0 = niedziela, 6 = sobota

    // Sejm obraduje najczęściej we wtorki, środy, czwartki i wybrane piątki
    const isSittingDay = dayOfWeek >= 2 && dayOfWeek <= 5 && i % 3 !== 0;

    if (!isSittingDay) {
      days.push({
        date: dateStr,
        total_votes: 0,
        attendance_rate: 0,
        rebellion_rate: 0,
        dominant_status: "NO_VOTES",
      });
      continue;
    }

    // Liczba głosowań w dniu posiedzenia (od 12 do 48)
    const votesCount = 12 + Math.floor(Math.random() * 36);
    const rand = Math.random();

    if (rand < 0.7) {
      // LOYAL: wysoka frekwencja, znikomy bunt
      days.push({
        date: dateStr,
        total_votes: votesCount,
        attendance_rate: 0.95 + Math.random() * 0.05,
        rebellion_rate: Math.random() * 0.03,
        dominant_status: "LOYAL",
      });
    } else if (rand < 0.85) {
      // MIXED: obecny, ale wahał się / wstrzymywał
      days.push({
        date: dateStr,
        total_votes: votesCount,
        attendance_rate: 0.85 + Math.random() * 0.1,
        rebellion_rate: 0.1 + Math.random() * 0.15,
        dominant_status: "MIXED",
      });
    } else if (rand < 0.93) {
      // REBELLIOUS: głosował przeciw klubowi
      days.push({
        date: dateStr,
        total_votes: votesCount,
        attendance_rate: 0.9 + Math.random() * 0.1,
        rebellion_rate: 0.35 + Math.random() * 0.4,
        dominant_status: "REBELLIOUS",
      });
    } else {
      // ABSENT: opuszczone głosowania
      days.push({
        date: dateStr,
        total_votes: votesCount,
        attendance_rate: Math.random() * 0.3,
        rebellion_rate: 0,
        dominant_status: "ABSENT",
      });
    }
  }

  return days;
};

/**
 * Rzeczywista funkcja pobierająca dane z FastAPI
 */
const fetchDailyActivity = async (
  mpId: string,
  apiBaseUrl: string,
  useMock: boolean
): Promise<DailyActivity[]> => {
  if (useMock) {
    return fetchMockDailyActivity(mpId);
  }

  const url = `${apiBaseUrl.replace(/\/$/, "")}/api/v1/mps/${encodeURIComponent(mpId)}/daily-activity`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(
      `Błąd podczas pobierania aktywności posła [${res.status} ${res.statusText}]`
    );
  }
  return res.json();
};

/**
 * Komponent MPActivityHeatmap – tablica aktywności poselskiej na wzór GitHuba
 */
export const MPActivityHeatmap: React.FC<MPActivityHeatmapProps> = ({
  mpId,
  mpName = "Poseł na Sejm RP",
  clubName = "Klub Parlamentarny",
  apiBaseUrl = "http://localhost:8000",
  useMock = true, // Domyślnie włączony mock dla ułatwienia testów frontendu
  className = "",
}) => {
  const { data: activities, isLoading, isError, error, refetch } = useQuery<
    DailyActivity[],
    Error
  >({
    queryKey: ["mpDailyActivity", mpId, useMock],
    queryFn: () => fetchDailyActivity(mpId, apiBaseUrl, useMock),
    staleTime: 1000 * 60 * 10, // 10 minut cache
  });

  // Obliczenia statystyk zagregowanych
  const sittingDays = activities?.filter((d) => d.dominant_status !== "NO_VOTES") ?? [];
  const totalVotesCast = sittingDays.reduce((acc, curr) => acc + curr.total_votes, 0);

  const avgAttendance = sittingDays.length
    ? Math.round(
        (sittingDays.reduce((acc, curr) => acc + curr.attendance_rate, 0) /
          sittingDays.length) *
          100
      )
    : 0;

  const avgPartyLoyalty = sittingDays.length
    ? Math.round(
        (sittingDays.reduce((acc, curr) => acc + (1 - curr.rebellion_rate), 0) /
          sittingDays.length) *
          100
      )
    : 0;

  // Stan ładowania (Skeleton)
  if (isLoading) {
    return (
      <div
        className={`w-full max-w-3xl rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 animate-pulse ${className}`}
      >
        <div className="h-5 w-48 rounded bg-slate-200 dark:bg-slate-800 mb-2" />
        <div className="h-4 w-32 rounded bg-slate-200 dark:bg-slate-800 mb-6" />
        <div className="flex gap-2 overflow-x-auto pb-2">
          {Array.from({ length: 30 }).map((_, i) => (
            <div
              key={i}
              className="h-8 w-8 shrink-0 rounded-md bg-slate-200 dark:bg-slate-800"
            />
          ))}
        </div>
      </div>
    );
  }

  // Stan błędu
  if (isError || !activities) {
    return (
      <div
        className={`w-full max-w-3xl rounded-xl border border-rose-200 bg-rose-50/50 p-6 dark:border-rose-900/50 dark:bg-rose-950/20 ${className}`}
      >
        <div className="flex items-center justify-between">
          <div>
            <h4 className="font-semibold text-rose-800 dark:text-rose-300">
              Błąd pobierania danych posła
            </h4>
            <p className="mt-1 text-sm text-rose-600 dark:text-rose-400">
              {error?.message || "Nie udało się załadować historii głosowań."}
            </p>
          </div>
          <button
            onClick={() => refetch()}
            className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-rose-700 active:scale-95"
          >
            Odśwież
          </button>
        </div>
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={150}>
      <div
        className={`w-full max-w-3xl rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 ${className}`}
      >
        {/* Nagłówek i statystyki posła */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-5 dark:border-slate-800">
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-bold tracking-tight text-slate-900 dark:text-slate-100">
                {mpName}
              </h3>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                {clubName}
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Aktywność poselska i dyscyplina głosowań w ostatnich 30 dniach
            </p>
          </div>

          {/* Podsumowanie wskaźników (KPI) */}
          <div className="flex items-center gap-4 text-xs">
            <div className="rounded-lg bg-slate-50 px-3 py-1.5 border border-slate-100 dark:bg-slate-800/60 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400">Frekwencja: </span>
              <span className="font-bold text-slate-900 dark:text-slate-100">
                {avgAttendance}%
              </span>
            </div>
            <div className="rounded-lg bg-slate-50 px-3 py-1.5 border border-slate-100 dark:bg-slate-800/60 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400">Zgodność: </span>
              <span className="font-bold text-emerald-600 dark:text-emerald-400">
                {avgPartyLoyalty}%
              </span>
            </div>
            <div className="hidden sm:block rounded-lg bg-slate-50 px-3 py-1.5 border border-slate-100 dark:bg-slate-800/60 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400">Głosowań: </span>
              <span className="font-bold text-slate-900 dark:text-slate-100">
                {totalVotesCast}
              </span>
            </div>
          </div>
        </div>

        {/* Sekcja Heatmapy (Siatka kafelków dni) */}
        <div className="mt-6">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-3">
            Oś Czasu Posiedzeń (Ostatnie 30 dni):
          </div>

          {/* Horyzontalna siatka kafelków ze scrollem na małych ekranach */}
          <div className="flex flex-wrap gap-2 sm:gap-2.5">
            {activities.map((day) => {
              const style = STATUS_STYLES[day.dominant_status];
              const attendancePercent = Math.round(day.attendance_rate * 100);
              const partyLoyaltyPercent = Math.round((1 - day.rebellion_rate) * 100);

              return (
                <Tooltip key={day.date}>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      aria-label={`Dzień ${day.date} - ${style.label}`}
                      className={`h-7 w-7 sm:h-8 sm:w-8 rounded-md transition-transform duration-150 hover:scale-110 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 ${style.bgClass}`}
                    />
                  </TooltipTrigger>
                  <TooltipContent
                    side="top"
                    className="rounded-lg border border-slate-200 bg-white p-3 text-xs shadow-lg dark:border-slate-800 dark:bg-slate-900"
                  >
                    <div className="font-semibold text-slate-900 dark:text-slate-100 border-b border-slate-100 pb-1.5 mb-1.5 dark:border-slate-800 flex items-center justify-between gap-3">
                      <span>{day.date}</span>
                      <span className="font-normal text-[11px] text-slate-500">
                        {style.label}
                      </span>
                    </div>

                    {day.dominant_status === "NO_VOTES" ? (
                      <div className="text-slate-500 dark:text-slate-400 italic">
                        Brak zaplanowanych głosowań w Sejmie
                      </div>
                    ) : (
                      <div className="space-y-1 text-slate-700 dark:text-slate-300">
                        <div className="flex justify-between gap-4">
                          <span className="text-slate-500 dark:text-slate-400">Frekwencja:</span>
                          <span className="font-medium">{attendancePercent}%</span>
                        </div>
                        <div className="flex justify-between gap-4">
                          <span className="text-slate-500 dark:text-slate-400">
                            Zgodność z klubem:
                          </span>
                          <span
                            className={`font-medium ${
                              partyLoyaltyPercent < 70
                                ? "text-rose-500"
                                : "text-emerald-600 dark:text-emerald-400"
                            }`}
                          >
                            {partyLoyaltyPercent}%
                          </span>
                        </div>
                        <div className="flex justify-between gap-4">
                          <span className="text-slate-500 dark:text-slate-400">
                            Liczba głosowań:
                          </span>
                          <span className="font-medium">{day.total_votes}</span>
                        </div>
                      </div>
                    )}
                  </TooltipContent>
                </Tooltip>
              );
            })}
          </div>
        </div>

        {/* Legenda kolorystyczna */}
        <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4 text-xs text-slate-600 dark:border-slate-800 dark:text-slate-400">
          <span className="font-medium">Legenda:</span>
          <div className="flex flex-wrap items-center gap-3.5">
            <div className="flex items-center gap-1.5">
              <span className="h-3 w-3 rounded-sm bg-emerald-500" />
              <span>Lojalny</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-3 w-3 rounded-sm bg-yellow-400" />
              <span>Mieszany</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-3 w-3 rounded-sm bg-rose-500" />
              <span>Bunt</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-3 w-3 rounded-sm bg-slate-800" />
              <span>Nieobecny</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="h-3 w-3 rounded-sm bg-slate-100 border border-slate-200 dark:bg-slate-800/40 dark:border-slate-800" />
              <span>Brak posiedzeń</span>
            </div>
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
};

export default MPActivityHeatmap;
