import type { Metadata } from "next";
import { Geist_Mono, Instrument_Sans, Source_Serif_4 } from "next/font/google";
import "./globals.css";
import AppAuthProvider from "@/components/AppAuthProvider";
import { SessionProvider } from "@/components/SessionProvider";

// Body face per the design reference: Instrument Sans.
const instrumentSans = Instrument_Sans({
  variable: "--font-instrument-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// Serif for assistant narrative — the defining trait of the Claude-style reading surface.
const sourceSerif = Source_Serif_4({
  variable: "--font-source-serif",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "CSA Workbench",
  description: "CSA Workbench — the agent-powered engagement workspace for solution architects",
  icons: {
    icon: [
      { url: "/icon.svg", type: "image/svg+xml" },
    ],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${instrumentSans.variable} ${geistMono.variable} ${sourceSerif.variable} font-sans antialiased`}
      >
        <AppAuthProvider>
          <SessionProvider>{children}</SessionProvider>
        </AppAuthProvider>
      </body>
    </html>
  );
}
