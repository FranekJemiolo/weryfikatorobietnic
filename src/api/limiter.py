"""Moduł ograniczania częstotliwości zapytań (Rate Limiting) dla FastAPI.

Chroni publiczne endpointy API przed przeciążeniem, scrapingiem DoS oraz
wyczerpaniem puli połączeń bazy danych (Connection Pool Exhaustion).
Implementuje algorytm Sliding Window Counter per adres IP klienta.
"""

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status


class SlidingWindowRateLimiter:
    """Ogranicznik zapytań oparty na ruchomym oknie czasowym (Sliding Window Counter)."""

    def __init__(self, times: int = 60, seconds: int = 60) -> None:
        """Inicjalizuje limiter.

        Args:
            times: Maksymalna dozwolona liczba zapytań w danym oknie.
            seconds: Długość okna czasowego w sekundach.
        """
        self.times = times
        self.seconds = seconds
        # Słownik: client_ip -> lista timestampów (float)
        self._history: dict[str, list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        """Wyciąga prawdziwy adres IP klienta, uwzględniając nagłówki proxy (np. X-Forwarded-For)."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "127.0.0.1"

    def is_rate_limited(self, client_ip: str) -> tuple[bool, int]:
        """Sprawdza, czy klient przekroczył limit zapytań.

        Returns:
            Krotka (czy_zablokowany, sekundy_do_zwolnienia_blokady).
        """
        now = time.monotonic()
        cutoff = now - self.seconds

        # Czyszczenie wpisów starszych niż okno czasowe
        timestamps = self._history[client_ip]
        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)

        if len(timestamps) >= self.times:
            oldest_in_window = timestamps[0]
            retry_after = max(1, int(oldest_in_window + self.seconds - now))
            return True, retry_after

        # Rejestracja nowego zapytania
        timestamps.append(now)
        return False, 0

    def reset(self) -> None:
        """Czyści historię zapytań (przydatne m.in. w testach jednostkowych)."""
        self._history.clear()

    async def __call__(self, request: Request) -> None:
        """Callable do użycia jako Depends() w routerach FastAPI."""
        client_ip = self._get_client_ip(request)
        limited, retry_after = self.is_rate_limited(client_ip)

        if limited:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Zbyt wiele zapytań (Rate Limit Exceeded). Spróbuj ponownie za {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )


# Domyślny ogranicznik dla intensywnych zapytań wyszukiwarki (30 zapytań / minutę)
search_rate_limiter = SlidingWindowRateLimiter(times=30, seconds=60)

# Domyślny ogranicznik dla endpointów ewaluacji i szczegółów (60 zapytań / minutę)
evaluation_rate_limiter = SlidingWindowRateLimiter(times=60, seconds=60)
