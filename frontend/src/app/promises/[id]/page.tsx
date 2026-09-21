import React, { Suspense } from "react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowLeft,
  Coins,
  ShieldCheck,
  AlertTriangle,
  XCircle,
  HelpCircle,
  Bot,
  Sparkles,
  FileText,
  Scale,
  Building2,
  Calendar,
  AlertOctagon,
  Quote,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  LegislativeTimeline,
  LegislativeTimelineSkeleton,
} from "@/components/LegislativeTimeline";
import type { AlignmentStatus, PromiseEvaluationDetail } from "@/lib/api";
import { formatPLN } from "@/lib/utils";

interface PageProps {
  params: {
    id: string;
  };
}

/**
 * Konfiguracja wizualna statusu zgodności z LLM.
 */
const ALIGNMENT_CONFIG: Record<
  AlignmentStatus,
  {
    badgeVariant: "success" | "warning" | "danger" | "secondary";
    badgeText: string;
    icon: React.ComponentType<{ className?: string }>;
    cardBg: string;
    cardBorder: string;
    accentColor: string;
  }
> = {
  W_PELNI: {
    badgeVariant: "success",
    badgeText: "W PEŁNI ZGODNA",
    icon: ShieldCheck,
    cardBg: "bg-emerald-950/20 border-emerald-900/40",
    cardBorder: "border-emerald-800/60",
    accentColor: "text-emerald-400",
  },
  CZESCIOWO: {
    badgeVariant: "warning",
    badgeText: "CZĘŚCIOWO ZGODNA",
    icon: AlertTriangle,
    cardBg: "bg-amber-950/20 border-amber-900/40",
    cardBorder: "border-amber-800/60",
    accentColor: "text-amber-400",
  },
  SPRZECZNA: {
    badgeVariant: "danger",
    badgeText: "SPRZECZNA Z OBIETNICĄ",
    icon: XCircle,
    cardBg: "bg-rose-950/20 border-rose-900/40",
    cardBorder: "border-rose-800/60",
    accentColor: "text-rose-400",
  },
  BRAK_POWIAZANIA: {
    badgeVariant: "secondary",
    badgeText: "BRAK POWIĄZANIA",
    icon: HelpCircle,
    cardBg: "bg-slate-900/60 border-slate-800",
    cardBorder: "border-slate-700",
    accentColor: "text-slate-400",
  },
};

import {
  SHOWCASE_PROMISES,
  SHOWCASE_PROMISE_DETAILS,
  SHOWCASE_TIMELINES,
} from "@/lib/showcaseData";

/**
 * Pobiera szczegółową ocenę obietnicy bezpośrednio z backendu FastAPI po stronie serwera (RSC).
 * W przypadku eksportu statycznego lub braku połączenia z API zwraca dane z bazy pokazowej.
 */
async function getPromiseDetail(id: string): Promise<PromiseEvaluationDetail | null> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL;
  if (baseUrl && process.env.NEXT_EXPORT !== "true") {
    try {
      const res = await fetch(`${baseUrl}/api/v1/promises/${encodeURIComponent(id)}/evaluation`, {
        next: { revalidate: 60 }, // ISR: odświeżanie danych co 60 sekund
      });

      if (res.ok) {
        return res.json();
      }
    } catch (error) {
      console.error(`Błąd pobierania obietnicy ID ${id} z API:`, error);
    }
  }

  if (SHOWCASE_PROMISE_DETAILS[id]) {
    return SHOWCASE_PROMISE_DETAILS[id];
  }

  const p = SHOWCASE_PROMISES.find((x) => x.id === id);
  if (p) {
    return {
      promise_id: p.id,
      title: p.title,
      full_text: `Deklaracja wyborcza partii ${p.party} w kategorii ${p.category}: "${p.title}".`,
      party: p.party,
      category: p.category,
      status: p.status,
      alignment_status: p.latest_alignment_status,
      confidence_score: p.confidence_score,
      bill_title: `Projekt ustawy regulujący obszar: ${p.category}`,
      bill_print_num: "X/2024",
      estimated_budget_impact_pln: p.estimated_budget_impact_pln,
      divergence_details: "Wstępna analiza zgodności z deklaracją wyborczą; Trwają konsultacje międzyresortowe.",
      justification: `Model AI przeprowadził analizę deklaracji programowej komitetu ${p.party} i porównał ją z aktualnym stanem procesu prawodawczego w Sejmie RP X Kadencji.`,
      relevant_articles: [],
    };
  }

  return null;
}

// Required for `next export` (GitHub Pages static build)
export const dynamic = "force-static";
export const dynamicParams = false;

/**
 * Dla `next export`: generuje statyczne strony HTML dla wszystkich
 * 12 zdefiniowanych obietnic wyborczych Sejmu RP X Kadencji.
 */
export function generateStaticParams() {
  return SHOWCASE_PROMISES.map((p) => ({ id: p.id }));
}

/**
 * Dynamiczne generowanie metadanych SEO dla podstrony obietnicy.
 */
export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const detail = await getPromiseDetail(params.id);

  if (!detail) {
    return {
      title: "Obietnica nie została odnaleziona | Weryfikator Obietnic",
    };
  }

  const statusLabel = detail.alignment_status
    ? ALIGNMENT_CONFIG[detail.alignment_status]?.badgeText || detail.alignment_status
    : "Weryfikacja w toku";

  return {
    title: `${detail.title} (${detail.party}) – Szczegóły i Oś Czasu | Weryfikator Obietnic`,
    description: `Audyt obywatelski obietnicy partii ${detail.party}: "${detail.title}". Ocena AI: ${statusLabel}. Szacowany koszt budżetowy OSR oraz chronologiczna oś procesu legislacyjnego w Sejmie.`,
  };
}

/**
 * Rozbija ciąg opisujący luki na poszczególne punkty w liście.
 */
function parseDivergences(divergenceDetails?: string | null): string[] {
  if (!divergenceDetails) return [];
  // Obsługa podziału po średnikach lub nowych liniach
  return divergenceDetails
    .split(/;|\n/)
    .map((s) => s.trim().replace(/^[-•*]\s*/, ""))
    .filter((s) => s.length > 0);
}

/**
 * Asynchroniczny React Server Component dla dynamicznej podstrony obietnicy.
 */
export default async function PromiseDetailPage({ params }: PageProps) {
  const detail = await getPromiseDetail(params.id);

  if (!detail) {
    notFound();
  }

  const alignmentStatus = detail.alignment_status || "CZESCIOWO";
  const config = ALIGNMENT_CONFIG[alignmentStatus] || ALIGNMENT_CONFIG.CZESCIOWO;
  const StatusIcon = config.icon;
  const divergences = parseDivergences(detail.divergence_details);

  return (
    <div className="mx-auto max-w-5xl space-y-10 pb-16">
      {/* Przycisk nawigacji powrotnej */}
      <div>
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-xs sm:text-sm text-slate-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Powrót do katalogu obietnic
        </Link>
      </div>

      {/* ========================================================================= */}
      {/* SEKCJA 1: NAGŁÓWEK (HERO) */}
      {/* ========================================================================= */}
      <section className="relative overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-900/95 to-indigo-950/40 p-6 sm:p-10 shadow-2xl space-y-6">
        {/* Metadane nagłówka: Identyfikator, Partia, Kategoria */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-md border border-slate-700 bg-slate-800 px-2.5 py-1 text-xs font-bold uppercase tracking-wider text-slate-200">
              Partia: {detail.party}
            </span>
            <span className="rounded-md border border-slate-800 bg-slate-900/80 px-2.5 py-1 text-xs font-medium text-slate-400">
              Kategoria: {detail.category}
            </span>
            <span className="font-mono text-xs text-slate-500">ID: {detail.promise_id}</span>
          </div>

          {/* Przypięty Badge z ostateczną oceną z LLM */}
          <Badge
            variant={config.badgeVariant}
            className="flex items-center gap-1.5 px-3 py-1 text-xs sm:text-sm font-semibold shadow-md"
          >
            <StatusIcon className="h-4 w-4" />
            <span>{config.badgeText}</span>
          </Badge>
        </div>

        {/* Główny tytuł obietnicy */}
        <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold tracking-tight text-white leading-tight">
          {detail.title}
        </h1>

        {/* Wycena kosztu w PLN z OSR */}
        <div className="flex flex-wrap items-center gap-4 pt-2">
          <div className="flex items-center gap-2.5 rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-2.5 text-amber-300">
            <Coins className="h-5 w-5 text-amber-400" />
            <div>
              <span className="block text-[10px] font-semibold uppercase tracking-wider text-amber-400/80">
                Wpływ na finanse publiczne (OSR)
              </span>
              <span className="text-base sm:text-lg font-bold text-amber-200">
                {formatPLN(detail.estimated_budget_impact_pln)}
              </span>
            </div>
          </div>

          {detail.bill_print_num && (
            <div className="flex items-center gap-2 rounded-xl border border-sky-500/20 bg-sky-500/10 px-4 py-2.5 text-sky-300">
              <Building2 className="h-5 w-5 text-sky-400" />
              <div>
                <span className="block text-[10px] font-semibold uppercase tracking-wider text-sky-400/80">
                  Druk Sejmowy
                </span>
                <span className="text-sm sm:text-base font-bold text-sky-200">
                  Nr {detail.bill_print_num}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Pierwotna treść deklaracji wyborczej */}
        <div className="rounded-xl border border-slate-800/80 bg-slate-950/60 p-4 sm:p-5">
          <div className="flex items-start gap-3">
            <Quote className="h-5 w-5 shrink-0 text-slate-500 mt-0.5" />
            <div className="space-y-1">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Oryginalna deklaracja programowa:
              </span>
              <p className="text-sm sm:text-base text-slate-200 italic leading-relaxed">
                „{detail.full_text}”
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* SEKCJA 2: WERDYKT AI ("RAPORT AUDYTORA") */}
      {/* ========================================================================= */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-indigo-400" />
            <h2 className="text-lg sm:text-xl font-bold text-white tracking-tight">
              Werdykt AI: Raport Audytora
            </h2>
          </div>
          {detail.confidence_score !== undefined && detail.confidence_score !== null && (
            <span className="text-xs text-slate-400">
              Pewność oceny:{" "}
              <strong className="text-white">
                {Math.round(detail.confidence_score * 100)}%
              </strong>
            </span>
          )}
        </div>

        <Card className={`overflow-hidden transition-all shadow-xl ${config.cardBg}`}>
          <CardHeader className="border-b border-slate-800/60 pb-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Sparkles className={`h-4 w-4 ${config.accentColor}`} />
                <CardTitle className="text-base sm:text-lg font-bold">
                  Ocena zgodności normatywnej: {config.badgeText}
                </CardTitle>
              </div>
              <span className="font-mono text-[11px] text-slate-400">
                Model: RAG + Gemini 2.5 Flash
              </span>
            </div>
            {detail.bill_title && (
              <CardDescription className="text-xs text-slate-300 mt-1">
                Oceniany projekt ustawy: <strong>{detail.bill_title}</strong>
              </CardDescription>
            )}
          </CardHeader>

          <CardContent className="space-y-6 pt-6">
            {/* Uzasadnienie modelu (justification) */}
            <div className="space-y-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <Scale className="h-3.5 w-3.5 text-indigo-400" />
                Uzasadnienie merytoryczne audytora:
              </h3>
              <p className="text-sm sm:text-base text-slate-200 leading-relaxed bg-slate-950/40 rounded-lg p-4 border border-slate-800/50">
                {detail.justification ||
                  "Trwa pogłębiona ewaluacja semantyczna w pgvector pod kątem zgodności normatywnej z deklaracjami komitetu."}
              </p>
            </div>

            {/* Wypunktowane luki między obietnicą a ustawą (divergence_details) */}
            {divergences.length > 0 ? (
              <div className="space-y-2.5">
                <h3 className="text-xs font-bold uppercase tracking-wider text-rose-400 flex items-center gap-1.5">
                  <AlertOctagon className="h-3.5 w-3.5 text-rose-400" />
                  Zidentyfikowane luki i rozbieżności normatywne:
                </h3>
                <ul className="space-y-2 rounded-lg border border-rose-900/30 bg-rose-950/10 p-4">
                  {divergences.map((item, idx) => (
                    <li key={idx} className="flex items-start gap-2.5 text-xs sm:text-sm text-rose-200">
                      <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-rose-400 shrink-0" />
                      <span className="leading-relaxed">{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : detail.divergence_details ? (
              <div className="space-y-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-rose-400 flex items-center gap-1.5">
                  <AlertOctagon className="h-3.5 w-3.5 text-rose-400" />
                  Zidentyfikowane luki i rozbieżności:
                </h3>
                <p className="rounded-lg border border-rose-900/30 bg-rose-950/10 p-3.5 text-xs sm:text-sm text-rose-200 leading-relaxed">
                  {detail.divergence_details}
                </p>
              </div>
            ) : null}

            {/* Powiązane artykuły prawne (Wycinki z ustawy) */}
            {detail.relevant_articles && detail.relevant_articles.length > 0 && (
              <div className="space-y-3 pt-2">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <FileText className="h-3.5 w-3.5 text-sky-400" />
                  Kluczowe artykuły procedowanej ustawy:
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {detail.relevant_articles.map((art, idx) => (
                    <div
                      key={idx}
                      className="rounded-lg border border-slate-800 bg-slate-950/70 p-3.5 space-y-1.5"
                    >
                      <span className="inline-block rounded bg-indigo-950/60 border border-indigo-800/40 px-2 py-0.5 font-mono text-[11px] font-semibold text-indigo-300">
                        {art.article_number}
                      </span>
                      <p className="text-xs text-slate-300 line-clamp-3 leading-relaxed">
                        {art.raw_text}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      {/* ========================================================================= */}
      {/* SEKCJA 3: OŚ CZASU (TIME-TO-DELIVERY) */}
      {/* ========================================================================= */}
      <section className="space-y-6 pt-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Calendar className="h-5 w-5 text-sky-400" />
            <h2 className="text-lg sm:text-xl font-bold text-white tracking-tight">
              Oś Czasu Procesu Legislacyjnego (Time-to-Delivery)
            </h2>
          </div>
          <p className="text-xs sm:text-sm text-slate-400">
            Śledzenie etapów prac parlamentarnych: od wniesienia deklaracji wyborczej, przez etapy czytań w Sejmie i Senacie, aż po podpis Prezydenta RP.
          </p>
        </div>

        {/* Wertykalna oś czasu ładowana przez React Query z Suspense */}
        <Suspense fallback={<LegislativeTimelineSkeleton />}>
          <LegislativeTimeline
            promiseId={detail.promise_id}
            initialData={SHOWCASE_TIMELINES[detail.promise_id] || []}
          />
        </Suspense>
      </section>
    </div>
  );
}
