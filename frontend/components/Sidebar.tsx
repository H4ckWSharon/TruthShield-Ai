"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/authContext";
import { HowItWorksModal } from "./HowItWorksModal";
import {
  LayoutDashboard,
  ScanSearch,
  Briefcase,
  Fingerprint,
  FileCheck2,
  ShieldAlert,
  HelpCircle,
} from "lucide-react";

export const Sidebar: React.FC = () => {
  const pathname = usePathname();
  const { user } = useAuth();
  const [showGuide, setShowGuide] = useState(false);

  const navItems = [
    {
      label: "Home Overview",
      hint: "Live summary & quick actions",
      href: "/",
      icon: LayoutDashboard,
    },
    {
      label: "Check Content",
      hint: "Scan links, photos, video, text",
      href: "/analysis",
      icon: ScanSearch,
    },
    {
      label: "My Cases & Proof",
      hint: "Track incidents & lock files",
      href: "/cases",
      icon: Briefcase,
    },
    {
      label: "Protect Originals",
      hint: "Guard against copied uploads",
      href: "/fingerprints",
      icon: Fingerprint,
    },
    {
      label: "Removal & PDFs",
      hint: "Draft takedowns & verify links",
      href: "/removal",
      icon: FileCheck2,
    },
  ];

  if (!user || user.role === "admin") {
    navItems.push({
      label: "System Settings",
      hint: "AI models, users & audit logs",
      href: "/admin",
      icon: ShieldAlert,
    });
  }

  return (
    <>
      <aside className="w-64 border-r border-slate-800/70 bg-navy-950/50 p-4 flex-col justify-between shrink-0 hidden md:flex">
        <div className="space-y-4">
          <div className="text-[10px] font-semibold tracking-wider uppercase text-slate-500 px-3">
            Workspace Tools
          </div>

          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-start gap-3 px-3 py-2.5 rounded-xl transition ${
                    isActive
                      ? "bg-cyan-500/10 text-cyan-300 border border-cyan-500/30"
                      : "text-slate-400 hover:text-white hover:bg-slate-800/50 border border-transparent"
                  }`}
                >
                  <Icon
                    className={`w-4 h-4 mt-0.5 shrink-0 ${
                      isActive ? "text-cyan-400" : "text-slate-400"
                    }`}
                  />
                  <div className="min-w-0">
                    <div className="text-xs font-semibold leading-tight">{item.label}</div>
                    <div className="text-[10px] text-slate-500 truncate mt-0.5">{item.hint}</div>
                  </div>
                </Link>
              );
            })}
          </nav>
        </div>

        <button
          type="button"
          onClick={() => setShowGuide(true)}
          className="text-left rounded-2xl border border-slate-800/80 bg-slate-900/50 hover:border-cyan-500/30 hover:bg-slate-900/80 p-3.5 space-y-1.5 transition"
        >
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
            <HelpCircle className="w-4 h-4 text-cyan-400" />
            Not sure where to start?
          </div>
          <p className="text-[11px] text-slate-400 leading-relaxed">
            Click here for a simple 4-step guide on what every button does.
          </p>
        </button>
      </aside>

      <HowItWorksModal isOpen={showGuide} onClose={() => setShowGuide(false)} />
    </>
  );
};
