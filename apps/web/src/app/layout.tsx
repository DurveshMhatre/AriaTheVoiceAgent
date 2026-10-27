import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "Aria Voice CX · Aura Skincare", description: "A private evaluator demo of Aura Skincare's voice and text support assistant." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" data-theme="dark"><body>{children}</body></html>;
}
