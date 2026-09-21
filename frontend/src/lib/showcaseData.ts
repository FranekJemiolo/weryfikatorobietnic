import type {
  PromiseListItem,
  PromiseEvaluationDetail,
  AnalyticsSummary,
  TimelineEvent,
} from "./api";

export const SHOWCASE_ANALYTICS: AnalyticsSummary = {
  total_promises: 120,
  fulfilled_count: 34,
  in_progress_count: 58,
  broken_count: 18,
  average_delivery_days: 142,
};

export const SHOWCASE_PROMISES: PromiseListItem[] = [
  {
    id: "KO-100K-042",
    party: "KO",
    title: "Podniesienie kwoty wolnej od podatku PIT do 60 000 zł",
    category: "Podatki",
    status: "IN_PROGRESS",
    latest_alignment_status: "CZESCIOWO",
    confidence_score: 0.89,
    estimated_budget_impact_pln: 35000000000,
    created_at: "2023-11-15T10:00:00Z",
  },
  {
    id: "TD-GWAR-015",
    party: "TD",
    title: "Wakacje składkowe – 1 miesiąc wolny od ZUS dla mikrofirm",
    category: "Gospodarka",
    status: "FULFILLED",
    latest_alignment_status: "W_PELNI",
    confidence_score: 0.96,
    estimated_budget_impact_pln: 1640000000,
    created_at: "2023-11-20T12:00:00Z",
  },
  {
    id: "LEW-SPO-008",
    party: "LEWICA",
    title: "Renta wdowia – wsparcie finansowe dla owdowiałych seniorów",
    category: "Sprawiedliwość",
    status: "FULFILLED",
    latest_alignment_status: "W_PELNI",
    confidence_score: 0.94,
    estimated_budget_impact_pln: 4200000000,
    created_at: "2023-12-01T09:30:00Z",
  },
  {
    id: "KO-100K-001",
    party: "KO",
    title: "Program 'Aktywny Rodzic' (tzw. Babciowe) do 1500 zł miesięcznie",
    category: "Gospodarka",
    status: "FULFILLED",
    latest_alignment_status: "W_PELNI",
    confidence_score: 0.97,
    estimated_budget_impact_pln: 8900000000,
    created_at: "2023-11-10T14:15:00Z",
  },
  {
    id: "KO-100K-023",
    party: "KO",
    title: "Kredyt mieszkaniowy 0% #naStart dla młodych",
    category: "Mieszkalnictwo",
    status: "IN_PROGRESS",
    latest_alignment_status: "SPRZECZNA",
    confidence_score: 0.84,
    estimated_budget_impact_pln: 11500000000,
    created_at: "2023-11-25T11:00:00Z",
  },
  {
    id: "KO-100K-005",
    party: "KO",
    title: "30% podwyżki wynagrodzeń dla nauczycieli od 2024 r.",
    category: "Edukacja",
    status: "FULFILLED",
    latest_alignment_status: "W_PELNI",
    confidence_score: 0.98,
    estimated_budget_impact_pln: 12800000000,
    created_at: "2023-11-05T08:00:00Z",
  },
  {
    id: "TD-GWAR-003",
    party: "TD",
    title: "Odpartyjnienie i transparentne konkursy w Spółkach Skarbu Państwa",
    category: "Sprawiedliwość",
    status: "IN_PROGRESS",
    latest_alignment_status: "CZESCIOWO",
    confidence_score: 0.76,
    estimated_budget_impact_pln: 0,
    created_at: "2023-12-12T16:45:00Z",
  },
  {
    id: "LEW-ZDR-003",
    party: "LEWICA",
    title: "Dostępność antykoncepcji awaryjnej ('dzień po') od 15. roku życia",
    category: "Zdrowie",
    status: "FULFILLED",
    latest_alignment_status: "CZESCIOWO",
    confidence_score: 0.88,
    estimated_budget_impact_pln: 50000000,
    created_at: "2024-01-10T13:00:00Z",
  },
  {
    id: "KO-100K-088",
    party: "KO",
    title: "Likwidacja Funduszu Kościelnego i zastąpienie odpisem podatkowym",
    category: "Sprawiedliwość",
    status: "IN_PROGRESS",
    latest_alignment_status: "CZESCIOWO",
    confidence_score: 0.72,
    estimated_budget_impact_pln: 216000000,
    created_at: "2024-01-20T10:30:00Z",
  },
  {
    id: "KONF-POD-002",
    party: "KONFEDERACJA",
    title: "Liniowy PIT 12% oraz podwojenie kwoty wolnej od podatku",
    category: "Podatki",
    status: "BROKEN",
    latest_alignment_status: "BRAK_POWIAZANIA",
    confidence_score: 0.65,
    estimated_budget_impact_pln: 45000000000,
    created_at: "2023-11-01T09:00:00Z",
  },
  {
    id: "PIS-PROG-004",
    party: "PIS",
    title: "Bezpłatne państwowe autostrady dla samochodów osobowych",
    category: "Gospodarka",
    status: "FULFILLED",
    latest_alignment_status: "W_PELNI",
    confidence_score: 0.95,
    estimated_budget_impact_pln: 850000000,
    created_at: "2023-09-01T12:00:00Z",
  },
  {
    id: "LEW-PRA-001",
    party: "LEWICA",
    title: "Rządowa ustawa o rejestrowanych związkach partnerskich",
    category: "Sprawiedliwość",
    status: "IN_PROGRESS",
    latest_alignment_status: "CZESCIOWO",
    confidence_score: 0.81,
    estimated_budget_impact_pln: 15000000,
    created_at: "2024-02-01T15:20:00Z",
  },
];

export const SHOWCASE_PROMISE_DETAILS: Record<string, PromiseEvaluationDetail> = {
  "KO-100K-042": {
    promise_id: "KO-100K-042",
    title: "Podniesienie kwoty wolnej od podatku PIT do 60 000 zł",
    full_text:
      "Podniesiemy kwotę wolną od podatku z 30 tys. zł do 60 tys. zł dla wszystkich podatników rozliczających się według skali podatkowej (PIT). Osoby zarabiające do 6000 zł brutto nie zapłacą ani grosza podatku dochodowego.",
    party: "KO",
    category: "Podatki",
    status: "IN_PROGRESS",
    alignment_status: "CZESCIOWO",
    confidence_score: 0.89,
    bill_id: "sejm-x-341",
    bill_title: "Rządowy projekt ustawy o zmianie ustawy o podatku dochodowym od osób fizycznych",
    bill_print_num: "341",
    estimated_budget_impact_pln: 35000000000,
    divergence_details:
      "Termin wejścia w życie odroczony na lata 2025/2026 ze względu na unijną procedurę nadmiernego deficytu (EDP); Trwają prace analityczne w Ministerstwie Finansów nad etapowym wdrażaniem ulgi; Pierwotna obietnica zakładała realizację w pierwszych 100 dniach rządu.",
    justification:
      "Model ocenił stopień realizacji jako CZĘŚCIOWY. Projekt wpisano do wieloletniego planu finansowego państwa, a Ministerstwo Finansów opublikowało założenia analityczne. Ze względu na ograniczenia fiskalne budżetu realizacja została przesunięta w czasie w stosunku do deklaracji wyborczej.",
    relevant_articles: [
      {
        article_number: "Art. 27 ust. 1",
        raw_text:
          "Podatek dochodowy pobiera się od podstawy jego obliczenia według skali podatkowej, z uwzględnieniem kwoty zmniejszającej podatek odpowiadającej kwocie wolnej...",
      },
      {
        article_number: "Art. 27b ust. 3",
        raw_text:
          "W roku podatkowym 2025 kwota zmniejszająca podatek wynosi 10 800 zł dla podstawy obliczenia nieprzekraczającej 60 000 zł...",
      },
    ],
  },
  "TD-GWAR-015": {
    promise_id: "TD-GWAR-015",
    title: "Wakacje składkowe – 1 miesiąc wolny od ZUS dla mikrofirm",
    full_text:
      "Wprowadzimy dobrowolny ZUS i wakacje składkowe dla mikroprzedsiębiorców w trudnej sytuacji – jeden miesiąc w roku całkowicie bez opłacania składek na ubezpieczenie społeczne, finansowany przez państwo.",
    party: "TD",
    category: "Gospodarka",
    status: "FULFILLED",
    alignment_status: "W_PELNI",
    confidence_score: 0.96,
    bill_id: "sejm-x-389",
    bill_title: "Ustawa z dnia 9 maja 2024 r. o zmianie ustawy o systemie ubezpieczeń społecznych oraz niektórych innych ustaw",
    bill_print_num: "389",
    estimated_budget_impact_pln: 1640000000,
    divergence_details:
      "Składka zdrowotna nie została objęta zwolnieniem wakacyjnym (zwolnienie dotyczy składek na ubezpieczenie społeczne: emerytalne, rentowe, wypadkowe i chorobowe).",
    justification:
      "Ustawa została uchwalona przez Sejm, podpisana przez Prezydenta RP i opublikowana w Dzienniku Ustaw. Przedsiębiorcy mogą składać wnioski do ZUS od 1 listopada 2024 r. Koszt refundacji składek pokrywa budżet państwa.",
    relevant_articles: [
      {
        article_number: "Art. 17a ust. 1",
        raw_text:
          "Płatnik składek będący mikroprzedsiębiorcą może złożyć wniosek o zwolnienie z obowiązku opłacenia należnych składek na własne ubezpieczenia społeczne za jeden wskazany we wniosku miesiąc kalendarzowy w danym roku kalendarzowym...",
      },
      {
        article_number: "Art. 17a ust. 4",
        raw_text:
          "Składki, o których mowa w ust. 1, są finansowane w ramach dotacji z budżetu państwa do Funduszu Ubezpieczeń Społecznych...",
      },
    ],
  },
  "LEW-SPO-008": {
    promise_id: "LEW-SPO-008",
    title: "Renta wdowia – wsparcie finansowe dla owdowiałych seniorów",
    full_text:
      "Wprowadzimy rentę wdowią: możliwość zachowania własnej emerytury i pobierania 50% świadczenia po zmarłym małżonku, lub zachowania 100% świadczenia zmarłego i 50% własnego.",
    party: "LEWICA",
    category: "Sprawiedliwość",
    status: "FULFILLED",
    alignment_status: "W_PELNI",
    confidence_score: 0.94,
    bill_id: "sejm-x-492",
    bill_title: "Ustawa z dnia 26 lipca 2024 r. o zmianie ustawy o emeryturach i rentach z Funduszu Ubezpieczeń Społecznych (Druk sejmowy 492)",
    bill_print_num: "492",
    estimated_budget_impact_pln: 4200000000,
    divergence_details:
      "Wskaźnik drugiego świadczenia ustalono w pierwszym etapie na 15% (od 1 lipca 2025 do końca 2026 r.), a od 2027 r. na poziomie 25% (zamiast postulowanych 50%).",
    justification:
      "Kluczowy postulat socjalny Nowej Lewicy został przyjęty przez parlament i podpisany przez Prezydenta RP. Wdrożono model kroczącego wzrostu świadczenia w porozumieniu z Ministerstwem Finansów.",
    relevant_articles: [
      {
        article_number: "Art. 95a ust. 1",
        raw_text:
          "W razie zbiegu prawa do renty rodzinnej z prawem do własnego świadczenia emerytalnego, wypłaca się jedno świadczenie w całości, a drugie w wysokości 15%...",
      },
    ],
  },
  "KO-100K-001": {
    promise_id: "KO-100K-001",
    title: "Program 'Aktywny Rodzic' (tzw. Babciowe) do 1500 zł miesięcznie",
    full_text:
      "Wprowadzimy świadczenie 'Aktywny Rodzic' w kwocie 1500 zł miesięcznie dla rodziców powracających na rynek pracy po narodzinach dziecka do lat 3, na dofinansowanie opieki babci lub niani.",
    party: "KO",
    category: "Gospodarka",
    status: "FULFILLED",
    alignment_status: "W_PELNI",
    confidence_score: 0.97,
    bill_id: "sejm-x-387",
    bill_title: "Ustawa z dnia 15 maja 2024 r. o wspieraniu rodziców w aktywności zawodowej oraz w wychowaniu dziecka – 'Aktywny Rodzic'",
    bill_print_num: "387",
    estimated_budget_impact_pln: 8900000000,
    divergence_details:
      "Dla dzieci z niepełnosprawnościami podniesiono kwotę świadczenia do 1900 zł miesięcznie.",
    justification:
      "Ustawa weszła w życie 1 października 2024 r. Wypłaty realizowane są przez ZUS w trzech filarach: aktywni rodzice w pracy (1500 zł), aktywnie w żłobku (do 1500 zł) oraz aktywnie w domu (500 zł).",
    relevant_articles: [
      {
        article_number: "Art. 7 ust. 1",
        raw_text:
          "Świadczenie 'aktywni rodzice w pracy' przysługuje w wysokości 1500 zł miesięcznie na dziecko od pierwszego dnia miesiąca, w którym dziecko ukończyło 12. miesiąc życia, do ostatniego dnia miesiąca poprzedzającego miesiąc, w którym dziecko ukończy 35. miesiąc życia...",
      },
    ],
  },
  "KO-100K-023": {
    promise_id: "KO-100K-023",
    title: "Kredyt mieszkaniowy 0% #naStart dla młodych",
    full_text:
      "Wprowadzimy kredyt 0% na zakup pierwszego mieszkania dla ludzi do 35. roku życia. Państwo dopłaci do odsetek, likwidując bariery wejścia na rynek nieruchomości.",
    party: "KO",
    category: "Mieszkalnictwo",
    status: "IN_PROGRESS",
    alignment_status: "SPRZECZNA",
    confidence_score: 0.84,
    bill_id: "sejm-x-544",
    bill_title: "Projekt ustawy o kredycie mieszkaniowym #naStart (Druk 544)",
    bill_print_num: "544",
    estimated_budget_impact_pln: 11500000000,
    divergence_details:
      "Brak konsensusu w koalicji rządowej (sprzeciw Polski 2050 i Lewicy); Wprowadzono kwartalne limity wniosków i kryteria dochodowe; Ryzyko napędzania cen transakcyjnych mieszkań.",
    justification:
      "Założenia projektu ustawy wywołały głęboki podział wewnątrz koalicji rządzącej. Koalicjanci wskazali na ryzyko subsydiowania zysków deweloperów. Projekt został skierowany do ponownych konsultacji społecznych i nie uzyskał większości w Sejmie.",
    relevant_articles: [
      {
        article_number: "Art. 4 ust. 2",
        raw_text:
          "Dopłata do rat kredytu mieszkaniowego przysługuje, o ile dochód gospodarstwa jednoosobowego nie przekracza limitu określonego w załączniku nr 1...",
      },
    ],
  },
  "KO-100K-005": {
    promise_id: "KO-100K-005",
    title: "30% podwyżki wynagrodzeń dla nauczycieli od 2024 r.",
    full_text:
      "Podniesiemy pensje nauczycieli o co najmniej 30%, nie mniej niż 1500 zł brutto podwyżki, przywracając prestiż zawodowi nauczyciela i godne warunki płacy.",
    party: "KO",
    category: "Edukacja",
    status: "FULFILLED",
    alignment_status: "W_PELNI",
    confidence_score: 0.98,
    bill_id: "sejm-x-112",
    bill_title: "Ustawa budżetowa na rok 2024 z dnia 18 stycznia 2024 r. (Dz.U. 2024 poz. 271)",
    bill_print_num: "112",
    estimated_budget_impact_pln: 12800000000,
    divergence_details:
      "Nauczyciele początkujący otrzymali podwyżkę w wysokości 33% (zamiast 30%), aby zrównać ich pensję minimalną z płacą ustawową.",
    justification:
      "Zapisy zrealizowano w ustawie budżetowej na rok 2024. Wypłaty podwyżek z wyrównaniem od 1 stycznia 2024 r. zostały przekazane wszystkim jednostkom samorządu terytorialnego.",
    relevant_articles: [
      {
        article_number: "Art. 9 ust. 1 pkt 2",
        raw_text:
          "Średnie wynagrodzenia nauczycieli wzrastają o 30%, a w przypadku nauczycieli nieposiadających stopnia awansu zawodowego o 33% w stosunku do roku bazowego...",
      },
    ],
  },
};

export const SHOWCASE_TIMELINES: Record<string, TimelineEvent[]> = {
  "KO-100K-042": [
    {
      date: "2023-10-15",
      stage_name: "Deklaracja Programowa",
      description: "Ogłoszenie '100 Konkretów na 100 Dni' Koalicji Obywatelskiej.",
      is_completed: true,
    },
    {
      date: "2024-02-14",
      stage_name: "Założenia w Ministerstwie Finansów",
      description: "Publikacja wstępnych symulacji skutków dla sektora finansów publicznych.",
      is_completed: true,
    },
    {
      date: "2024-06-19",
      stage_name: "Procedura Nadmiernego Deficytu (EDP)",
      description: "Komisja Europejska objęła Polskę procedurą EDP, wymuszając konsolidację fiskalną.",
      is_completed: true,
    },
    {
      date: "2025-01-01",
      stage_name: "Kolejna faza legislacyjna",
      description: "Planowane skierowanie zmodyfikowanego projektu do prac sejmowych.",
      is_completed: false,
    },
  ],
  "TD-GWAR-015": [
    {
      date: "2023-09-20",
      stage_name: "12 Gwarancji Trzeciej Drogi",
      description: "Wpisanie wakacji składkowych do wspólnego programu PSL i Polski 2050.",
      is_completed: true,
    },
    {
      date: "2024-03-12",
      stage_name: "Projekt Rządowy (Druk 389)",
      description: "Rada Ministrów przyjęła i skierowała projekt ustawy do Sejmu RP.",
      is_completed: true,
    },
    {
      date: "2024-05-09",
      stage_name: "Uchwalenie przez Sejm",
      description: "Sejm uchwalił ustawę większością 432 głosów za.",
      is_completed: true,
    },
    {
      date: "2024-06-11",
      stage_name: "Podpis Prezydenta i Publikacja",
      description: "Prezydent RP podpisał ustawę. Publikacja w Dzienniku Ustaw (poz. 863).",
      is_completed: true,
    },
    {
      date: "2024-11-01",
      stage_name: "Wejście w życie",
      description: "System ZUS uruchomił składanie wniosków RWS przez PUE ZUS / eZUS.",
      is_completed: true,
    },
  ],
};
