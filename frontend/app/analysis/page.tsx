"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import type { AnalysisResult } from "@/types";
import { ActionHint } from "@/components/ActionHint";
import {
  ScanSearch,
  Image as ImageIcon,
  Video,
  Mic,
  FileText,
  Globe,
  AlertTriangle,
  ShieldCheck,
  ArrowRight,
  Info,
  ChevronDown,
  ChevronUp,
  Briefcase,
} from "lucide-react";

type TabType = "image" | "video" | "audio" | "text" | "url";

const TAB_CONFIG: Array<{
  key: TabType;
  label: string;
  hint: string;
  useCase: string;
  icon: React.ComponentType<{ className?: string }>;
}> = [
  {
    key: "image",
    label: "Photo / Screenshot",
    hint: "Reads text inside screenshots & checks edits",
    useCase: "Use for suspicious screenshots, memes, edited photos, or shared intimate images.",
    icon: ImageIcon,
  },
  {
    key: "video",
    label: "Video",
    hint: "Inspects keyframes & transcribes speech",
    useCase: "Use for short clips, screen recordings, or suspected deepfake videos.",
    icon: Video,
  },
  {
    key: "audio",
    label: "Audio / Voice",
    hint: "Transcribes spoken words & checks threats",
    useCase: "Use for voice notes, call recordings, or suspicious audio files.",
    icon: Mic,
  },
  {
    key: "text",
    label: "Message / Text",
    hint: "Flags threats, scams, impersonation & fake news",
    useCase: "Paste DMs, emails, comments, or posts to check for harmful language.",
    icon: FileText,
  },
  {
    key: "url",
    label: "Website / Link",
    hint: "Safely checks phishing, redirects & page text",
    useCase: "Paste any public website or social post link before clicking or reporting it.",
    icon: Globe,
  },
];

export default function AnalysisPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabType>("image");
  const [loading, setLoading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showTechDetails, setShowTechDetails] = useState(false);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [inputText, setInputText] = useState("");
  const [inputUrl, setInputUrl] = useState("");

  const activeConfig = TAB_CONFIG.find((t) => t.key === activeTab)!;

  const handleRunAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg(null);
    setAnalysisResult(null);

    try {
      let res: Response;
      if (activeTab === "text") {
        if (!inputText.trim()) throw new Error("Please paste or type some text to check.");
        res = await apiFetch("/analysis/text", {
          method: "POST",
          body: JSON.stringify({ text: inputText }),
        });
      } else if (activeTab === "url") {
        if (!inputUrl.trim()) throw new Error("Please enter a public website link to check.");
        res = await apiFetch("/analysis/url", {
          method: "POST",
          body: JSON.stringify({ url: inputUrl }),
        });
      } else {
        if (!selectedFile) throw new Error(`Please choose a ${activeTab} file first.`);
        const formData = new FormData();
        formData.append("file", selectedFile);
        res = await apiFetch(`/analysis/${activeTab}`, {
          method: "POST",
          body: formData,
        });
      }

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Scan could not be completed");
      }

      const data: AnalysisResult = await res.json();
      setAnalysisResult(data);
      setShowTechDetails(false);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "An unexpected error occurred during the scan.");
    } finally {
      setLoading(false);
    }
  };

  const getRiskDisplay = (level: string) => {
    switch (level?.toLowerCase()) {
      case "critical":
        return {
          label: "Critical Alert",
          badge: "bg-rose-500/20 text-rose-300 border-rose-500/40",
        };
      case "high":
        return {
          label: "High Risk Warning",
          badge: "bg-orange-500/20 text-orange-300 border-orange-500/40",
        };
      case "medium":
        return {
          label: "Needs Review",
          badge: "bg-amber-500/20 text-amber-300 border-amber-500/40",
        };
      default:
        return {
          label: "Low Risk / Safe",
          badge: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
        };
    }
  };

  const handleEscalateCase = () => {
    if (!analysisResult) return;
    const params = new URLSearchParams({
      prefill_title: `Incident Check (${activeConfig.label})`,
      risk: analysisResult.risk_level,
      description: analysisResult.explanation,
    });
    if (activeTab === "url" && inputUrl) {
      params.set("url", inputUrl);
    }
    router.push(`/cases?${params.toString()}`);
  };

  const ocrText =
    typeof analysisResult?.raw_metadata?.ocr_text === "string"
      ? analysisResult.raw_metadata.ocr_text
      : "";
  const transcriptSegments = Array.isArray(analysisResult?.raw_metadata?.transcript_segments)
    ? (analysisResult.raw_metadata.transcript_segments as Array<{ start: number; end: number; text: string }>)
    : [];

  return (
    <div className="space-y-7">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
          <ScanSearch className="w-6 h-6 text-cyan-400" />
          Check Content for Threats or Fake Info
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Pick what kind of content you have below, submit it, and get a clear safety breakdown with next steps.
        </p>
      </div>

      {/* Clean Minimal Type Selector */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
        {TAB_CONFIG.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => {
                setActiveTab(tab.key);
                setAnalysisResult(null);
                setErrorMsg(null);
              }}
              className={`text-left p-3 rounded-2xl border transition-all ${
                isActive
                  ? "border-cyan-500/60 bg-cyan-500/10 text-white shadow-sm"
                  : "border-slate-800/80 bg-slate-900/40 text-slate-400 hover:border-slate-700 hover:text-slate-200"
              }`}
            >
              <Icon className={`w-4 h-4 mb-2 ${isActive ? "text-cyan-400" : "text-slate-400"}`} />
              <div className="text-xs font-semibold leading-tight">{tab.label}</div>
              <div className="text-[10px] text-slate-500 mt-0.5 line-clamp-1">{tab.hint}</div>
            </button>
          );
        })}
      </div>

      {/* Main Split Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Input Card */}
        <div className="lg:col-span-5 minimal-card p-6 space-y-5">
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-cyan-400">Step 1 • Provide Content</span>
              <ActionHint title={activeConfig.label} description={activeConfig.useCase} />
            </div>
            <h2 className="text-base font-bold text-white">{activeConfig.label}</h2>
            <p className="text-xs text-slate-400">{activeConfig.useCase}</p>
          </div>

          <form onSubmit={handleRunAnalysis} className="space-y-4">
            {activeTab === "text" && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-medium text-slate-300">Paste message or post text</label>
                  <button
                    type="button"
                    onClick={() =>
                      setInputText("Official customer support here — verify your seed phrase or I will leak your photos.")
                    }
                    className="text-[11px] text-cyan-400 hover:underline"
                  >
                    Try sample text
                  </button>
                </div>
                <textarea
                  rows={6}
                  required
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  placeholder="Paste any suspicious DM, comment, email, or claim here..."
                  className="w-full p-3 rounded-xl border border-slate-800 bg-slate-950/90 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500"
                />
              </div>
            )}

            {activeTab === "url" && (
              <div className="space-y-2.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-medium text-slate-300">Website or Social Media Link</label>
                  <button
                    type="button"
                    onClick={() => setInputUrl("https://paypal-security-verify.xyz/login")}
                    className="text-[11px] text-cyan-400 hover:underline"
                  >
                    Try example link
                  </button>
                </div>
                <input
                  type="url"
                  required
                  value={inputUrl}
                  onChange={(e) => setInputUrl(e.target.value)}
                  placeholder="https://example.com/post-or-login-page"
                  className="w-full p-3 rounded-xl border border-slate-800 bg-slate-950/90 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500"
                />
                <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 text-[11px] text-slate-400 flex items-start gap-2">
                  <ShieldCheck className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                  <span>
                    Safe Inspection: Only checks public web links. Private/local network addresses are automatically blocked.
                  </span>
                </div>
              </div>
            )}

            {["image", "video", "audio"].includes(activeTab) && (
              <div className="space-y-2">
                <label className="block text-xs font-medium text-slate-300">
                  Choose a {activeTab} file from your device
                </label>
                <input
                  type="file"
                  required
                  accept={
                    activeTab === "image"
                      ? "image/*"
                      : activeTab === "video"
                      ? "video/*"
                      : "audio/*"
                  }
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-950/90 text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-cyan-500 file:text-slate-950 cursor-pointer"
                />
                <p className="text-[11px] text-slate-500">
                  Processed locally on your machine (up to 50MB). Executable files are automatically rejected.
                </p>
              </div>
            )}

            {errorMsg && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            <div className="space-y-2 pt-1">
              <button type="submit" disabled={loading} className="btn-primary w-full py-3">
                {loading ? "Scanning Content..." : "Scan & Check Safety"}
                <ArrowRight className="w-4 h-4" />
              </button>
              <p className="text-[11px] text-center text-slate-500">
                Runs local safety checks, text recognition, and hash verification.
              </p>
            </div>
          </form>
        </div>

        {/* Right: Results Card */}
        <div className="lg:col-span-7 minimal-card p-6 space-y-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-cyan-400">Step 2 • Safety Report & Next Actions</span>
            {analysisResult && (
              <span className="text-[11px] text-slate-500">
                {Math.round(analysisResult.confidence * 100)}% confidence
              </span>
            )}
          </div>

          {!analysisResult ? (
            <div className="rounded-xl border border-dashed border-slate-800 bg-slate-950/30 p-12 text-center text-slate-500 space-y-2">
              <ScanSearch className="w-8 h-8 mx-auto text-slate-600" />
              <p className="text-xs font-medium text-slate-400">Your scan results will appear here</p>
              <p className="text-[11px] text-slate-500 max-w-sm mx-auto">
                You will see a plain-English risk rating, specific warning flags found, and a button to turn it into an official removal case.
              </p>
            </div>
          ) : (
            <div className="space-y-5">
              {/* Risk Verdict Banner */}
              <div className="flex flex-wrap items-center justify-between gap-3 p-4 rounded-xl bg-slate-950/80 border border-slate-800">
                <div className="space-y-0.5">
                  <div className="text-[11px] text-slate-400">Overall Assessment</div>
                  <div className="text-base font-bold text-white">
                    {getRiskDisplay(analysisResult.risk_level).label}
                  </div>
                </div>
                <span
                  className={`px-3 py-1 rounded-full text-xs font-semibold uppercase border ${
                    getRiskDisplay(analysisResult.risk_level).badge
                  }`}
                >
                  {analysisResult.risk_level} risk
                </span>
              </div>

              {/* Plain-English Summary */}
              <div className="space-y-1.5">
                <h3 className="text-xs font-semibold text-slate-300">What We Found</h3>
                <p className="text-xs text-slate-300 leading-relaxed">{analysisResult.explanation}</p>
              </div>

              {/* Specific Warning Signals */}
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-slate-300">
                  Warning Indicators ({analysisResult.findings?.length || 0})
                </h3>
                {analysisResult.findings?.length === 0 ? (
                  <div className="p-3 rounded-xl bg-emerald-500/5 border border-emerald-500/20 text-xs text-emerald-300">
                    No harmful threats, scams, or policy-violation indicators were triggered.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {analysisResult.findings.map((f, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-xl border border-slate-800 bg-slate-950/50 text-xs space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-white">{f.category}</span>
                          <span className="text-[10px] font-semibold uppercase text-orange-400">
                            {f.severity}
                            {typeof f.timestamp_start === "number" ? ` • @${f.timestamp_start}s` : ""}
                          </span>
                        </div>
                        <p className="text-slate-400 text-[11px]">{f.description}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Recommended Next Step + Save as Case CTA */}
              <div className="p-4 rounded-xl bg-cyan-950/20 border border-cyan-500/25 space-y-3">
                <div className="space-y-1">
                  <div className="text-xs font-semibold text-cyan-300">What Should You Do Next?</div>
                  <p className="text-xs text-slate-200 leading-relaxed">{analysisResult.recommended_action}</p>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                  <span className="text-[11px] text-slate-400">
                    Save this result to attach screenshots and prepare a platform takedown PDF.
                  </span>
                  <button type="button" onClick={handleEscalateCase} className="btn-primary">
                    <Briefcase className="w-3.5 h-3.5" />
                    Save as Investigation Case
                  </button>
                </div>
              </div>

              {/* Collapsible Technical Forensic Evidence */}
              <div className="border-t border-slate-800 pt-3">
                <button
                  type="button"
                  onClick={() => setShowTechDetails((v) => !v)}
                  className="btn-ghost w-full justify-between px-2"
                >
                  <span>Technical Forensic Details (Hashes, OCR, Transcript & Limitations)</span>
                  {showTechDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>

                {showTechDetails && (
                  <div className="mt-3 space-y-4">
                    {ocrText && (
                      <div>
                        <div className="text-[11px] font-semibold text-slate-400 mb-1">Extracted Image Text (OCR)</div>
                        <pre className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-300 whitespace-pre-wrap max-h-32 overflow-y-auto">
                          {ocrText}
                        </pre>
                      </div>
                    )}

                    {transcriptSegments.length > 0 && (
                      <div>
                        <div className="text-[11px] font-semibold text-slate-400 mb-1">Audio Transcript (Whisper)</div>
                        <div className="space-y-1 bg-slate-950 p-3 rounded-xl border border-slate-800 max-h-36 overflow-y-auto">
                          {transcriptSegments.map((seg, i) => (
                            <div key={i} className="text-[11px] text-slate-300 flex gap-2">
                              <span className="font-mono text-cyan-400 shrink-0">
                                [{seg.start}s–{seg.end}s]
                              </span>
                              <span>{seg.text}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {analysisResult.evidence?.length > 0 && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {analysisResult.evidence.map((ev, idx) => (
                          <div key={idx} className="p-2.5 rounded-xl border border-slate-800 bg-slate-950/60 text-xs">
                            <div className="text-[10px] font-semibold text-cyan-400 uppercase">{ev.indicator}</div>
                            <div className="text-[11px] font-mono text-slate-200 truncate mt-0.5" title={String(ev.observed_value)}>
                              {String(ev.observed_value)}
                            </div>
                            <div className="text-[10px] text-slate-500 mt-1">{ev.interpretation}</div>
                          </div>
                        ))}
                      </div>
                    )}

                    {analysisResult.limitations?.length > 0 && (
                      <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 space-y-1">
                        <div className="text-[11px] font-semibold text-slate-300 flex items-center gap-1.5">
                          <Info className="w-3.5 h-3.5 text-amber-400" /> Limitations to Keep in Mind
                        </div>
                        <ul className="list-disc list-inside text-[11px] text-slate-400 space-y-0.5">
                          {analysisResult.limitations.map((lim, idx) => (
                            <li key={idx}>{lim}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
