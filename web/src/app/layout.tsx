import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Lease and issue review",
  description: "Review what the lease and issue agents produced, unit by unit.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full">{children}</body>
    </html>
  );
}
