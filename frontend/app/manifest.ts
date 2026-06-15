import type { MetadataRoute } from "next";
import { SITE_NAME, SITE_DESC } from "@/lib/site";

// Generates /manifest.webmanifest (Next auto-links it). Makes the app installable + gives mobile
// the brand colours. PWA icons live in /public (referenced by path).
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: SITE_NAME,
    short_name: "MiCA Copilot",
    description: SITE_DESC,
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#faf9f5",
    theme_color: "#1a3e72",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
