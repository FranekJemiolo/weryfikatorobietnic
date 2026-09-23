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
  interpellations_count?: number;
}

export interface MPProfile {
  id: number;
  first_name: string;
  last_name: string;
  club: string;
  active: boolean;
  interpellations_count?: number;
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

export interface PushSubscriptionData {
  endpoint: string;
  keys: {
    p256dh: string;
    auth: string;
  };
}

export interface SubscribePayload {
  subscription: PushSubscriptionData;
  target_type: "PROMISE" | "MP" | "CATEGORY";
  target_id: string;
}

export interface SubscribeResponse {
  success: boolean;
  message: string;
  subscription_id?: number | null;
}

export interface UnsubscribePayload {
  endpoint: string;
  target_type: "PROMISE" | "MP" | "CATEGORY";
  target_id: string;
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

import {
  SHOWCASE_PROMISES,
  SHOWCASE_PROMISE_DETAILS,
  SHOWCASE_TIMELINES,
  SHOWCASE_ANALYTICS,
  SHOWCASE_MPS_LIST,
} from "./showcaseData";

export const api = {
  /**
   * Pobiera listę wszystkich obietnic wyborczych wraz ze statusem LLM i kosztem OSR.
   * W przypadku braku aktywnego backendu (np. GitHub Pages) zwraca Złotą Bazę Pokazową.
   */
  async getPromises(): Promise<PromiseListItem[]> {
    try {
      return await request<PromiseListItem[]>("/api/v1/promises");
    } catch {
      return SHOWCASE_PROMISES;
    }
  },

  /**
   * Pobiera szczegółową ocenę konkretnej obietnicy wraz z wycinkami artykułów ustaw (Diff).
   */
  async getPromiseEvaluation(promiseId: string): Promise<PromiseEvaluationDetail> {
    try {
      return await request<PromiseEvaluationDetail>(`/api/v1/promises/${encodeURIComponent(promiseId)}/evaluation`);
    } catch {
      if (SHOWCASE_PROMISE_DETAILS[promiseId]) {
        return SHOWCASE_PROMISE_DETAILS[promiseId];
      }
      const p = SHOWCASE_PROMISES.find((x) => x.id === promiseId);
      if (p) {
        return {
          promise_id: p.id,
          title: p.title,
          full_text: `Deklaracja wyborcza ${p.party} w kategorii ${p.category}: ${p.title}.`,
          party: p.party,
          category: p.category,
          status: p.status,
          alignment_status: p.latest_alignment_status,
          confidence_score: p.confidence_score,
          estimated_budget_impact_pln: p.estimated_budget_impact_pln,
          justification: "Analiza AI na podstawie publicznych materiałów legislacyjnych Sejmu RP X Kadencji.",
          relevant_articles: [],
        };
      }
      throw new ApiError(404, "Nie znaleziono obietnicy");
    }
  },

  /**
   * Pobiera dzienną frekwencję i wskaźnik zgodności głosowań posła dla Heatmapy.
   */
  async getMPVotingActivity(mpId: number | string): Promise<DailyActivityItem[]> {
    try {
      return await request<DailyActivityItem[]>(`/api/v1/mps/${mpId}/voting-activity`);
    } catch {
      return [];
    }
  },

  /**
   * Pobiera podstawowe informacje profilowe posła.
   */
  async getMPProfile(mpId: number | string): Promise<MPProfile> {
    try {
      return await request<MPProfile>(`/api/v1/mps/${mpId}`);
    } catch {
      return {
        id: Number(mpId) || 1,
        first_name: "Poseł",
        last_name: `Sejmu RP (#${mpId})`,
        club: "Koalicja Obywatelska",
        active: true,
        interpellations_count: 14,
      };
    }
  },

  /**
   * Pobiera skrócony status karty obietnicy z postępem prac legislacyjnych.
   */
  async getPromiseStatus(promiseId: string): Promise<PromiseStatusCardData> {
    try {
      return await request<PromiseStatusCardData>(`/api/v1/promises/${encodeURIComponent(promiseId)}/status`);
    } catch {
      const p = SHOWCASE_PROMISES.find((x) => x.id === promiseId);
      return {
        promise_id: promiseId,
        promise_title: p?.title || "Obietnica",
        llm_alignment_status: p?.latest_alignment_status || "CZESCIOWO",
        llm_justification: "Analiza w toku na podstawie druków sejmowych.",
        time_elapsed_days: 140,
        current_stage: "Prace w komisjach sejmowych",
        stage_progress_percent: 65,
      };
    }
  },

  /**
   * Pobiera sekwencję etapów procesu legislacyjnego obietnicy (Time-to-Delivery).
   */
  async getPromiseTimeline(promiseId: string): Promise<TimelineEvent[]> {
    try {
      return await request<TimelineEvent[]>(`/api/v1/promises/${encodeURIComponent(promiseId)}/timeline`);
    } catch {
      return SHOWCASE_TIMELINES[promiseId] || [];
    }
  },

  /**
   * Pobiera globalne statystyki i podsumowanie wskaźników rządu (Government Score).
   */
  async getAnalyticsSummary(): Promise<AnalyticsSummary> {
    try {
      return await request<AnalyticsSummary>("/api/v1/analytics/summary");
    } catch {
      return SHOWCASE_ANALYTICS;
    }
  },

  /**
   * Wyszukuje obietnice wyborcze z parametrami filtrowania i paginacji.
   */
  async searchPromises(params?: PromiseSearchParams): Promise<PromiseSearchResponse> {
    try {
      const searchParams = new URLSearchParams();
      if (params?.q) searchParams.set("q", params.q);
      if (params?.party && params.party !== "ALL") searchParams.set("party", params.party);
      if (params?.status && params.status !== "ALL") searchParams.set("status", params.status);
      if (params?.category && params.category !== "ALL") searchParams.set("category", params.category);
      if (params?.limit !== undefined) searchParams.set("limit", params.limit.toString());
      if (params?.offset !== undefined) searchParams.set("offset", params.offset.toString());

      const queryString = searchParams.toString();
      return await request<PromiseSearchResponse>(
        `/api/v1/promises/search${queryString ? `?${queryString}` : ""}`
      );
    } catch {
      let filtered = [...SHOWCASE_PROMISES];
      if (params?.q) {
        const query = params.q.toLowerCase();
        filtered = filtered.filter(
          (p) =>
            p.title.toLowerCase().includes(query) ||
            p.category.toLowerCase().includes(query) ||
            p.party.toLowerCase().includes(query)
        );
      }
      if (params?.party && params.party !== "ALL") {
        filtered = filtered.filter((p) => p.party === params.party);
      }
      if (params?.status && params.status !== "ALL") {
        filtered = filtered.filter(
          (p) => p.status === params.status || p.latest_alignment_status === params.status
        );
      }
      if (params?.category && params.category !== "ALL") {
        filtered = filtered.filter((p) => p.category === params.category);
      }
      return {
        items: filtered,
        total: filtered.length,
        limit: params?.limit || 50,
        offset: params?.offset || 0,
      };
    }
  },

  /**
   * Pobiera publiczny klucz VAPID dla Service Workera.
   */
  async getVapidPublicKey(): Promise<string> {
    const res = await request<{ public_key: string }>("/api/v1/subscriptions/vapid-key");
    return res.public_key;
  },

  /**
   * Rejestruje subskrypcję Web Push dla obietnicy, posła lub kategorii.
   */
  async subscribePush(payload: SubscribePayload): Promise<SubscribeResponse> {
    return request<SubscribeResponse>("/api/v1/subscribe", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  /**
   * Usuwa subskrypcję Web Push.
   */
  async unsubscribePush(payload: UnsubscribePayload): Promise<{ success: boolean; message: string }> {
    return request<{ success: boolean; message: string }>("/api/v1/unsubscribe", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  /**
   * Pobiera listę posłów (Sprawdź Posła) z wyszukiwarką i filtrem klubów.
   */
  async getMPs(params?: {
    q?: string;
    club?: string;
    active_only?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<{ items: MPProfile[]; total: number }> {
    try {
      const searchParams = new URLSearchParams();
      if (params?.q) searchParams.set("q", params.q);
      if (params?.club && params.club !== "ALL") searchParams.set("club", params.club);
      if (params?.active_only !== undefined) searchParams.set("active_only", params.active_only.toString());
      if (params?.limit !== undefined) searchParams.set("limit", params.limit.toString());
      if (params?.offset !== undefined) searchParams.set("offset", params.offset.toString());

      const queryString = searchParams.toString();
      return await request<{ items: MPProfile[]; total: number }>(
        `/api/v1/mps${queryString ? `?${queryString}` : ""}`
      );
    } catch {
      let filtered = [...SHOWCASE_MPS_LIST];
      if (params?.q) {
        const query = params.q.toLowerCase();
        filtered = filtered.filter(
          (m) =>
            m.first_name.toLowerCase().includes(query) ||
            m.last_name.toLowerCase().includes(query) ||
            m.club.toLowerCase().includes(query)
        );
      }
      if (params?.club && params.club !== "ALL") {
        filtered = filtered.filter((m) => m.club.toLowerCase().includes(params.club!.toLowerCase()));
      }
      return {
        items: filtered,
        total: filtered.length,
      };
    }
  },
};

