"use client";

import { motion } from "framer-motion";
import { ArrowRight, Shield, Sparkles, GitMerge, Eye } from "lucide-react";
import Link from "next/link";

const STATS = [
  { value: "460", label: "Posłów monitorowanych", suffix: "" },
  { value: "2 400", label: "Obietnic wyborczych", suffix: "+" },
  { value: "99.7", label: "Dostępność API", suffix: "%" },
  { value: "24/7", label: "Ciągły audyt AI", suffix: "" },
];

const BADGES = [
  { icon: Shield, label: "Open Source · MIT" },
  { icon: Sparkles, label: "RAG + pgvector" },
  { icon: GitMerge, label: "Apache Airflow DAGs" },
  { icon: Eye, label: "Transparentność publiczna" },
];

const fadeUp = {
  hidden: { opacity: 0, y: 30 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1, duration: 0.6, ease: "easeOut" as const },
  }),
};

export function HeroSection() {
  return (
    <section className="relative overflow-hidden pt-8 pb-20">
      {/* Ambient glow orbs */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-40 left-1/2 -translate-x-1/2 w-[900px] h-[600px] rounded-full bg-indigo-600/10 blur-[120px]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute top-20 -right-20 w-[400px] h-[400px] rounded-full bg-sky-500/8 blur-[100px]"
      />

      <div className="relative z-10 mx-auto max-w-5xl text-center">
        {/* Badge row */}
        <motion.div
          initial={false}
          animate="visible"
          variants={fadeUp}
          custom={0}
          className="mb-6 flex flex-wrap justify-center gap-2"
        >
          {BADGES.map(({ icon: Icon, label }) => (
            <span
              key={label}
              className="inline-flex items-center gap-1.5 rounded-full border border-slate-700/60 bg-slate-800/50 px-3 py-1 text-xs font-medium text-slate-300 backdrop-blur-sm"
            >
              <Icon className="h-3 w-3 text-indigo-400" />
              {label}
            </span>
          ))}
        </motion.div>

        {/* Headline */}
        <motion.h1
          initial={false}
          animate="visible"
          variants={fadeUp}
          custom={1}
          className="text-4xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-white leading-[1.08]"
        >
          Czy politycy dotrzymują{" "}
          <span className="relative inline-block">
            <span className="bg-gradient-to-r from-indigo-400 via-sky-400 to-emerald-400 bg-clip-text text-transparent">
              obietnic?
            </span>
            <motion.span
              initial={{ scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ delay: 0.2, duration: 0.4, ease: "easeOut" }}
              className="absolute -bottom-1 left-0 right-0 h-px origin-left bg-gradient-to-r from-indigo-400 via-sky-400 to-emerald-400"
            />
          </span>
        </motion.h1>

        {/* Sub-headline */}
        <motion.p
          initial={false}
          animate="visible"
          variants={fadeUp}
          custom={2}
          className="mt-6 mx-auto max-w-2xl text-base sm:text-lg text-slate-400 leading-relaxed"
        >
          Weryfikator Obietnic to obywatelski audytor napędzany AI, który automatycznie
          weryfikuje deklaracje wyborcze partii politycznych z rzeczywistymi zapisami
          projektów ustaw procedowanych w{" "}
          <span className="text-slate-300 font-medium">Sejmie RP X Kadencji</span>.
        </motion.p>

        {/* CTA buttons */}
        <motion.div
          initial={false}
          animate="visible"
          variants={fadeUp}
          custom={3}
          className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4"
        >
          <a
            href="#katalog"
            id="hero-cta-primary"
            className="group relative inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-sky-600 px-7 py-3.5 text-sm font-semibold text-white shadow-lg shadow-indigo-600/30 transition-all duration-200 hover:shadow-indigo-600/50 hover:scale-[1.02] active:scale-[0.98]"
          >
            Sprawdź obietnice
            <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
          </a>
          <a
            href="https://github.com/FranekJemiolo/weryfikatorobietnic"
            target="_blank"
            rel="noopener noreferrer"
            id="hero-cta-github"
            className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-800/60 px-7 py-3.5 text-sm font-semibold text-slate-200 backdrop-blur-sm transition-all duration-200 hover:border-slate-600 hover:bg-slate-700/60"
          >
            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path
                fillRule="evenodd"
                d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                clipRule="evenodd"
              />
            </svg>
            GitHub
          </a>
        </motion.div>

        {/* Stats */}
        <motion.div
          initial={false}
          animate="visible"
          variants={fadeUp}
          custom={4}
          className="mt-16 grid grid-cols-2 sm:grid-cols-4 gap-px rounded-2xl border border-slate-800/80 bg-slate-800/80 overflow-hidden shadow-xl"
        >
          {STATS.map(({ value, label, suffix }) => (
            <div
              key={label}
              className="flex flex-col items-center gap-1 bg-slate-900/70 px-6 py-6 backdrop-blur-sm"
            >
              <span className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
                {value}
                <span className="text-indigo-400">{suffix}</span>
              </span>
              <span className="text-xs text-slate-400 text-center">{label}</span>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
