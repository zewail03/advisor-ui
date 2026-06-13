import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AIU Admin Portal",
  description: "Administration console for the AIU student system",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      {/* suppressHydrationWarning: browser extensions (e.g. Grammarly) inject
          data-* attributes on <body> before React hydrates */}
      <body className="min-h-screen antialiased" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
