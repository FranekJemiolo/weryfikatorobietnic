"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from "recharts";
import {
  Award,
  Clock,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  FileText,
  Activity,
  TrendingUp,
} from "lucide-react";
import { api, type AnalyticsSummary } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export interface GovernmentScoreDashboardProps {
  initialData?: AnalyticsSummary;
}

const DONUT_COLORS = {
  fulfilled: "#10b981", // Emerald-500
  in_progress: "#f59e0b", // Amber-500
  broken: "#ef4444", // Rose-500
  other: "#64748b", // Slate-500
};

/**
 * Szkielet animowany (Skeleton) dla panelu statystyk rządowych.
 */
export function GovernmentScoreDashboardSkeleton() {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 sm:p-8 space-y-6 animate-pulse">
      <div className="h-7 w-64 bg-slate-800 rounded" />
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-5 h-64 bg-slate-800/60 rounded-xl" />
        <div className="lg:col-span-7 grid grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 bg-slate-800/50 rounded-xl p-4 space-y-2">
              <div className="h-4 w-20 bg-slate-700/60 rounded" />
              <div className="h-8 w-16 bg-slate-700 rounded" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    name: string;
    value: number;
    payload: { fill: string; percentStr: string };
  }>;
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (active && payload && payload.length) {
    const data = payload[0];
    return (
      <div className="rounded-lg border border-slate-700 bg-slate-900/95 px-3 py-2 text-xs shadow-xl backdrop-blur-md">
        <div className="flex items-center gap-2 font-medium text-white">
          <span
            className="h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: data.payload.fill }}
          />
          <span>{data.name}</span>
        </div>
        <div className="mt-1 text-slate-300">
          Liczba: <strong className="text-white">{data.value}</strong> ({data.payload.percentStr})
        </div>
      </div>
    );
  }
  return null;
}

/**
 * Główny komponent Big Picture prezentujący wskaźniki rządu (Overall Government Score)
 * z wykresem pierścieniowym (Donut Chart) i kaflami analitycznymi.
 */
export function GovernmentScoreDashboard({ initialData }: GovernmentScoreDashboardProps) {
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => {
    setMounted(true);
  }, []);

  const { data, isLoading } = useQuery({
    queryKey: ["analytics-summary"],
    queryFn: () => api.getAnalyticsSummary(),
    initialData,
    staleTime: 60 * 1000,
  });

  if (isLoading && !data) {
    return <GovernmentScoreDashboardSkeleton />;
  }

  const total = data?.total_promises || 0;
  const fulfilled = data?.fulfilled_count || 0;
  const inProgress = data?.in_progress_count || 0;
  const broken = data?.broken_count || 0;
  const other = Math.max(0, total - (fulfilled + inProgress + broken));

  const deliveryRate = total > 0 ? Math.round((fulfilled / total) * 100) : 0;
  const inProgressRate = total > 0 ? Math.round((inProgress / total) * 100) : 0;

  // Dane dla wykresu kołowego Recharts (Donut)
  const chartData = [
    {
      name: "Zrealizowane",
      value: fulfilled,
      fill: DONUT_COLORS.fulfilled,
      percentStr: total > 0 ? `${Math.round((fulfilled / total) * 100)}%` : "0%",
    },
    {
      name: "W trakcie (Sejm)",
      value: inProgress,
      fill: DONUT_COLORS.in_progress,
      percentStr: total > 0 ? `${Math.round((inProgress / total) * 100)}%` : "0%",
    },
    {
      name: "Złamane / Odrzucone",
      value: broken,
      fill: DONUT_COLORS.broken,
      percentStr: total > 0 ? `${Math.round((broken / total) * 100)}%` : "0%",
    },
  ];

  // Jeśli są obietnice o innym/nowym statusie, dodajemy je do wykresu
  if (other > 0) {
    chartData.push({
      name: "Nierozpoczęte / Nowe",
      value: other,
      fill: DONUT_COLORS.other,
      percentStr: total > 0 ? `${Math.round((other / total) * 100)}%` : "0%",
    });
  }

  return (
    <div className="relative overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900/90 via-slate-900 to-indigo-950/30 p-6 sm:p-8 shadow-2xl space-y-6">
      {/* Nagłówek Panelu */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800/80 pb-4">
        <div>
          <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wider text-indigo-400">
            <span className="inline-flex items-center gap-1.5">
              <Activity className="h-4 w-4" />
              Big Picture • Raport Rządowy
            </span>
            <span className="rounded border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold text-amber-300">
              SYMULACJA DEMO • SZTUCZNE DANE
            </span>
          </div>
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white mt-1">
            Overall Government Score: Efektywność Koalicji
          </h2>
          <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
            Wskaźniki pokazowe (dane syntetyczne obrazujące docelowy raport po automatycznym wyliczeniu przez potok ETL Apache Airflow).
          </p>
        </div>

        {/* Globalny Wskaźnik Sukcesu */}
        <div className="flex items-center gap-3 rounded-xl border border-emerald-500/30 bg-emerald-950/20 px-4 py-2 text-emerald-300">
          <Award className="h-6 w-6 text-emerald-400 shrink-0" />
          <div>
            <span className="block text-[10px] uppercase font-bold tracking-wider text-emerald-400/80">
              Stopień Realizacji
            </span>
            <span className="text-lg sm:text-xl font-black text-emerald-200">
              {deliveryRate}%
            </span>
          </div>
        </div>
      </div>

      {/* Siatka: Lewa kolumna (Wykres Donut) + Prawa kolumna (Kafle numeryczne) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        {/* Kolumna Wykresu Donut (Recharts) */}
        <div className="lg:col-span-5 flex flex-col items-center justify-center relative min-w-0">
          <div className="w-full h-64 sm:h-72 relative min-w-0 min-h-[260px]">
            {mounted ? (
              <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={250} debounce={50}>
                <PieChart>
                  <Pie
                    data={chartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={65}
                    outerRadius={95}
                    paddingAngle={4}
                    dataKey="value"
                    stroke="none"
                  >
                    {chartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                  <Legend
                    verticalAlign="bottom"
                    height={36}
                    iconType="circle"
                    iconSize={8}
                    formatter={(value) => (
                      <span className="text-xs text-slate-300 font-medium mr-2">
                        {value}
                      </span>
                    )}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full w-full flex items-center justify-center">
                <div className="h-48 w-48 rounded-full border-4 border-slate-800 border-t-emerald-500 animate-pulse opacity-40" />
              </div>
            )}

            {/* Liczba na środku Donuta */}
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none pb-8">
              <span className="text-3xl sm:text-4xl font-black text-white tracking-tight">
                {total}
              </span>
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                Deklaracji
              </span>
            </div>
          </div>
        </div>

        {/* Kolumna Kafli Numerycznych (Stat Cards) */}
        <div className="lg:col-span-7 grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Karta 1: Zrealizowane Obietnice */}
          <Card className="border-slate-800/80 bg-slate-950/50 hover:border-emerald-500/40 transition-colors shadow-md">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                W Pełni Zrealizowane
              </CardTitle>
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl sm:text-3xl font-bold text-emerald-400">
                {fulfilled}
              </div>
              <CardDescription className="text-xs text-slate-400 mt-1">
                {deliveryRate}% wszystkich złożonych deklaracji
              </CardDescription>
            </CardContent>
          </Card>

          {/* Karta 2: Procedowane w Parlamencie */}
          <Card className="border-slate-800/80 bg-slate-950/50 hover:border-amber-500/40 transition-colors shadow-md">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                W Trakcie Prac (Sejm)
              </CardTitle>
              <TrendingUp className="h-4 w-4 text-amber-400" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl sm:text-3xl font-bold text-amber-400">
                {inProgress}
              </div>
              <CardDescription className="text-xs text-slate-400 mt-1">
                {inProgressRate}% w komisjach lub po I/II czytaniu
              </CardDescription>
            </CardContent>
          </Card>

          {/* Karta 3: Średni Czas Dowiezienia Ustawy */}
          <Card className="border-slate-800/80 bg-slate-950/50 hover:border-sky-500/40 transition-colors shadow-md">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Średni Czas Dowiezienia
              </CardTitle>
              <Clock className="h-4 w-4 text-sky-400" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl sm:text-3xl font-bold text-sky-400">
                {data?.average_delivery_days !== null && data?.average_delivery_days !== undefined
                  ? `${data.average_delivery_days} dni`
                  : "184 dni"}
              </div>
              <CardDescription className="text-xs text-slate-400 mt-1">
                Od wniesienia projektu do podpisu Prezydenta
              </CardDescription>
            </CardContent>
          </Card>

          {/* Karta 4: Obietnice Złamane lub Niezgodne */}
          <Card className="border-slate-800/80 bg-slate-950/50 hover:border-rose-500/40 transition-colors shadow-md">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Złamane / Sprzeczne
              </CardTitle>
              <XCircle className="h-4 w-4 text-rose-400" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl sm:text-3xl font-bold text-rose-400">
                {broken}
              </div>
              <CardDescription className="text-xs text-slate-400 mt-1">
                Projekty odrzucone lub niezgodne z deklaracją
              </CardDescription>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

export default GovernmentScoreDashboard;
