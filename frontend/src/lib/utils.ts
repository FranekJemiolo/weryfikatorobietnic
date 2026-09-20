import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Łączy klasy Tailwind CSS, eliminując konflikty i puste wartości.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * Formatuje kwotę PLN na czytelny format walutowy (np. "48 000 000 000 zł" lub "48 mld zł").
 */
export function formatPLN(amount?: number | null): string {
  if (amount === undefined || amount === null) {
    return "Nieoszacowano w OSR";
  }
  if (Math.abs(amount) >= 1_000_000_000) {
    return `${(amount / 1_000_000_000).toLocaleString("pl-PL", { maximumFractionDigits: 1 })} mld zł`;
  }
  if (Math.abs(amount) >= 1_000_000) {
    return `${(amount / 1_000_000).toLocaleString("pl-PL", { maximumFractionDigits: 1 })} mln zł`;
  }
  return `${amount.toLocaleString("pl-PL")} zł`;
}
