/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  /* config options here */
  typescript: {
    ignoreBuildErrors: true,
  },
  reactStrictMode: false,
  transpilePackages: ["lucide-react"],
};

export default nextConfig;
