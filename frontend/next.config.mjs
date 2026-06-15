/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Same-origin proxy: the browser calls /api/* on this host and Next forwards to the
  // FastAPI backend server-side. Lets a single tunnelled hostname serve both the UI and
  // the API (no CORS, no second subdomain). SSE streams through unchanged.
  async rewrites() {
    const backend = process.env.BACKEND_ORIGIN || "http://127.0.0.1:8000";
    // Self-hosted Plausible. Proxying it first-party means the browser only ever loads
    // same-origin HTTPS (the instance is plain http → would be blocked as mixed content),
    // it hides the origin IP, and it survives ad-blockers.
    const plausible = process.env.PLAUSIBLE_ORIGIN || "http://178.105.127.121:3001";
    return [
      { source: "/api/:path*", destination: `${backend}/:path*` },
      { source: "/pa/js/:script*", destination: `${plausible}/js/:script*` },
      { source: "/pa/event", destination: `${plausible}/api/event` },
    ];
  },
};

export default nextConfig;
