import React from "react";

interface LogoProps {
  size?: "sm" | "md" | "lg";
  showTagline?: boolean;
}

export const Logo: React.FC<LogoProps> = ({ size = "md", showTagline = false }) => {
  const iconSizes = {
    sm: "w-7 h-7",
    md: "w-9 h-9",
    lg: "w-12 h-12",
  };

  const titleSizes = {
    sm: "text-base",
    md: "text-xl",
    lg: "text-2xl",
  };

  return (
    <div className="flex items-center gap-3">
      {/* Original Shield + Lock Concept SVG */}
      <div className={`relative flex items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-blue-700 p-2 shadow-lg shadow-cyan-500/20 ${iconSizes[size]}`}>
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="w-full h-full text-white drop-shadow"
        >
          {/* Shield Outer Path */}
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          {/* Shackle of Lock */}
          <path d="M10 10V8a2 2 0 0 1 4 0v2" strokeWidth="2.2" />
          {/* Lock Body */}
          <rect x="9" y="10" width="6" height="5" rx="1" fill="currentColor" stroke="none" />
          {/* Keyhole dot */}
          <circle cx="12" cy="12.5" r="0.8" fill="#0B132B" stroke="none" />
        </svg>
      </div>

      <div>
        <div className="flex items-center gap-1.5 leading-none">
          <span className={`font-extrabold tracking-tight text-white ${titleSizes[size]}`}>
            TruthShield<span className="text-cyan-400">AI</span>
          </span>
        </div>
        <p className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">
          Content Protection
        </p>
        {showTagline && (
          <p className="text-[11px] text-cyan-300 italic mt-0.5">
            “Together for a Safer Digital World”
          </p>
        )}
      </div>
    </div>
  );
};

