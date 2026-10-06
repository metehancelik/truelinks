import type { NextConfig } from "next";

// Where the Python API lives. Inside Docker Compose this is the `api` service.
const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Self-contained server bundle, so the runtime image needs no node_modules.
  output: "standalone",

  // The browser only ever talks to this app; /api/* is proxied to the backend.
  // One public domain, no CORS.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;
