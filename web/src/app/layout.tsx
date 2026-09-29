import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CiteHop",
  description: "Scientific paper search in MariaDB: keyword, meaning and citation links.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <a
          href="#main"
          className="fixed -top-16 left-3 z-50 rounded-control bg-surface px-3 py-2 focus:top-3"
        >
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
