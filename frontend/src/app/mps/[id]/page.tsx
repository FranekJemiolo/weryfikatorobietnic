import React from "react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, User, Shield, CheckCircle2, XCircle, BarChart3 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { MPActivityHeatmap } from "@/components/MPActivityHeatmap";
import type { MPProfile } from "@/lib/api";

interface PageProps {
  params: {
    id: string;
  };
}

/**
 * Pobiera dane profilu posła bezpośrednio z API po stronie serwera.
 */
async function getMP(id: string): Promise<MPProfile | null> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  try {
    const res = await fetch(`${baseUrl}/api/v1/mps/${encodeURIComponent(id)}`, {
      next: { revalidate: 120 }, // Odświeżanie danych profilu co 2 minuty
    });
    if (!res.ok) {
      if (res.status === 404) return null;
      throw new Error(`HTTP ${res.status}`);
    }
    return res.json();
  } catch (error) {
    console.error(`Błąd podczas pobierania danych posła ID ${id}:`, error);
    return null;
  }
}

/**
 * Dynamiczne generowanie metadanych SEO dla posła.
 */
export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const mp = await getMP(params.id);
  if (!mp) {
    return {
      title: "Poseł nie został znaleziony | Weryfikator Obietnic",
    };
  }

  const fullName = `${mp.first_name} ${mp.last_name}`;
  return {
    title: `${fullName} (${mp.club}) – Profil i Frekwencja w Sejmie | Weryfikator Obietnic`,
    description: `Zobacz profil głosowań, frekwencję oraz spójność klubową posła ${fullName} (${mp.club}) w Sejmie RP X Kadencji.`,
  };
}

/**
 * Asynchroniczny React Server Component dla profilu posła.
 */
export default async function MPProfilePage({ params }: PageProps) {
  const mp = await getMP(params.id);

  if (!mp) {
    return (
      <div className="mx-auto max-w-3xl space-y-6 py-12 text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-slate-900 border border-slate-800 text-slate-500">
          <User className="h-8 w-8" />
        </div>
        <h2 className="text-2xl font-bold text-white">Nie znaleziono posła</h2>
        <p className="text-sm text-slate-400 max-w-md mx-auto">
          Poseł o identyfikatorze <strong>#{params.id}</strong> nie figuruje w rejestrze X Kadencji Sejmu RP lub baza danych oczekuje na zsynchronizowanie.
        </p>
        <div>
          <Link
            href="/"
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-xs sm:text-sm font-medium text-white shadow-lg hover:bg-indigo-500 transition"
          >
            <ArrowLeft className="h-4 w-4" />
            Wróć do strony głównej
          </Link>
        </div>
      </div>
    );
  }

  const fullName = `${mp.first_name} ${mp.last_name}`;
  const initials = `${mp.first_name.charAt(0)}${mp.last_name.charAt(0)}`;

  return (
    <div className="mx-auto max-w-5xl space-y-8 pb-16">
      {/* Przycisk powrotu */}
      <div>
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-xs sm:text-sm text-slate-400 hover:text-slate-100 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Powrót do katalogu obietnic
        </Link>
      </div>

      {/* Karta Profilowa Posła (Nagłówek) */}
      <Card className="border-slate-800 bg-gradient-to-br from-slate-900/90 via-slate-900/80 to-slate-950 p-6 sm:p-8 shadow-2xl backdrop-blur-md">
        <div className="flex flex-col sm:flex-row sm:items-center gap-6">
          {/* Awatar z gradientem i inicjałami */}
          <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-tr from-sky-500 to-indigo-600 text-2xl font-black text-white shadow-xl shadow-indigo-500/20 border border-indigo-400/30">
            {initials}
          </div>

          <div className="space-y-2 flex-1">
            <div className="flex flex-wrap items-center gap-2.5">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                {fullName}
              </h1>
              <Badge variant="secondary" className="font-semibold text-xs bg-slate-800 text-slate-200">
                Poseł X Kadencji
              </Badge>
            </div>

            <div className="flex flex-wrap items-center gap-3 text-xs sm:text-sm text-slate-400">
              <span className="flex items-center gap-1.5 font-medium text-slate-200">
                <Shield className="h-4 w-4 text-indigo-400" />
                Klub: <strong className="text-sky-300">{mp.club}</strong>
              </span>
              <span>•</span>
              <span className="flex items-center gap-1.5">
                {mp.active ? (
                  <>
                    <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                    <span className="text-emerald-400 font-medium">Mandat aktywny</span>
                  </>
                ) : (
                  <>
                    <XCircle className="h-4 w-4 text-rose-400" />
                    <span className="text-rose-400 font-medium">Mandat wygaszony</span>
                  </>
                )}
              </span>
            </div>
          </div>
        </div>
      </Card>

      {/* Moduł Aktywności i Heatmapa Głosowań */}
      <Card className="border-slate-800 bg-slate-900/70 p-6 sm:p-8 shadow-xl backdrop-blur-sm">
        <CardHeader className="p-0 pb-6">
          <div className="flex items-center gap-2.5">
            <BarChart3 className="h-5 w-5 text-sky-400" />
            <CardTitle className="text-lg sm:text-xl font-bold text-white">
              Tablica Aktywności i Lojalności Klubowej
            </CardTitle>
          </div>
          <p className="text-xs sm:text-sm text-slate-400 pt-1">
            Wizualizacja każdego dnia posiedzeń Sejmu RP, na którym poseł {fullName} brał udział w głosowaniach.
          </p>
        </CardHeader>

        <CardContent className="p-0">
          <MPActivityHeatmap
            mpId={params.id}
            mpName={fullName}
            clubName={mp.club}
          />
        </CardContent>
      </Card>
    </div>
  );
}
