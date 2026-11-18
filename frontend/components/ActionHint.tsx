"use client";

import React, { useState } from "react";
import { HelpCircle } from "lucide-react";

interface ActionHintProps {
  title?: string;
  description: string;
}

export const ActionHint: React.FC<ActionHintProps> = ({ title, description }) => {
  const [open, setOpen] = useState(false);

  return (
    <span className="relative inline-flex items-center">
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        aria-label={title || "More information"}
        className="p-0.5 rounded-full text-slate-400 hover:text-cyan-400 transition-colors focus:outline-none"
      >
        <HelpCircle className="w-3.5 h-3.5" />
      </button>

      {open && (
        <div
          role="tooltip"
          className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-60 rounded-xl border border-slate-700 bg-slate-950/95 p-3 text-left shadow-2xl z-50 pointer-events-none"
        >
          {title && <div className="text-[11px] font-semibold text-cyan-400 mb-1">{title}</div>}
          <p className="text-[11px] leading-relaxed text-slate-300 font-normal">{description}</p>
        </div>
      )}
    </span>
  );
};
