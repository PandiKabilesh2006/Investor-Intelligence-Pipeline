import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  typedRoutes: true,
  output: "export",
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
