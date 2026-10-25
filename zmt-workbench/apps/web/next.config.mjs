/** @type {import('next').NextConfig} */
const basePath = process.env.NEXT_BASE_PATH || '';

const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  // 公网部署在 Caddy 443 的 /zmt 路径下（Lighthouse 只放行 80/443），页面与静态资源统一挂前缀
  basePath,
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: `${process.env.BACKEND_URL ?? 'http://localhost:8000'}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;