"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  FileText,
  Clock,
  Sparkles,
  Coins,
  ChevronRight,
  ShieldCheck,
  AlertTriangle,
  XCircle,
  HelpCircle,
} from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { api, type AlignmentStatus, type PromiseListItem } from "@/lib/api";
import { formatPLN } from "@/lib/utils";

export interface PromiseCardProps {
  promiseId?: string;
  initialData?: PromiseListItem;
  className?: string;
  onSelect?: (id: string) => void;
}

const STATUS_BADGE_CONFIG: Record<
  AlignmentStatus,
  {
    variant: "success" | "warning" | "danger" | "secondary";
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    progressValue: number;
    indicatorColor: string;
  }
> = {
  W_PELNI: {
    variant: "success",
    label: "W PEŁNI ZGODNA",
    icon: ShieldCheck,
    progressValue: 100,
    indicatorColor: "bg-emerald-500",
  },
  CZESCIOWO: {
    variant: "warning",
    label: "CZĘŚCIOWO ZGODNA",
    icon: AlertTriangle,
    progressValue: 50,
    indicatorColor: "bg-amber-500",
  },
  SPRZECZNA: {
    variant: "danger",
    label: "SPRZECZNA Z OBIETNICĄ",
    icon: XCircle,
    progressValue: 20,
    indicatorColor: "bg-rose-500",
  },
  BRAK_POWIAZANIA: {
    variant: "secondary",
    label: "BRAK POWIĄZANIA W USTAWIE",
    icon: HelpCircle,
    progressValue: 10,
    indicatorColor: "bg-slate-400",
  },
};

export function PromiseCardSkeleton() {
  return (
    <Card className="animate-pulse border-slate-800/80 bg-slate-900/60 p-6">
      <div className="flex items-center justify-between pb-4">
        <div className="h-6 w-24 rounded-full bg-slate-800" />
        <div className="h-6 w-32 rounded-full bg-slate-800" />
      </div>
      <div className="h-6 w-3/4 rounded bg-slate-800 mb-2" />
      <div className="h-4 w-1/2 rounded bg-slate-800 mb-6" />
      <div className="h-20 w-full rounded-lg bg-slate-800/50 mb-4" />
      <div className="h-2 w-full rounded bg-slate-800 mb-3" />
      <div className="flex justify-between pt-2">
        <div className="h-4 w-28 rounded bg-slate-800" />
        <div className="h-4 w-20 rounded bg-slate-800" />
      </div>
    </Card>
  );
}

export function PromiseCard({
  promiseId,
  initialData,
  className,
  onSelect,
}: PromiseCardProps) {
  const activeId = promiseId || initialData?.id || "";

  // Pobranie szczegółów ewaluacji obietnicy przez RAG / LLM
  const { data: evalDetail, isLoading } = useQuery({
    queryKey: ["promise-evaluation", activeId],
    queryFn: () => api.getPromiseEvaluation(activeId),
    enabled: Boolean(activeId),
  });

  if (isLoading && !initialData) {
    return <PromiseCardSkeleton />;
  }

  const title = evalDetail?.title || initialData?.title || "Brak tytułu deklaracji";
  const party = evalDetail?.party || initialData?.party || "Koalicja";
  const category = evalDetail?.category || initialData?.category || "Ogólne";
  const statusRaw = evalDetail?.alignment_status || initialData?.latest_alignment_status || "CZESCIOWO";
  const config = STATUS_BADGE_CONFIG[statusRaw] || STATUS_BADGE_CONFIG.CZESCIOWO;
  const StatusIcon = config.icon;
  const justification =
    evalDetail?.justification ||
    "Trwa analiza prawna i wektoryzacja artykułów projektu w pgvector. Wykryto zbieżność tematyczną z procedowanym drukiem sejmowym.";
  const budgetCost = initialData?.estimated_budget_impact_pln;
  const billPrintNum = evalDetail?.bill_print_num;

  return (
    <Card
      onClick={() => onSelect?.(activeId)}
      className={`group relative overflow-hidden border-slate-800/80 bg-slate-900/70 shadow-lg backdrop-blur-sm transition-all duration-300 hover:border-slate-700 hover:shadow-indigo-500/10 hover:shadow-2xl ${className || ""}`}
    >
      {/* Kolorowy akcent na górnej krawędzi */}
      <div className={`h-1 w-full ${config.indicatorColor}`} />

      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="rounded-md bg-slate-800 px-2 py-0.5 text-xs font-semibold text-slate-300 uppercase tracking-wider">
              {party}
            </span>
            <span className="text-xs text-slate-400 font-medium">
              {category}
            </span>
          </div>
          <Badge variant={config.variant} className="gap-1.5 py-1 px-3">
            <StatusIcon className="h-3.5 w-3.5" />
            <span>{config.label}</span>
          </Badge>
        </div>

        <CardTitle className="pt-2 text-base font-bold text-slate-100 group-hover:text-indigo-300 transition-colors sm:text-lg">
          {title}
        </CardTitle>
        <CardDescription className="line-clamp-2 text-xs text-slate-400">
          ID: {activeId} {billPrintNum ? `• Sejm Druk nr ${billPrintNum}` : ""}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4 pb-3">
        {/* Cytat z wnioskowaniem LLM */}
        <div className="relative rounded-lg border border-slate-800 bg-slate-950/60 p-3.5 text-xs sm:text-sm text-slate-300">
          <div className="flex items-center gap-1.5 pb-1.5 text-xs font-semibold text-indigo-400">
            <Sparkles className="h-3.5 w-3.5" />
            <span>Audyt RAG (LLM Reasoning)</span>
          </div>
          <blockquote className="italic leading-relaxed text-slate-300 before:content-['„'] after:content-['”']">
            {justification}
          </blockquote>
        </div>

        {/* Pasek postępu legislacyjnego */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              Postęp wdrożenia
            </span>
            <span className="font-semibold text-slate-200">
              {config.progressValue}%
            </span>
          </div>
          <Progress
            value={config.progressValue}
            indicatorColor={config.indicatorColor}
            className="h-2 bg-slate-800"
          />
        </div>
      </CardContent>

      <CardFooter className="flex items-center justify-between border-t border-slate-800/60 pt-3 text-xs text-slate-400">
        <div className="flex items-center gap-1.5 font-medium text-slate-300">
          <Coins className="h-3.5 w-3.5 text-amber-400" />
          <span>OSR: {formatPLN(budgetCost)}</span>
        </div>

        {evalDetail?.relevant_articles && evalDetail.relevant_articles.length > 0 && (
          <div className="flex items-center gap-1 text-indigo-400 group-hover:translate-x-0.5 transition-transform">
            <FileText className="h-3.5 w-3.5" />
            <span>{evalDetail.relevant_articles.length} art. w ustawie</span>
            <ChevronRight className="h-3.5 w-3.5" />
          </div>
        )}
      </CardFooter>
    </Card>
  );
}
