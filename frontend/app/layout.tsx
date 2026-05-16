import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { Shell } from "@/components/layout/shell";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "CodeMind — Architecture Intelligence",
  description: "Enterprise codebase knowledge graph platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        <Providers>
          <Shell>{children}</Shell>
        </Providers>
      </body>
    </html>
  );
}
