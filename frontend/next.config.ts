import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  typedRoutes: true,
  output: "export",
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
