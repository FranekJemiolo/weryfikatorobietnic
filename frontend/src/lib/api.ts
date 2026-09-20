/**
 * Klient HTTP łączący się z backendem FastAPI projektu "Weryfikator Obietnic".
 * Zapewnia pełne typowanie zgodne ze schematami Pydantic w FastAPI.
 */

export type AlignmentStatus = "W_PELNI" | "CZESCIOWO" | "SPRZECZNA" | "BRAK_POWIAZANIA";

export interface PromiseListItem {
  id: string;
  party: string;
  title: string;
  category: string;
  status: string;
  latest_alignment_status?: AlignmentStatus | null;
  confidence_score?: number | null;
  estimated_budget_impact_pln?: number | null;
  created_at: string;
}

export interface ArticleExcerpt {
  article_number: string;
  raw_text: string;
}

export interface TimelineEvent {
  date: string;
  stage_name: string;
  description: string;
  is_completed: boolean;
}

export interface PromiseEvaluationDetail {
  promise_id: string;
  title: string;
  full_text: string;
  party: string;
  category: string;
  status: string;
  alignment_status?: AlignmentStatus | null;
  justification?: string | null;
  confidence_score?: number | null;
  bill_id?: string | null;
  bill_title?: string | null;
  bill_print_num?: string | null;
  estimated_budget_impact_pln?: number | null;
  divergence_details?: string | null;
  relevant_articles: ArticleExcerpt[];
}

export interface DailyActivityItem {
  date: string; // YYYY-MM-DD
  total_votes: number;
  attendance_rate: number; // 0.0 - 1.0
  rebellion_rate?: number; // 0.0 - 1.0
  dominant_status: "LOYAL" | "REBELLIOUS" | "ABSENT" | "MIXED" | "NO_VOTES";
}

export interface MPProfile {
  id: number;
  first_name: string;
  last_name: string;
  club: string;
  active: boolean;
}

export interface PromiseStatusCardData {
  promise_id: string;
  promise_title: string;
  llm_alignment_status: AlignmentStatus;
  llm_justification: string;
  time_elapsed_days: number;
  current_stage: string;
  stage_progress_percent?: number;
  divergence_details?: string | null;
  source_print_number?: string | null;
}

export interface AnalyticsSummary {
  total_promises: number;
  fulfilled_count: number;
  in_progress_count: number;
  broken_count: number;
  average_delivery_days?: number | null;
}

export interface PromiseSearchResponse {
  items: PromiseListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface PromiseSearchParams {
  q?: string;
  party?: string;
  status?: string;
  category?: string;
  limit?: number;
  offset?: number;
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined" ? "" : "http://localhost:8000");

class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = {
    "Content-Type": "application/json",
    Accept: "application/json",
    ...options?.headers,
  };

  const res = await fetch(url, { ...options, headers });
  if (!res.ok) {
    let errorDetail = `Błąd HTTP ${res.status}: ${res.statusText}`;
    try {
      const errorJson = await res.json();
      if (errorJson?.detail) {
        errorDetail = typeof errorJson.detail === "string" ? errorJson.detail : JSON.stringify(errorJson.detail);
      }
    } catch {
      // Ignorowanie błędu parsowania JSON błędu
    }
    throw new ApiError(res.status, errorDetail);
  }

  return res.json() as Promise<T>;
}

export const api = {
  /**
   * Pobiera listę wszystkich obietnic wyborczych wraz ze statusem LLM i kosztem OSR.
   */
  async getPromises(): Promise<PromiseListItem[]> {
    return request<PromiseListItem[]>("/api/v1/promises");
  },

  /**
   * Pobiera szczegółową ocenę konkretnej obietnicy wraz z wycinkami artykułów ustaw (Diff).
   */
  async getPromiseEvaluation(promiseId: string): Promise<PromiseEvaluationDetail> {
    return request<PromiseEvaluationDetail>(`/api/v1/promises/${encodeURIComponent(promiseId)}/evaluation`);
  },

  /**
   * Pobiera dzienną frekwencję i wskaźnik zgodności głosowań posła dla Heatmapy.
   */
  async getMPVotingActivity(mpId: number | string): Promise<DailyActivityItem[]> {
    return request<DailyActivityItem[]>(`/api/v1/mps/${mpId}/voting-activity`);
  },

  /**
   * Pobiera podstawowe informacje profilowe posła.
   */
  async getMPProfile(mpId: number | string): Promise<MPProfile> {
    return request<MPProfile>(`/api/v1/mps/${mpId}`);
  },

  /**
   * Pobiera skrócony status karty obietnicy z postępem prac legislacyjnych.
   */
  async getPromiseStatus(promiseId: string): Promise<PromiseStatusCardData> {
    return request<PromiseStatusCardData>(`/api/v1/promises/${encodeURIComponent(promiseId)}/status`);
  },

  /**
   * Pobiera sekwencję etapów procesu legislacyjnego obietnicy (Time-to-Delivery).
   */
  async getPromiseTimeline(promiseId: string): Promise<TimelineEvent[]> {
    return request<TimelineEvent[]>(`/api/v1/promises/${encodeURIComponent(promiseId)}/timeline`);
  },

  /**
   * Pobiera globalne statystyki i podsumowanie wskaźników rządu (Government Score).
   */
  async getAnalyticsSummary(): Promise<AnalyticsSummary> {
    return request<AnalyticsSummary>("/api/v1/analytics/summary");
  },

  /**
   * Wyszukuje obietnice wyborcze z parametrami filtrowania i paginacji.
   */
  async searchPromises(params?: PromiseSearchParams): Promise<PromiseSearchResponse> {
    const searchParams = new URLSearchParams();
    if (params?.q) searchParams.set("q", params.q);
    if (params?.party && params.party !== "ALL") searchParams.set("party", params.party);
    if (params?.status && params.status !== "ALL") searchParams.set("status", params.status);
    if (params?.category && params.category !== "ALL") searchParams.set("category", params.category);
    if (params?.limit !== undefined) searchParams.set("limit", params.limit.toString());
    if (params?.offset !== undefined) searchParams.set("offset", params.offset.toString());

    const queryString = searchParams.toString();
    return request<PromiseSearchResponse>(
      `/api/v1/promises/search${queryString ? `?${queryString}` : ""}`
    );
  },
};
