"use client";

import { motion } from "framer-motion";
import { Code2, FileText, MessagesSquare, Star } from "lucide-react";

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1, duration: 0.55, ease: "easeOut" as const },
  }),
};

const WAYS = [
  {
    icon: FileText,
    title: "Dodaj obietnicę",
    description:
      "Nie jesteś programistą? Zgłoś nową deklarację wyborczą lub uzupełnij plik YAML w repozytorium. Opisz obietnicę partii i podaj źródło — resztą zajmie się pipeline.",
    cta: "Przeglądaj data/",
    href: "https://github.com/FranekJemiolo/weryfikatorobietnic/tree/main/data",
    accent: "border-emerald-500/30 hover:border-emerald-500/50",
    glow: "bg-emerald-500/5",
    badge: "Dla każdego",
    badgeColor: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20",
  },
  {
    icon: Code2,
    title: "Zgłoś Pull Request",
    description:
      "Backend w FastAPI + SQLModel, DAGi Airflow, scraper Sejmu? Otwórz issue albo fork repozytorium. Przyjmujemy testy, refactoring i nowe źródła danych.",
    cta: "Otwórz issue",
    href: "https://github.com/FranekJemiolo/weryfikatorobietnic/issues/new",
    accent: "border-indigo-500/30 hover:border-indigo-500/50",
    glow: "bg-indigo-500/5",
    badge: "Programiści",
    badgeColor: "bg-indigo-500/10 text-indigo-300 border-indigo-500/20",
  },
  {
    icon: MessagesSquare,
    title: "Zrecenzuj werdykt AI",
    description:
      "Każda ocena AI może być zakwestionowana. Zbieramy feedback obywatelski do doskonalenia modeli. Jeśli widzisz błędny werdykt — sprawdź i zgłoś uwagę.",
    cta: "Przeglądaj katalog",
    href: "#katalog",
    accent: "border-sky-500/30 hover:border-sky-500/50",
    glow: "bg-sky-500/5",
    badge: "Obywatele",
    badgeColor: "bg-sky-500/10 text-sky-300 border-sky-500/20",
  },
  {
    icon: Star,
    title: "Gwiazdka na GitHub",
    description:
      "Najprostszy sposób wsparcia — daj gwiazdkę repozytorium. Pomaga nam dotrzeć do deweloperów civic-tech i mediów zainteresowanych transparentnością.",
    cta: "GitHub Repo",
    href: "https://github.com/FranekJemiolo/weryfikatorobietnic",
    accent: "border-amber-500/30 hover:border-amber-500/50",
    glow: "bg-amber-500/5",
    badge: "Wszyscy",
    badgeColor: "bg-amber-500/10 text-amber-300 border-amber-500/20",
  },
];

export function ContributeSection() {
  return (
    <section className="py-20">
      <motion.div
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, margin: "-80px" }}
        variants={fadeUp}
        custom={0}
        className="text-center mb-12"
      >
        <span className="inline-block rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-300 mb-4">
          Open Source
        </span>
        <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
          Dołącz do ruchu transparentności
        </h2>
        <p className="mt-3 text-slate-400 max-w-xl mx-auto text-sm sm:text-base">
          Projekt jest w pełni otwarty. Każdy — programista, dziennikarz,
          aktywista — może wnieść swój wkład.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {WAYS.map(({ icon: Icon, title, description, cta, href, accent, glow, badge, badgeColor }, i) => (
          <motion.div
            key={title}
            id={`contribute-${title.toLowerCase().replace(/\s+/g, "-")}`}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-40px" }}
            variants={fadeUp}
            custom={i + 1}
            className={`group relative rounded-2xl border ${accent} ${glow} bg-slate-900/50 p-6 backdrop-blur-sm transition-all duration-300`}
          >
            <div className="flex items-start gap-4">
              <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-800/80 ring-1 ring-slate-700/60">
                <Icon className="h-5 w-5 text-slate-300" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-bold text-white text-sm sm:text-base">{title}</h3>
                  <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${badgeColor}`}>
                    {badge}
                  </span>
                </div>
                <p className="text-xs sm:text-sm text-slate-400 leading-relaxed mb-4">
                  {description}
                </p>
                <a
                  href={href}
                  target={href.startsWith("http") ? "_blank" : undefined}
                  rel={href.startsWith("http") ? "noopener noreferrer" : undefined}
                  className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-300 hover:text-white transition-colors duration-150 group/link"
                >
                  {cta}
                  <svg
                    className="h-3.5 w-3.5 transition-transform duration-200 group-hover/link:translate-x-0.5"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                </a>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
