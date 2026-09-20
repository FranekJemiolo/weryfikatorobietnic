import React from "react";
import { useQuery } from "@tanstack/react-query";

/**
 * Model odpowiedzi zwracany przez endpoint FastAPI:
 * GET /api/v1/promises/{promise_id}/status
 */
export interface PromiseStatusResponse {
  promise_id: string;
  promise_title: string;
  llm_alignment_status: "W_PELNI" | "CZESCIOWO" | "SPRZECZNA" | "BRAK_POWIAZANIA";
  llm_justification: string;
  time_elapsed_days: number;
  current_stage: string;
  stage_progress_percent?: number;
  divergence_details?: string | null;
  source_print_number?: string | null;
}

export interface PromiseEvaluationCardProps {
  promiseId: string;
  apiBaseUrl?: string;
  className?: string;
}

/**
 * Konfiguracja stylów i etykiet dla poszczególnych statusów weryfikacji LLM.
 */
const STATUS_CONFIG: Record<
  PromiseStatusResponse["llm_alignment_status"],
  { label: string; badgeClasses: string; dotClass: string }
> = {
  W_PELNI: {
    label: "W PEŁNI ZGODNA",
    badgeClasses:
      "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800",
    dotClass: "bg-emerald-500",
  },
  CZESCIOWO: {
    label: "CZĘŚCIOWO ZGODNA",
    badgeClasses:
      "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800",
    dotClass: "bg-amber-500",
  },
  SPRZECZNA: {
    label: "SPRZECZNA / ZŁAMANA",
    badgeClasses:
      "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800",
    dotClass: "bg-rose-500",
  },
  BRAK_POWIAZANIA: {
    label: "BRAK POWIĄZANIA",
    badgeClasses:
      "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700",
    dotClass: "bg-slate-400",
  },
};

/**
 * Funkcja pobierająca status obietnicy z FastAPI
 */
const fetchPromiseStatus = async (
  promiseId: string,
  apiBaseUrl: string
): Promise<PromiseStatusResponse> => {
  const url = `${apiBaseUrl.replace(/\/$/, "")}/api/v1/promises/${encodeURIComponent(promiseId)}/status`;
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(
      `Błąd podczas pobierania statusu obietnicy [${response.status} ${response.statusText}]`
    );
  }

  return response.json();
};

/**
 * Komponent ewaluacji obietnicy wyborczej zintegrowany z FastAPI i modelem LLM.
 */
export const PromiseEvaluationCard: React.FC<PromiseEvaluationCardProps> = ({
  promiseId,
  apiBaseUrl = "http://localhost:8000",
  className = "",
}) => {
  const { data, isLoading, isError, error, refetch } = useQuery<PromiseStatusResponse, Error>({
    queryKey: ["promiseStatus", promiseId],
    queryFn: () => fetchPromiseStatus(promiseId, apiBaseUrl),
    staleTime: 1000 * 60 * 5, // 5 minut cache w pamięci
  });

  // Stan ładowania (Skeleton Loader)
  if (isLoading) {
    return (
      <div
        className={`w-full max-w-xl rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 animate-pulse ${className}`}
      >
        <div className="flex items-center justify-between gap-4">
          <div className="h-4 w-24 rounded bg-slate-200 dark:bg-slate-800" />
          <div className="h-6 w-32 rounded-full bg-slate-200 dark:bg-slate-800" />
        </div>
        <div className="mt-4 h-6 w-3/4 rounded bg-slate-200 dark:bg-slate-800" />
        <div className="mt-6 space-y-2">
          <div className="h-3 w-full rounded bg-slate-200 dark:bg-slate-800" />
          <div className="h-3 w-5/6 rounded bg-slate-200 dark:bg-slate-800" />
        </div>
        <div className="mt-6 h-2 w-full rounded-full bg-slate-200 dark:bg-slate-800" />
      </div>
    );
  }

  // Stan błędu komunikacji z API
  if (isError || !data) {
    return (
      <div
        className={`w-full max-w-xl rounded-xl border border-rose-200 bg-rose-50/50 p-6 dark:border-rose-900/50 dark:bg-rose-950/20 ${className}`}
      >
        <div className="flex items-start justify-between">
          <div>
            <h4 className="font-semibold text-rose-800 dark:text-rose-300">
              Nie udało się pobrać statusu obietnicy
            </h4>
            <p className="mt-1 text-sm text-rose-600 dark:text-rose-400">
              {error?.message || "Wystąpił nieoczekiwany błąd komunikacji z API."}
            </p>
          </div>
          <button
            onClick={() => refetch()}
            className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-rose-700 active:scale-95"
          >
            Spróbuj ponownie
          </button>
        </div>
      </div>
    );
  }

  const statusMeta = STATUS_CONFIG[data.llm_alignment_status] || STATUS_CONFIG.BRAK_POWIAZANIA;
  const progressValue = data.stage_progress_percent ?? 50;

  return (
    <div
      className={`group relative w-full max-w-xl rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition-all hover:shadow-md dark:border-slate-800 dark:bg-slate-900 ${className}`}
    >
      {/* Nagłówek karty: Identyfikator oraz Badge Statusu */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs font-mono text-slate-500 dark:text-slate-400">
          <span>{data.promise_id}</span>
          {data.source_print_number && (
            <>
              <span>•</span>
              <span className="font-medium text-slate-700 dark:text-slate-300">
                {data.source_print_number}
              </span>
            </>
          )}
        </div>

        {/* Dynamiczny Badge Zgodności */}
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold tracking-wide ${statusMeta.badgeClasses}`}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${statusMeta.dotClass}`} />
          {statusMeta.label}
        </span>
      </div>

      {/* Tytuł deklaracji wyborczej */}
      <h3 className="mt-3 text-lg font-bold tracking-tight text-slate-900 dark:text-slate-100">
        {data.promise_title}
      </h3>

      {/* Uzasadnienie modelu LLM w postaci Blockquote */}
      <div className="mt-4">
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-1.5">
          Analiza Semantyczna LLM:
        </div>
        <blockquote className="border-l-4 border-indigo-500 bg-slate-50 py-2.5 px-3.5 text-sm italic leading-relaxed text-slate-700 dark:border-indigo-400 dark:bg-slate-800/60 dark:text-slate-300 rounded-r-md">
          „{data.llm_justification}”
        </blockquote>
      </div>

      {/* Detale rozbieżności (jeśli zidentyfikowane przez model) */}
      {data.divergence_details && (
        <div className="mt-3 rounded-md bg-amber-50/70 p-3 text-xs text-amber-800 dark:bg-amber-950/30 dark:text-amber-300 border border-amber-200/60 dark:border-amber-900/50">
          <span className="font-semibold">Rozbieżność względem deklaracji: </span>
          {data.divergence_details}
        </div>
      )}

      {/* Ścieżka legislacyjna i pasek postępu (Progress Bar) */}
      <div className="mt-6 border-t border-slate-100 pt-4 dark:border-slate-800">
        <div className="flex items-center justify-between text-xs font-medium text-slate-600 dark:text-slate-400 mb-2">
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
            <span className="font-semibold text-slate-800 dark:text-slate-200">
              {data.current_stage}
            </span>
          </div>
          <span>{data.time_elapsed_days} dni w toku</span>
        </div>

        {/* Wskaźnik postępu (Progress bar) */}
        <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
          <div
            className="h-full rounded-full bg-blue-600 transition-all duration-500 ease-out dark:bg-blue-500"
            style={{ width: `${progressValue}%` }}
          />
        </div>
      </div>
    </div>
  );
};

export default PromiseEvaluationCard;
