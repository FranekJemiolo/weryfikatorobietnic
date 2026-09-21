"use client";

import { motion } from "framer-motion";
import {
  Database,
  BrainCircuit,
  Wind,
  Globe,
  Webhook,
  BarChart3,
  FileSearch,
  Bell,
} from "lucide-react";

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.55, ease: "easeOut" as const },
  },
};

interface BentoItem {
  id: string;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  tags?: string[];
  accent: string;
  span?: "wide" | "tall" | "normal";
}

const BENTO_ITEMS: BentoItem[] = [
  {
    id: "llm-rag",
    title: "LLM + RAG Engine",
    description:
      "Semantyczne wyszukiwanie wektorowe w pgvector porównuje fragmenty obietnic z treścią procedowanych ustaw. Model LLM wydaje werdykt: SPEŁNIONA / W TRAKCIE / ZŁAMANA.",
    icon: BrainCircuit,
    tags: ["pgvector", "OpenAI / Mistral", "Cosine similarity"],
    accent: "from-violet-500/15 to-indigo-500/5 border-violet-500/20",
    span: "wide",
  },
  {
    id: "airflow",
    title: "Apache Airflow DAGs",
    description:
      "Orkiestracja ETL — codzienne pobieranie danych z API Sejmu, RCL i ISAP, parsowanie PDF, ekstrakcja embedingów i wyzwalanie ewaluacji AI.",
    icon: Wind,
    tags: ["Celery Executor", "DAG SLA"],
    accent: "from-sky-500/15 to-cyan-500/5 border-sky-500/20",
  },
  {
    id: "database",
    title: "PostgreSQL + pgvector",
    description:
      "Relacyjna baza danych z rozszerzeniem wektorowym. Modele SQLModel z migracjami Alembic. Pełna historia głosowań, interpelacji i biogramów posłów.",
    icon: Database,
    tags: ["SQLModel", "Alembic", "pgvector 0.7"],
    accent: "from-emerald-500/15 to-teal-500/5 border-emerald-500/20",
  },
  {
    id: "sejm-api",
    title: "Wieloźródłowy ETL",
    description:
      "Klienci API dla Sejmu RP, Senatu, ISAP, RCL oraz scrapery RSS partii politycznych. Deduplikacja i normalizacja danych in-pipeline.",
    icon: FileSearch,
    tags: ["Sejm API", "ISAP", "RSS"],
    accent: "from-amber-500/15 to-orange-500/5 border-amber-500/20",
  },
  {
    id: "fastapi",
    title: "FastAPI Backend",
    description:
      "Async REST API z OpenAPI docs, rate-limitingiem, JWT auth i ustrukturyzowanym logowaniem structlog w formacie JSON.",
    icon: Globe,
    tags: ["FastAPI", "structlog", "JWT"],
    accent: "from-rose-500/15 to-pink-500/5 border-rose-500/20",
  },
  {
    id: "dashboard",
    title: "Government Score",
    description:
      "Syntetyczny wskaźnik efektywności rządu — ważona ocena realizacji obietnic z podziałem na partie, kategorie i horyzont czasowy.",
    icon: BarChart3,
    tags: ["Recharts", "ISR 60s"],
    accent: "from-fuchsia-500/15 to-purple-500/5 border-fuchsia-500/20",
  },
  {
    id: "webhooks",
    title: "Webhooks & Push PWA",
    description:
      "NGO i dziennikarze subskrybują zdarzenia przez Webhooki HMAC-SHA256. Obywatele otrzymują powiadomienia Push zgodne z RODO.",
    icon: Webhook,
    tags: ["Web Push", "HMAC", "RODO"],
    accent: "from-cyan-500/15 to-blue-500/5 border-cyan-500/20",
    span: "wide",
  },
  {
    id: "notifications",
    title: "Aktywny Obywatel",
    description:
      "System subskrypcji — śledź konkretnego posła lub kategorię obietnic i otrzymuj alert gdy AI zmieni werdykt.",
    icon: Bell,
    tags: ["PWA", "BackgroundTask"],
    accent: "from-green-500/15 to-emerald-500/5 border-green-500/20",
  },
];

export function ArchitectureBento() {
  return (
    <section className="py-20">
      <motion.div
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, margin: "-80px" }}
        variants={fadeUp}
        className="text-center mb-12"
      >
        <span className="inline-block rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-xs font-semibold text-indigo-300 mb-4">
          Architektura systemu
        </span>
        <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
          Cały stack w jednym spojrzeniu
        </h2>
        <p className="mt-3 text-slate-400 max-w-xl mx-auto text-sm sm:text-base">
          Mikroserwisy, pipeline&apos;y AI i interfejs obywatela — zaprojektowane z myślą
          o skalowalności i pełnej audytowalności.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 auto-rows-fr">
        {BENTO_ITEMS.map((item, i) => {
          const Icon = item.icon;
          const colSpan =
            item.span === "wide" ? "sm:col-span-2" : "col-span-1";

          return (
            <motion.div
              key={item.id}
              id={`bento-${item.id}`}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, margin: "-40px" }}
              variants={{
                hidden: { opacity: 0, y: 24 },
                visible: {
                  opacity: 1,
                  y: 0,
                  transition: {
                    delay: (i % 3) * 0.08,
                    duration: 0.55,
                    ease: "easeOut" as const,
                  },
                },
              }}
              className={`${colSpan} group relative rounded-2xl border bg-gradient-to-br ${item.accent} p-6 backdrop-blur-sm transition-all duration-300 hover:scale-[1.01] hover:shadow-lg hover:shadow-indigo-500/5`}
            >
              <div className="flex items-start gap-4">
                <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-800/80 ring-1 ring-slate-700/60">
                  <Icon className="h-5 w-5 text-indigo-300" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-bold text-white text-sm sm:text-base mb-1">
                    {item.title}
                  </h3>
                  <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
                    {item.description}
                  </p>
                  {item.tags && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {item.tags.map((tag) => (
                        <span
                          key={tag}
                          className="rounded-md bg-slate-800/70 px-2 py-0.5 text-[10px] font-mono text-slate-400"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}
