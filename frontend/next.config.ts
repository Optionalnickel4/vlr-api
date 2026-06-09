import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next 16 hardens cross-origin dev access. This dashboard is reached over the
  // LXC 289 LAN IP (and potentially Tailscale), so whitelist those hosts to
  // avoid the known dev-origin hydration/asset bug class. Production (next
  // start) is unaffected; this only relaxes `next dev`.
  allowedDevOrigins: ["192.168.1.35"],
};

export default nextConfig;
