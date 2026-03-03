import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/sonner";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "D2LUT - D2R Loot Filter Tool with FG Prices",
  description: "Track Forum Gold prices for Diablo 2 Resurrected items. Build custom loot filters with tier-based color coding. Monitor prices from d2jsp, Traderie, and more.",
  keywords: ["D2R", "Diablo 2 Resurrected", "Loot Filter", "FG", "Forum Gold", "d2jsp", "Traderie", "Price Tracker", "Item Filter"],
  authors: [{ name: "D2LUT Team" }],
  icons: {
    icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>💀</text></svg>",
  },
  openGraph: {
    title: "D2LUT - D2R Loot Filter Tool",
    description: "Track Forum Gold prices and build custom D2R loot filters",
    url: "https://d2lut.app",
    siteName: "D2LUT",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "D2LUT - D2R Loot Filter Tool",
    description: "Track Forum Gold prices and build custom D2R loot filters",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-zinc-950 text-white`}
      >
        {children}
        <Toaster />
      </body>
    </html>
  );
}
