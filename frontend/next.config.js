/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: process.env.BACKEND_API_URL || 'http://127.0.0.1:5000/api/:path*',
      },
      {
        source: '/ws/:path*',
        destination: process.env.WS_GATEWAY_URL || 'http://127.0.0.1:8000/ws/:path*',
      },
    ];
  },
};

module.exports = nextConfig;

