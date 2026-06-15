/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Same-origin proxy: the browser calls /api/* on this host and Next forwards to the
  // FastAPI backend server-side. Lets a single tunnelled hostname serve both the UI and
  // the API (no CORS, no second subdomain). SSE streams through unchanged.
  async rewrites() {
    const backend = process.env.BACKEND_ORIGIN || "http://127.0.0.1:8000";
    return [{ source: "/api/:path*", destination: `${backend}/:path*` }];
  },
};

export default nextConfig;
