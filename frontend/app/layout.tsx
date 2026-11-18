import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/authContext";
import { Navbar } from "@/components/Navbar";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "TruthShield AI — Digital Content Protection Platform",
  description: "AI-Powered Digital Content Protection & Removal Assistance Platform by Alphard Crucis Private Limited.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-navy-950 text-slate-100 flex flex-col min-h-screen">
        <AuthProvider>
          <Navbar />
          <div className="flex flex-1 overflow-hidden">
            <Sidebar />
            <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
              <div className="max-w-7xl mx-auto">{children}</div>
            </main>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
