"use client";

import React, { useState } from "react";
import { Bell, BellRing, BellOff, Check, Loader2 } from "lucide-react";
import { usePushSubscriptions } from "@/hooks/usePushSubscriptions";

export interface SubscribeButtonProps {
  targetType: "PROMISE" | "MP" | "CATEGORY";
  targetId: string;
  label?: string;
  className?: string;
  size?: "sm" | "default";
}

export function SubscribeButton({
  targetType,
  targetId,
  label = "Śledź zmianę",
  className = "",
  size = "sm",
}: SubscribeButtonProps) {
  const { isSubscribed, subscribe, unsubscribe, isDenied, isLoading, error } =
    usePushSubscriptions();

  const [hovered, setHovered] = useState(false);
  const subscribed = isSubscribed(targetType, targetId);

  const handleClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();

    if (isDenied) return;

    if (subscribed) {
      await unsubscribe(targetType, targetId);
    } else {
      await subscribe(targetType, targetId);
    }
  };

  const sizeClasses =
    size === "sm"
      ? "px-2.5 py-1 text-xs gap-1.5"
      : "px-4 py-2 text-sm gap-2";

  if (isDenied) {
    return (
      <div className="relative inline-block group" onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          disabled
          aria-label="Powiadomienia zablokowane w przeglądarce"
          className={`inline-flex items-center rounded-lg border border-slate-700/60 bg-slate-800/40 font-medium text-slate-400 cursor-not-allowed transition-all ${sizeClasses} ${className}`}
        >
          <BellOff className="h-3.5 w-3.5 text-rose-400" />
          <span>Powiadomienia zablokowane</span>
        </button>
        {/* Tooltip fallback dla zablokowanych powiadomień */}
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-50 w-64 p-2 bg-slate-950 border border-slate-700 rounded-md text-[11px] text-slate-300 shadow-xl text-center pointer-events-none">
          Powiadomienia są zablokowane w Twojej przeglądarce. Kliknij ikonę kłódki przy adresie strony, aby zezwolić na powiadomienia.
        </div>
      </div>
    );
  }

  if (subscribed) {
    return (
      <button
        type="button"
        onClick={handleClick}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        disabled={isLoading}
        aria-label="Anuluj subskrypcję powiadomień"
        className={`inline-flex items-center rounded-lg border font-semibold transition-all duration-200 ${
          hovered
            ? "border-rose-500/40 bg-rose-950/40 text-rose-300"
            : "border-emerald-500/40 bg-emerald-950/40 text-emerald-300 shadow-sm shadow-emerald-500/10"
        } ${sizeClasses} ${className}`}
      >
        {isLoading ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-emerald-400" />
        ) : hovered ? (
          <BellOff className="h-3.5 w-3.5 text-rose-400" />
        ) : (
          <Check className="h-3.5 w-3.5 text-emerald-400" />
        )}
        <span>{hovered ? "Przestań śledzić" : "Śledzisz"}</span>
      </button>
    );
  }

  return (
    <div className="inline-block relative">
      <button
        type="button"
        onClick={handleClick}
        disabled={isLoading}
        aria-label="Włącz powiadomienia Push dla tego elementu"
        className={`inline-flex items-center rounded-lg border border-slate-700 bg-slate-800/80 font-medium text-slate-200 hover:border-indigo-500/60 hover:bg-indigo-950/40 hover:text-indigo-200 active:scale-95 transition-all duration-200 shadow-sm ${sizeClasses} ${className}`}
      >
        {isLoading ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-400" />
        ) : (
          <Bell className="h-3.5 w-3.5 text-indigo-400" />
        )}
        <span>{label}</span>
      </button>
      {error && (
        <p className="absolute top-full left-0 mt-1 text-[10px] text-rose-400 whitespace-nowrap z-40 bg-slate-950/90 px-1.5 py-0.5 rounded border border-rose-800">
          {error}
        </p>
      )}
    </div>
  );
}
