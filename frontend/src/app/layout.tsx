import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Weryfikator Obietnic Wyborczych | Obywatelski Audyt Prawa",
  description:
    "Automatyczna weryfikacja obietnic wyborczych i projektów ustaw w Sejmie RP z wykorzystaniem modeli językowych LLM i bazy wektorowej.",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Weryfikator",
  },
  icons: {
    icon: "/icons/icon-192x192.png",
    apple: "/icons/icon-192x192.png",
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
              <div className="flex items-center space-x-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-tr from-indigo-500 to-sky-400 font-bold text-white shadow-lg shadow-indigo-500/30">
                  WO
                </div>
                <div>
                  <h1 className="text-sm font-bold tracking-tight text-white sm:text-base">
                    Weryfikator Obietnic
                  </h1>
                  <p className="text-[10px] text-slate-400 sm:text-xs">
                    Sejm RP X Kadencja • Audyt Obywatelski
                  </p>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <span className="inline-flex items-center rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-400 border border-emerald-500/20">
                  <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Live API
                </span>
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
