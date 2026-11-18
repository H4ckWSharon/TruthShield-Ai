"use client";

import React from "react";
import Link from "next/link";
import {
  X,
  ScanSearch,
  Briefcase,
  Fingerprint,
  FileCheck2,
  ShieldCheck,
  ArrowRight,
} from "lucide-react";

interface HowItWorksModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const GUIDE_SECTIONS = [
  {
    title: "1. Check Content",
    href: "/analysis",
    icon: ScanSearch,
    buttonName: "Scan & Check Safety",
    whatItDoes:
      "Scans photos, screenshots, videos, audio clips, text messages, or suspicious links for threats, scams, impersonation, or hidden text.",
    whenToUse:
      "Start here whenever you receive a suspicious link, abusive message, or altered media file.",
  },
  {
    title: "2. Save Case & Lock Proof",
    href: "/cases",
    icon: Briefcase,
    buttonName: "Open New Case / Deposit Proof",
    whatItDoes:
      "Organizes the incident with target URLs, investigator notes, and encrypted proof files sealed with tamper-proof SHA-256 checksums.",
    whenToUse:
      "Use this to safely store screenshots or media evidence privately before reporting.",
  },
  {
    title: "3. Protect Originals",
    href: "/fingerprints",
    icon: Fingerprint,
    buttonName: "Protect Original / Search Copies",
    whatItDoes:
      "Creates a private digital signature of your original photo, video, or audio so you can detect exact or cropped/edited re-uploads.",
    whenToUse:
      "Use this to safeguard original assets or test whether a suspect file matches yours.",
  },
  {
    title: "4. Request Removal & Export PDF",
    href: "/removal",
    icon: FileCheck2,
    buttonName: "Create Takedown / Download PDF / Verify Link",
    whatItDoes:
      "Drafts a ready-to-send takedown notice with cited platform policies, compiles a formal PDF report, links you to the platform's official intake form, and checks whether the link is still live.",
    whenToUse:
      "Use this once you are ready to formally report fake news, harassment, impersonation, or non-consensual content to YouTube, Instagram, Facebook, or web hosts.",
  },
];

export const HowItWorksModal: React.FC<HowItWorksModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl rounded-2xl border border-slate-800 bg-slate-900/95 p-6 shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 pb-3 border-b border-slate-800">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-cyan-400 text-xs font-semibold">
              <ShieldCheck className="w-4 h-4" /> Quick User Guide
            </div>
            <h2 className="text-lg font-bold text-white">How to Use TruthShield AI</h2>
            <p className="text-xs text-slate-400">
              A simple guide to what every section and button does — no technical background needed.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
            aria-label="Close guide"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
          {GUIDE_SECTIONS.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.href}
                className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 flex flex-col justify-between gap-3"
              >
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400">
                      <Icon className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-white">{item.title}</div>
                      <div className="text-[10px] text-cyan-300 font-medium">{item.buttonName}</div>
                    </div>
                  </div>
                  <p className="text-[11px] text-slate-300 leading-relaxed">{item.whatItDoes}</p>
                  <p className="text-[11px] text-slate-400 leading-relaxed">
                    <span className="text-slate-200 font-medium">When to use:</span> {item.whenToUse}
                  </p>
                </div>

                <Link
                  href={item.href}
                  onClick={onClose}
                  className="inline-flex items-center gap-1 text-[11px] font-semibold text-cyan-400 hover:text-cyan-300"
                >
                  Open {item.title.split(". ")[1]} <ArrowRight className="w-3 h-3" />
                </Link>
              </div>
            );
          })}
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-3.5 text-[11px] text-slate-400 leading-relaxed">
          <strong className="text-slate-200">Important Note:</strong> TruthShield AI runs locally on your machine, encrypts stored proof files, and never claims a third-party post is deleted until a live HTTP check confirms the link is offline.
        </div>
      </div>
    </div>
  );
};
