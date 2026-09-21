"use client";

import React, { useState, useEffect, useTransition } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useDebounce } from "use-debounce";
import {
  Search,
  X,
  Filter,
  SlidersHorizontal,
  RotateCcw,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

export interface FilterBarProps {
  onFiltersChange?: (filters: {
    q: string;
    party: string;
    status: string;
    category: string;
  }) => void;
  className?: string;
}

const PARTIES = [
  { value: "ALL", label: "Wszystkie komitety" },
  { value: "KO", label: "Koalicja Obywatelska (KO)" },
  { value: "TD", label: "Trzecia Droga (TD)" },
  { value: "LEWICA", label: "Nowa Lewica" },
  { value: "PIS", label: "Prawo i Sprawiedliwość (PiS)" },
  { value: "KONFEDERACJA", label: "Konfederacja" },
];

const STATUSES = [
  { value: "ALL", label: "Wszystkie statusy" },
  { value: "W_PELNI", label: "W pełni zgodna (LLM)" },
  { value: "CZESCIOWO", label: "Częściowo zgodna (LLM)" },
  { value: "SPRZECZNA", label: "Sprzeczna z deklaracją (LLM)" },
  { value: "BRAK_POWIAZANIA", label: "Brak powiązania z ustawą" },
  { value: "FULFILLED", label: "Zrealizowana (Status)" },
  { value: "IN_PROGRESS", label: "W trakcie prac w Sejmie" },
  { value: "BROKEN", label: "Złamana / Odrzucona" },
];

const CATEGORIES = [
  { value: "ALL", label: "Wszystkie kategorie" },
  { value: "Podatki", label: "Podatki i Finanse" },
  { value: "Gospodarka", label: "Gospodarka i Przedsiębiorczość" },
  { value: "Zdrowie", label: "Ochrona Zdrowia" },
  { value: "Edukacja", label: "Edukacja i Nauka" },
  { value: "Mieszkalnictwo", label: "Mieszkalnictwo i Budownictwo" },
  { value: "Sprawiedliwość", label: "Prawo i Wymiar Sprawiedliwości" },
];

/**
 * Komponent paska wyszukiwania i filtrowania zintegrowany ze stanem URL (query params)
 * oraz debouncingiem zapobiegającym nadmiernym zapytaniom do API.
 */
export function FilterBar({ onFiltersChange, className = "" }: FilterBarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [, startTransition] = useTransition();

  // Inicjalizacja stanu z parametrów URL
  const initialQ = searchParams?.get("q") || "";
  const initialParty = searchParams?.get("party") || "ALL";
  const initialStatus = searchParams?.get("status") || "ALL";
  const initialCategory = searchParams?.get("category") || "ALL";

  const [searchTerm, setSearchTerm] = useState(initialQ);
  const [debouncedSearch] = useDebounce(searchTerm, 500);

  const [selectedParty, setSelectedParty] = useState(initialParty);
  const [selectedStatus, setSelectedStatus] = useState(initialStatus);
  const [selectedCategory, setSelectedCategory] = useState(initialCategory);

  // Stan zwijania filtrów na małych ekranach (smartfony)
  const [isMobileExpanded, setIsMobileExpanded] = useState(false);

  // Synchronizacja z zewnętrznymi zmianami w URL (np. przycisk Wstecz)
  useEffect(() => {
    const qParam = searchParams?.get("q") || "";
    const partyParam = searchParams?.get("party") || "ALL";
    const statusParam = searchParams?.get("status") || "ALL";
    const categoryParam = searchParams?.get("category") || "ALL";

    setSearchTerm((prev) => (prev !== qParam ? qParam : prev));
    setSelectedParty((prev) => (prev !== partyParam ? partyParam : prev));
    setSelectedStatus((prev) => (prev !== statusParam ? statusParam : prev));
    setSelectedCategory((prev) => (prev !== categoryParam ? categoryParam : prev));
  }, [searchParams]);

  // Aktualizacja adresu URL oraz wywołanie callbacku po zmianie filtrów lub upływie debouce
  useEffect(() => {
    const params = new URLSearchParams();

    if (debouncedSearch.trim()) params.set("q", debouncedSearch.trim());
    if (selectedParty && selectedParty !== "ALL") params.set("party", selectedParty);
    if (selectedStatus && selectedStatus !== "ALL") params.set("status", selectedStatus);
    if (selectedCategory && selectedCategory !== "ALL") params.set("category", selectedCategory);

    const newQueryString = params.toString();
    const currentQueryString = searchParams?.toString() || "";

    if (newQueryString !== currentQueryString) {
      const targetUrl = newQueryString ? `${pathname}?${newQueryString}` : pathname;
      if (typeof window !== "undefined") {
        window.history.replaceState(null, "", targetUrl);
      }
    }

    onFiltersChange?.({
      q: debouncedSearch.trim(),
      party: selectedParty,
      status: selectedStatus,
      category: selectedCategory,
    });
  }, [debouncedSearch, selectedParty, selectedStatus, selectedCategory, pathname, searchParams, onFiltersChange]);

  const hasActiveFilters = Boolean(
    searchTerm.trim() ||
      (selectedParty && selectedParty !== "ALL") ||
      (selectedStatus && selectedStatus !== "ALL") ||
      (selectedCategory && selectedCategory !== "ALL")
  );

  const handleResetFilters = () => {
    setSearchTerm("");
    setSelectedParty("ALL");
    setSelectedStatus("ALL");
    setSelectedCategory("ALL");
  };

  return (
    <div
      className={`sticky top-14 z-20 rounded-xl border border-slate-800/90 bg-slate-950/85 p-3.5 sm:p-4 shadow-xl backdrop-blur-md transition-all ${className}`}
    >
      <div className="flex flex-col gap-3">
        {/* Górny wiersz: Pole wyszukiwania z lupką + Przycisk mobilny do zwijania/rozwijania */}
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <Input
              type="text"
              placeholder="Wyszukaj obietnicę po słowie kluczowym (np. kwota wolna, ZUS)..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 pr-8"
              aria-label="Wyszukiwarka deklaracji wyborczych"
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm("")}
                className="absolute right-2.5 top-2.5 text-slate-400 hover:text-white transition"
                title="Wyczyść pole wyszukiwania"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* Przełącznik zwijania filtrów na smartfonach */}
          <button
            type="button"
            onClick={() => setIsMobileExpanded(!isMobileExpanded)}
            className={`sm:hidden flex items-center justify-center h-10 px-3 rounded-lg border text-xs font-semibold transition ${
              isMobileExpanded || hasActiveFilters
                ? "border-indigo-500 bg-indigo-600/20 text-indigo-300"
                : "border-slate-800 bg-slate-900 text-slate-300"
            }`}
            aria-label="Rozwiń dodatkowe filtry"
          >
            <SlidersHorizontal className="h-4 w-4" />
          </button>
        </div>

        {/* Dolny wiersz: Dropdowny filtrów (Partia, Status, Kategoria) */}
        <div
          className={`flex-col sm:flex sm:flex-row items-center gap-3 ${
            isMobileExpanded ? "flex" : "hidden sm:flex"
          }`}
        >
          {/* Dropdown 1: Partia polityczna */}
          <div className="w-full sm:w-1/3">
            <Select
              value={selectedParty}
              onChange={(e) => setSelectedParty(e.target.value)}
              aria-label="Filtruj według komitetu lub partii"
            >
              {PARTIES.map((p) => (
                <option key={p.value} value={p.value} className="bg-slate-900 text-white">
                  {p.label}
                </option>
              ))}
            </Select>
          </div>

          {/* Dropdown 2: Status realizacji / zgodności LLM */}
          <div className="w-full sm:w-1/3">
            <Select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              aria-label="Filtruj według statusu"
            >
              {STATUSES.map((s) => (
                <option key={s.value} value={s.value} className="bg-slate-900 text-white">
                  {s.label}
                </option>
              ))}
            </Select>
          </div>

          {/* Dropdown 3: Kategoria */}
          <div className="w-full sm:w-1/3">
            <Select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              aria-label="Filtruj według kategorii tematycznej"
            >
              {CATEGORIES.map((c) => (
                <option key={c.value} value={c.value} className="bg-slate-900 text-white">
                  {c.label}
                </option>
              ))}
            </Select>
          </div>

          {/* Przycisk resetowania filtrów */}
          {hasActiveFilters && (
            <button
              onClick={handleResetFilters}
              className="flex w-full sm:w-auto items-center justify-center gap-1.5 h-10 px-3 rounded-lg border border-slate-700 bg-slate-900 text-xs font-medium text-slate-300 hover:bg-slate-800 hover:text-white transition shrink-0"
              title="Wyczyść wszystkie nałożone filtry"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span>Reset</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default FilterBar;
