import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "CiteHop", description: "Ask a question. Follow the sources." };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
