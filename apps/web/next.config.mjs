/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // API proxying is handled in middleware.ts (rewrites /api/* to INTERNAL_API_URL
  // with auth + the internal token), so no static rewrites are needed here.
};

export default nextConfig;
