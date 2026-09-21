import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "./providers";

const isExport = process.env.NEXT_OUTPUT === "export";
const prefix = isExport ? "/weryfikatorobietnic" : "";

export const metadata: Metadata = {
  title: "Weryfikator Obietnic Wyborczych | Obywatelski Audyt Prawa RP",
  description:
    "Automatyczna weryfikacja obietnic wyborczych i projektów ustaw w Sejmie RP z wykorzystaniem modeli językowych LLM i bazy wektorowej.",
  manifest: `${prefix}/manifest.json`,
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Weryfikator",
  },
  icons: {
    icon: `${prefix}/icons/icon-192x192.png`,
    apple: `${prefix}/icons/icon-192x192.png`,
  },
};

export const viewport: Viewport = {
  themeColor: "#0f172a",
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pl" className="dark">
      <body className="min-h-screen bg-slate-950 font-sans text-slate-100 antialiased selection:bg-indigo-500 selection:text-white">
        <Providers>
          <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
            <div className="container mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
              <a href={`${prefix}/#`} className="flex items-center space-x-3 group">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-tr from-indigo-500 to-sky-400 font-bold text-white shadow-lg shadow-indigo-500/30 group-hover:scale-105 transition-transform">
                  WO
                </div>
                <div>
                  <h1 className="text-sm font-bold tracking-tight text-white sm:text-base group-hover:text-indigo-300 transition-colors">
                    Weryfikator Obietnic
                  </h1>
                  <p className="text-[10px] text-slate-400 sm:text-xs">
                    Sejm RP X Kadencja • Audyt Obywatelski
                  </p>
                </div>
              </a>

              {/* Navigation links */}
              <nav className="hidden md:flex items-center space-x-6 text-xs font-medium text-slate-300">
                <a href={`${prefix}/#katalog`} className="hover:text-white transition-colors">
                  Katalog Obietnic
                </a>
                <a href={`${prefix}/#dashboard`} className="hover:text-white transition-colors">
                  Wskaźniki Rządu
                </a>
                <a href={`${prefix}/#architektura`} className="hover:text-white transition-colors">
                  Architektura AI
                </a>
                <a href={`${prefix}/#contribute`} className="hover:text-white transition-colors">
                  Współpraca
                </a>
              </nav>

              <div className="flex items-center space-x-3">
                <span className="inline-flex items-center rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-400 border border-emerald-500/20">
                  <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Live Audyt
                </span>
                <a
                  href="https://github.com/FranekJemiolo/weryfikatorobietnic"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hidden sm:inline-flex items-center rounded-lg border border-slate-700 bg-slate-800/80 px-3 py-1 text-xs font-medium text-slate-200 hover:bg-slate-700 hover:text-white transition"
                >
                  GitHub
                </a>
              </div>
            </div>
          </header>
          <main className="container mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
            {children}
          </main>
        </Providers>
      </body>
    </html>
  );
}
