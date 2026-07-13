import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import AuthGate from "@/components/AuthGate";
import Sidebar from "@/components/Sidebar";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "LifeOS — AI Diary",
  description: "Talk about your day. LifeOS writes the diary.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex h-dvh overflow-hidden">
        <AuthGate>
          <Sidebar />
          <main className="flex min-w-0 flex-1 flex-col pt-12 md:pt-0">{children}</main>
        </AuthGate>
      </body>
    </html>
  );
}
