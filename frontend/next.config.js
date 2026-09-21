const withPWA = require("@ducanh2912/next-pwa").default({
  dest: "public",
  disable: process.env.NODE_ENV === "development",
  register: true,
  skipWaiting: true,
  cacheOnFrontEndNav: true,
  aggressiveFrontEndNavCaching: true,
  reloadOnOnline: true,
  workboxOptions: {
    disableDevLogs: true,
  },
});

/** @type {import('next').NextConfig} */

// GitHub Pages serwuje pod /weryfikatorobietnic/ — bez basePath/assetPrefix
// Next.js generuje linki od / i CSS/JS są niedostępne (404).
const isExport = process.env.NEXT_OUTPUT === "export";
const REPO_NAME = "weryfikatorobietnic";

const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,

  // Standalone output: Docker/GCP Cloud Run
  // Export output:     GitHub Pages (static HTML)
  // Undefined:         regular Next.js server (local dev, Vercel)
  output:
    process.env.NEXT_OUTPUT === "standalone"
      ? "standalone"
      : isExport
        ? "export"
        : undefined,

  // Krytyczne dla GitHub Pages: ustawia prefix /_next/ → /weryfikatorobietnic/_next/
  basePath: isExport ? `/${REPO_NAME}` : "",
  assetPrefix: isExport ? `/${REPO_NAME}/` : "",

  images: {
    // next/image nie działa w output:export — wymagany unoptimized:true
    unoptimized: isExport,
    remotePatterns: [
      {
        protocol: "https",
        hostname: "api.sejm.gov.pl",
      },
    ],
  },

  async rewrites() {
    // rewrites nie działają w export mode (ignorowane przez Next.js)
    if (isExport) return [];
    return [
      {
        source: "/api/backend/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/:path*`,
      },
    ];
  },

  async headers() {
    // headers nie działają w export mode (ignorowane przez Next.js)
    if (isExport) return [];
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
      {
        source: "/_next/static/(.*)",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=31536000, immutable",
          },
        ],
      },
    ];
  },
};

module.exports = withPWA(nextConfig);
