/** @type {import('next').NextConfig} */
const apiBase = process.env.FASTAPI_URL || "http://127.0.0.1:8000";

const nextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiBase}/api/:path*` }];
  },
};

module.exports = nextConfig;

