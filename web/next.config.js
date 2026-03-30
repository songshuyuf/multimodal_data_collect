/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://172.16.55.196:8000/api/:path*",
      },
    ];
  },
};

module.exports = nextConfig;
