"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import type { CaseItem, RemovalWorkflowItem, ReportItem } from "@/types";
import { ActionHint } from "@/components/ActionHint";
import {
  FileCheck2,
  Download,
  ExternalLink,
  FileText,
  UserCheck,
  RefreshCw,
} from "lucide-react";

interface UrlVerificationResult {
  url: string;
  http_status?: number | null;
  verification_status: string;
  confirmed_removed: boolean;
  detail: string;
}

function RemovalContent() {
  const searchParams = useSearchParams();
  const initialCaseId = searchParams.get("case_id") || "";

  const [cases, setCases] = useState<CaseItem[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState(initialCaseId);
  const [platform, setPlatform] = useState("instagram");
  const [violationType, setViolationType] = useState("ncii");
  const [loading, setLoading] = useState(false);

  const [preparedWorkflow, setPreparedWorkflow] = useState<RemovalWorkflowItem | null>(null);
  const [submissionRef, setSubmissionRef] = useState("");
  const [approvalNotes, setApprovalNotes] = useState("");
  const [submittingApproval, setSubmittingApproval] = useState(false);

  const [verifyingUrls, setVerifyingUrls] = useState(false);
  const [urlChecks, setUrlChecks] = useState<UrlVerificationResult[] | null>(null);

  const [reports, setReports] = useState<ReportItem[]>([]);
  const [generatingPdf, setGeneratingPdf] = useState(false);

  const fetchCases = useCallback(async () => {
    try {
      const res = await apiFetch("/cases?limit=100");
      if (res.ok) {
        const data = await res.json();
        const items: CaseItem[] = data.items || [];
        setCases(items);
        if (!initialCaseId && items.length > 0) {
          setSelectedCaseId((prev) => prev || items[0].id);
        }
      }
    } catch (e) {
      console.error(e);
    }
  }, [initialCaseId]);

  const fetchReports = useCallback(async () => {
    try {
      const res = await apiFetch("/reports");
      if (res.ok) {
        setReports(await res.json());
      }
    } catch (e) {
      console.error(e);
    }
  }, []);

  const fetchWorkflowsForCase = useCallback(async (caseId: string) => {
    try {
      const res = await apiFetch(`/removal/status/${caseId}`);
      if (res.ok) {
        const data: RemovalWorkflowItem[] = await res.json();
        setPreparedWorkflow(data.length > 0 ? data[0] : null);
      }
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    fetchCases();
    fetchReports();
  }, [fetchCases, fetchReports]);

  useEffect(() => {
    if (selectedCaseId) {
      setUrlChecks(null);
      fetchWorkflowsForCase(selectedCaseId);
    }
  }, [selectedCaseId, fetchWorkflowsForCase]);

  const handlePrepareDossier = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCaseId) {
      alert("Please create or select an investigation case first.");
      return;
    }
    setLoading(true);

    try {
      const res = await apiFetch("/removal/prepare-report", {
        method: "POST",
        body: JSON.stringify({
          case_id: selectedCaseId,
          platform,
          violation_type: violationType,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to prepare removal request");
      }

      const wf: RemovalWorkflowItem = await res.json();
      setPreparedWorkflow(wf);
      alert("Takedown message drafted! Follow the steps on the right to submit it to the platform.");
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to prepare request");
    } finally {
      setLoading(false);
    }
  };

  const handleApproveWorkflow = async (approved: boolean) => {
    if (!preparedWorkflow) return;
    setSubmittingApproval(true);

    try {
      const res = await apiFetch("/removal/approve", {
        method: "POST",
        body: JSON.stringify({
          workflow_id: preparedWorkflow.id,
          approved,
          submission_reference: submissionRef,
          notes: approvalNotes,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Approval update failed");
      }

      const updated: RemovalWorkflowItem = await res.json();
      setPreparedWorkflow(updated);
      fetchCases();
      alert(approved ? "Marked as Submitted! Your tracking ticket is saved." : "Draft marked as Rejected.");
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Update failed");
    } finally {
      setSubmittingApproval(false);
    }
  };

  const handleVerifyLiveUrls = async () => {
    if (!selectedCaseId) return;
    setVerifyingUrls(true);
    setUrlChecks(null);
    try {
      const res = await apiFetch(`/removal/verify-url/${selectedCaseId}`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Verification failed");
      }
      const data = await res.json();
      setUrlChecks(data.results || []);
      fetchCases();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Verification failed");
    } finally {
      setVerifyingUrls(false);
    }
  };

  const handleGeneratePdf = async () => {
    if (!selectedCaseId) {
      alert("Please select a case first.");
      return;
    }
    setGeneratingPdf(true);

    try {
      const res = await apiFetch("/reports/generate", {
        method: "POST",
        body: JSON.stringify({
          case_id: selectedCaseId,
          template_type: platform,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "PDF generation failed");
      }

      const newReport: ReportItem = await res.json();
      setReports((prev) => [newReport, ...prev]);
      alert("Official PDF Report generated! Click Download PDF below to save it.");
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "PDF generation failed");
    } finally {
      setGeneratingPdf(false);
    }
  };

  const handleDownloadPdf = async (reportId: string, filename: string) => {
    try {
      const res = await apiFetch(`/reports/${reportId}/download`);
      if (!res.ok) throw new Error("Download failed");

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename || `TruthShield_Report_${reportId.slice(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Download failed");
    }
  };

  return (
    <div className="space-y-7">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
          <FileCheck2 className="w-6 h-6 text-cyan-400" />
          Request Content Removal & Download PDFs
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Only the website or social platform can delete a post from their servers. TruthShield prepares your official message, compiles a PDF report, links you to the platform form, and checks when the post goes down.
        </p>
      </div>

      {/* 4-Step Visual Guide Strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { num: "1", title: "Choose Case & Platform", desc: "Pick your saved case and where it's posted" },
          { num: "2", title: "Draft Notice & PDF", desc: "Generate the formal takedown text & PDF" },
          { num: "3", title: "Submit on Platform", desc: "Open the official link & paste your report" },
          { num: "4", title: "Verify Removal", desc: "Check live if the link returns 404 / removed" },
        ].map((step) => (
          <div key={step.num} className="minimal-card p-3.5 flex items-start gap-3">
            <span className="w-6 h-6 rounded-full bg-cyan-500/15 border border-cyan-500/30 text-cyan-300 text-xs font-bold flex items-center justify-center shrink-0">
              {step.num}
            </span>
            <div>
              <div className="text-xs font-semibold text-white">{step.title}</div>
              <div className="text-[11px] text-slate-400 mt-0.5">{step.desc}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Generator & Controls */}
        <div className="lg:col-span-5 minimal-card p-6 space-y-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-white">Step 1 & 2 • Prepare Takedown & PDF</h2>
            <ActionHint
              title="Why Manual Approval?"
              description="Platforms ban automated spam bots. TruthShield prepares your legal notice and lets you review and submit it directly through the platform's trusted safety form."
            />
          </div>

          <form onSubmit={handlePrepareDossier} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Which Case Is This For?</label>
              <select
                value={selectedCaseId}
                onChange={(e) => setSelectedCaseId(e.target.value)}
                className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-950/90 text-xs text-white focus:outline-none focus:border-cyan-500"
              >
                {cases.length === 0 ? (
                  <option value="">No cases yet — create one under “My Cases & Proof”</option>
                ) : (
                  cases.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.case_number} — {c.title} ({c.status.replace(/_/g, " ")})
                    </option>
                  ))
                )}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Where Is It Posted?</label>
              <select
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
                className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-950/90 text-xs text-white focus:outline-none focus:border-cyan-500"
              >
                <option value="instagram">Instagram</option>
                <option value="youtube">YouTube</option>
                <option value="facebook">Facebook</option>
                <option value="general_web">Website / Hosting Provider</option>
                <option value="incident">Police / Cybersecurity Incident Report</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Reason for Removal</label>
              <select
                value={violationType}
                onChange={(e) => setViolationType(e.target.value)}
                className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-950/90 text-xs text-white focus:outline-none focus:border-cyan-500"
              >
                <option value="ncii">Non-Consensual Intimate Content</option>
                <option value="deepfake">Deepfake / Manipulated Media</option>
                <option value="impersonation">Fake Account / Impersonation</option>
                <option value="harassment">Harassment & Bullying</option>
                <option value="misinformation">Fake News / Misinformation</option>
                <option value="copyright">Copyright / Stolen Content (DMCA)</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <button
                type="submit"
                disabled={loading || !selectedCaseId}
                className="btn-primary w-full py-2.5"
              >
                {loading ? "Preparing Notice..." : "Create Removal Request"}
              </button>
              <p className="text-[11px] text-center text-slate-500">
                Drafts the message & opens the platform submission checklist on the right.
              </p>
            </div>
          </form>

          <div className="pt-4 border-t border-slate-800 space-y-2.5">
            <div>
              <button
                type="button"
                onClick={handleGeneratePdf}
                disabled={generatingPdf || !selectedCaseId}
                className="btn-secondary w-full"
                title="Creates a clean PDF report with your case links and SHA-256 hashes"
              >
                <FileText className="w-4 h-4 text-cyan-400" />
                {generatingPdf ? "Building PDF..." : "Generate Official PDF Report"}
              </button>
              <p className="text-[10px] text-center text-slate-500 mt-1">
                Creates a downloadable PDF you can attach to support forms or legal notices.
              </p>
            </div>

            <div>
              <button
                type="button"
                onClick={handleVerifyLiveUrls}
                disabled={verifyingUrls || !selectedCaseId}
                className="btn-ghost w-full border border-cyan-500/30 text-cyan-300"
                title="Pings the target link right now to check if it still responds HTTP 200 or 404/Removed"
              >
                <RefreshCw className={`w-4 h-4 ${verifyingUrls ? "animate-spin" : ""}`} />
                {verifyingUrls ? "Checking Live Link..." : "Check If Post Is Still Live"}
              </button>
              <p className="text-[10px] text-center text-slate-500 mt-1">
                Verifies live whether the post is still online or has actually been removed.
              </p>
            </div>
          </div>

          {urlChecks && (
            <div className="p-3.5 rounded-xl border border-slate-800 bg-slate-950/80 space-y-2">
              <div className="text-xs font-semibold text-slate-200">Live Link Check Results</div>
              {urlChecks.map((chk, idx) => (
                <div key={idx} className="text-[11px] border-t border-slate-800/80 pt-2 space-y-0.5">
                  <div className="font-mono text-slate-300 truncate">{chk.url}</div>
                  <div className={chk.confirmed_removed ? "text-emerald-400 font-semibold" : "text-amber-400 font-medium"}>
                    {chk.confirmed_removed ? "Confirmed Removed" : "Still Online"} — {chk.detail}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: Guided Portal & PDF Archive */}
        <div className="lg:col-span-7 space-y-6">
          <div className="minimal-card p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-white">Step 3 & 4 • Review, Submit & Track</h2>
              {preparedWorkflow && (
                <span
                  className={`px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                    preparedWorkflow.human_approved
                      ? "bg-emerald-500/20 text-emerald-300"
                      : "bg-amber-500/20 text-amber-300"
                  }`}
                >
                  {preparedWorkflow.human_approved ? "Submitted" : "Waiting for Your Review"}
                </span>
              )}
            </div>

            {!preparedWorkflow ? (
              <div className="rounded-xl border border-dashed border-slate-800 bg-slate-950/30 p-10 text-center text-slate-500 space-y-1.5">
                <p className="text-xs font-medium text-slate-400">No removal draft prepared for this case yet</p>
                <p className="text-[11px]">Select your platform on the left and click “Create Removal Request”.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {preparedWorkflow.official_portal_url && (
                  <div className="p-3.5 rounded-xl bg-cyan-950/25 border border-cyan-500/30 flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="text-xs font-semibold text-white">Official {preparedWorkflow.platform.toUpperCase()} Reporting Link</div>
                      <div className="text-[11px] text-cyan-300">Open this official page to submit your drafted notice</div>
                    </div>
                    <a
                      href={preparedWorkflow.official_portal_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn-primary"
                    >
                      Open Official Form <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </div>
                )}

                {preparedWorkflow.guidance_steps && (
                  <div className="space-y-1.5">
                    <h3 className="text-xs font-semibold text-slate-300">Follow These Steps</h3>
                    <div className="space-y-1.5 bg-slate-950/70 p-3.5 rounded-xl border border-slate-800">
                      {preparedWorkflow.guidance_steps.map((step, idx) => (
                        <p key={idx} className="text-xs text-slate-300 leading-relaxed">
                          {step}
                        </p>
                      ))}
                    </div>
                  </div>
                )}

                <div className="space-y-1.5">
                  <h3 className="text-xs font-semibold text-slate-300">Ready-to-Copy Notice Message</h3>
                  <pre className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-[11px] text-slate-300 font-mono whitespace-pre-wrap max-h-44 overflow-y-auto">
                    {preparedWorkflow.report_content}
                  </pre>
                </div>

                <div className="p-4 rounded-xl bg-slate-950/70 border border-slate-800 space-y-3">
                  <div className="flex items-center gap-2 text-xs font-semibold text-white">
                    <UserCheck className="w-4 h-4 text-cyan-400" /> Mark As Submitted
                    <ActionHint description="Once you submit the form on the platform, paste any confirmation or ticket number here so you can track it." />
                  </div>

                  <input
                    type="text"
                    value={submissionRef}
                    onChange={(e) => setSubmissionRef(e.target.value)}
                    placeholder="Platform Ticket / Reference Number (optional)"
                    className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-900 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500"
                  />

                  <input
                    type="text"
                    value={approvalNotes}
                    onChange={(e) => setApprovalNotes(e.target.value)}
                    placeholder="Reviewer notes (e.g., Submitted via Instagram Safety Center)"
                    className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-900 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500"
                  />

                  <div className="flex flex-wrap items-center justify-end gap-2.5 pt-1">
                    <button
                      type="button"
                      onClick={() => handleApproveWorkflow(false)}
                      disabled={submittingApproval}
                      className="btn-ghost text-rose-300 border border-rose-500/30"
                    >
                      Discard Draft
                    </button>
                    <button
                      type="button"
                      onClick={() => handleApproveWorkflow(true)}
                      disabled={submittingApproval}
                      className="btn-primary"
                    >
                      Confirm & Mark Submitted
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Generated PDF Reports */}
          <div className="minimal-card p-6 space-y-4">
            <h3 className="text-sm font-bold text-white">
              Generated PDF Reports ({reports.length})
            </h3>

            {reports.length === 0 ? (
              <p className="text-xs text-slate-500 italic py-3">
                No PDFs generated yet. Click “Generate Official PDF Report” on the left to build one.
              </p>
            ) : (
              <div className="space-y-2">
                {reports.map((r) => (
                  <div
                    key={r.id}
                    className="p-3.5 rounded-xl border border-slate-800 bg-slate-950/70 flex flex-wrap items-center justify-between gap-3 text-xs"
                  >
                    <div>
                      <div className="font-semibold text-white">{r.title}</div>
                      <div className="text-[11px] text-slate-400">
                        Template: <span className="uppercase text-cyan-400">{r.template_type}</span> •{" "}
                        {new Date(r.created_at).toLocaleDateString()}
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleDownloadPdf(r.id, `${r.title.replace(/\s+/g, "_")}.pdf`)}
                      className="btn-secondary"
                    >
                      <Download className="w-3.5 h-3.5 text-cyan-400" /> Download PDF
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function RemovalPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-xs text-slate-500">Loading Removal Center...</div>}>
      <RemovalContent />
    </Suspense>
  );
}
