"use client";

import { useState, useEffect, useCallback } from "react";
import { api, type PushSubscriptionData } from "@/lib/api";

const SUBSCRIPTION_STORAGE_KEY = "weryfikator_push_subscriptions_v1";

/**
 * Konwertuje klucz publiczny base64 URL-safe do formatu Uint8Array wymaganego przez PushManager.
 */
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export function usePushSubscriptions() {
  const [isSupported, setIsSupported] = useState<boolean>(false);
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">("default");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [subscribedKeys, setSubscribedKeys] = useState<Set<string>>(new Set());

  // Inicjalizacja stanu przeglądarki i pamięci podręcznej subskrypcji
  useEffect(() => {
    if (typeof window === "undefined") return;

    const supported =
      "serviceWorker" in navigator &&
      "PushManager" in window &&
      "Notification" in window;

    setIsSupported(supported);
    if (supported) {
      setPermission(Notification.permission);
    } else {
      setPermission("unsupported");
    }

    try {
      const stored = localStorage.getItem(SUBSCRIPTION_STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as string[];
        setSubscribedKeys(new Set(parsed));
      }
    } catch {
      // Ignorowanie błędów odczytu z localStorage
    }
  }, []);

  const saveSubscribedKeys = useCallback((newSet: Set<string>) => {
    setSubscribedKeys(newSet);
    try {
      localStorage.setItem(SUBSCRIPTION_STORAGE_KEY, JSON.stringify(Array.from(newSet)));
    } catch {
      // Ignorowanie błędów zapisu do localStorage
    }
  }, []);

  const isSubscribed = useCallback(
    (targetType: "PROMISE" | "MP" | "CATEGORY", targetId: string): boolean => {
      const key = `${targetType}:${targetId}`;
      return subscribedKeys.has(key);
    },
    [subscribedKeys]
  );

  const subscribe = useCallback(
    async (
      targetType: "PROMISE" | "MP" | "CATEGORY",
      targetId: string
    ): Promise<boolean> => {
      if (!isSupported) {
        setError("Twoja przeglądarka nie obsługuje powiadomień Push.");
        return false;
      }

      setIsLoading(true);
      setError(null);

      try {
        // 1. Sprawdzenie / zapytanie o uprawnienia użytkownika
        let currentPerm = Notification.permission;
        if (currentPerm === "default") {
          currentPerm = await Notification.requestPermission();
          setPermission(currentPerm);
        }

        if (currentPerm !== "granted") {
          setError(
            currentPerm === "denied"
              ? "Powiadomienia zostały zablokowane w przeglądarce. Odblokuj je w ustawieniach witryny."
              : "Nie wyrażono zgody na otrzymywanie powiadomień."
          );
          setIsLoading(false);
          return false;
        }

        // 2. Rejestracja lub pobranie gotowego Service Workera
        let reg = await navigator.serviceWorker.getRegistration();
        if (!reg) {
          reg = await navigator.serviceWorker.register("/sw.js");
        }
        await navigator.serviceWorker.ready;

        // 3. Pobranie klucza VAPID z API
        const vapidPublicKey = await api.getVapidPublicKey();
        const applicationServerKey = urlBase64ToUint8Array(vapidPublicKey);

        // 4. Subskrypcja w PushManagerze przeglądarki
        let pushSub = await reg.pushManager.getSubscription();
        if (!pushSub) {
          pushSub = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: applicationServerKey.buffer as ArrayBuffer,
          });
        }

        const subJson = pushSub.toJSON();
        if (!subJson.endpoint || !subJson.keys?.p256dh || !subJson.keys?.auth) {
          throw new Error("Przeglądarka nie zwróciła wymaganych kluczy kryptograficznych.");
        }

        const subscriptionPayload: PushSubscriptionData = {
          endpoint: subJson.endpoint,
          keys: {
            p256dh: subJson.keys.p256dh,
            auth: subJson.keys.auth,
          },
        };

        // 5. Zapis w bazie FastAPI
        await api.subscribePush({
          subscription: subscriptionPayload,
          target_type: targetType,
          target_id: targetId,
        });

        const newSet = new Set(subscribedKeys);
        newSet.add(`${targetType}:${targetId}`);
        saveSubscribedKeys(newSet);

        setIsLoading(false);
        return true;
      } catch (err) {
        const message = err instanceof Error ? err.message : "Wystąpił błąd podczas subskrybowania.";
        setError(message);
        setIsLoading(false);
        return false;
      }
    },
    [isSupported, subscribedKeys, saveSubscribedKeys]
  );

  const unsubscribe = useCallback(
    async (
      targetType: "PROMISE" | "MP" | "CATEGORY",
      targetId: string
    ): Promise<boolean> => {
      setIsLoading(true);
      setError(null);

      try {
        if ("serviceWorker" in navigator) {
          const reg = await navigator.serviceWorker.getRegistration();
          if (reg) {
            const pushSub = await reg.pushManager.getSubscription();
            if (pushSub?.endpoint) {
              await api.unsubscribePush({
                endpoint: pushSub.endpoint,
                target_type: targetType,
                target_id: targetId,
              });
            }
          }
        }

        const newSet = new Set(subscribedKeys);
        newSet.delete(`${targetType}:${targetId}`);
        saveSubscribedKeys(newSet);

        setIsLoading(false);
        return true;
      } catch (err) {
        const message = err instanceof Error ? err.message : "Wystąpił błąd podczas anulowania subskrypcji.";
        setError(message);
        setIsLoading(false);
        return false;
      }
    },
    [subscribedKeys, saveSubscribedKeys]
  );

  return {
    isSupported,
    permission,
    isDenied: permission === "denied",
    isLoading,
    error,
    isSubscribed,
    subscribe,
    unsubscribe,
  };
}
