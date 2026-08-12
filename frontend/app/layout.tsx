import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OmniCare Financial Customer Assistant",
  description: "A prototype insurance customer assistant for policy and mock-claim support.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
