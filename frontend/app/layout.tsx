import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { Instrument_Serif } from "next/font/google";
import "./globals.css";
import { Shell } from "@/components/Shell";

const serif = Instrument_Serif({ weight: "400", subsets: ["latin"], variable: "--font-serif" });

export const metadata: Metadata = {
  title: "MiCA Compliance Copilot",
  description:
    "RAG + agentic assistant for the EU Markets in Crypto-Assets Regulation (Reg (EU) 2023/1114).",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable} ${serif.variable}`}>
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
