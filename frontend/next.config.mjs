/** @type {import('next').NextConfig} */
const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "");

const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  async rewrites() {
    if (!apiBaseUrl) {
      return [];
    }

    // Keep browser requests same-origin so Vercel previews do not need backend CORS access.
    return [
      {
        source: "/api/:path*",
        destination: `${apiBaseUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
