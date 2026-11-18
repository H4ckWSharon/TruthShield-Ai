"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import type { CaseItem, EvidenceItem } from "@/types";
import { ActionHint } from "@/components/ActionHint";
import {
  Briefcase,
  PlusCircle,
  Search,
  FileCheck2,
  Trash2,
  ExternalLink,
  Lock,
  ChevronRight,
  X,
  Download,
  Pencil,
  Save,
  FileDown,
} from "lucide-react";

function CasesContent() {
  const searchParams = useSearchParams();
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCase, setSelectedCase] = useState<CaseItem | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Filters
  const [statusFilter, setStatusFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [riskFilter, setRiskFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");

  // Create Form State
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("deepfake");
  const [riskLevel, setRiskLevel] = useState("high");
  const [description, setDescription] = useState("");
  const [urlInput, setUrlInput] = useState("");

  // Edit Case State
  const [isEditingCase, setIsEditingCase] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [editRisk, setEditRisk] = useState("medium");
  const [editUrls, setEditUrls] = useState("");

  // Evidence state inside case drawer
  const [evidenceFile, setEvidenceFile] = useState<File | null>(null);
  const [evidenceDesc, setEvidenceDesc] = useState("");
  const [evidenceSensitive, setEvidenceSensitive] = useState(false);
  const [caseEvidenceList, setCaseEvidenceList] = useState<EvidenceItem[]>([]);
  const [uploadingEvidence, setUploadingEvidence] = useState(false);

  useEffect(() => {
    const prefillTitle = searchParams.get("prefill_title");
    if (prefillTitle) {
      setTitle(prefillTitle);
      const risk = searchParams.get("risk");
      if (risk) setRiskLevel(risk);
      const desc = searchParams.get("description");
      if (desc) setDescription(desc);
      const url = searchParams.get("url");
      if (url) setUrlInput(url);
      setShowCreateModal(true);
    }
  }, [searchParams]);

  const fetchCases = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.append("status", statusFilter);
      if (categoryFilter) params.append("category", categoryFilter);
      if (riskFilter) params.append("risk_level", riskFilter);
      if (searchQuery) params.append("search", searchQuery);

      const res = await apiFetch(`/cases?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setCases(data.items || []);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, categoryFilter, riskFilter, searchQuery]);

  useEffect(() => {
    fetchCases();
  }, [fetchCases]);

  const handleCreateCase = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const urls = urlInput
        .split("\n")
        .map((u) => u.trim())
        .filter((u) => u.length > 0);

      const res = await apiFetch("/cases", {
        method: "POST",
        body: JSON.stringify({
          title,
          category,
          risk_level: riskLevel,
          description,
          urls,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to create case");
      }

      setShowCreateModal(false);
      setTitle("");
      setDescription("");
      setUrlInput("");
      fetchCases();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to create case");
    }
  };

  const fetchCaseDetails = useCallback(async (caseId: string) => {
    try {
      const [caseRes, evRes] = await Promise.all([
        apiFetch(`/cases/${caseId}`),
        apiFetch(`/evidence?case_id=${encodeURIComponent(caseId)}`),
      ]);
      if (caseRes.ok) {
        const fullCase: CaseItem = await caseRes.json();
        setSelectedCase(fullCase);
        setEditTitle(fullCase.title);
        setEditDescription(fullCase.description || "");
        setEditNotes(fullCase.notes || "");
        setEditRisk(fullCase.risk_level);
        setEditUrls((fullCase.urls || []).join("\n"));
      }
      if (evRes.ok) {
        setCaseEvidenceList(await evRes.json());
      }
    } catch (e) {
      console.error(e);
    }
  }, []);

  const handleSelectCase = async (c: CaseItem) => {
    setSelectedCase(c);
    setIsEditingCase(false);
    setCaseEvidenceList([]);
    fetchCaseDetails(c.id);
  };

  const handleSaveCaseEdits = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCase) return;
    try {
      const urls = editUrls
        .split("\n")
        .map((u) => u.trim())
        .filter((u) => u.length > 0);
      const res = await apiFetch(`/cases/${selectedCase.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: editTitle,
          description: editDescription,
          notes: editNotes,
          risk_level: editRisk,
          urls,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to save edits");
      }
      const updated: CaseItem = await res.json();
      setSelectedCase(updated);
      setIsEditingCase(false);
      fetchCases();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Update failed");
    }
  };

  const handleUpdateStatus = async (newStatus: string) => {
    if (!selectedCase) return;
    try {
      const res = await apiFetch(`/cases/${selectedCase.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      });
      if (res.ok) {
        const updated: CaseItem = await res.json();
        setSelectedCase(updated);
        fetchCases();
      }
    } catch {
      alert("Failed to update status");
    }
  };

  const handleUploadEvidence = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!evidenceFile || !selectedCase) return;
    setUploadingEvidence(true);

    try {
      const formData = new FormData();
      formData.append("file", evidenceFile);
      formData.append("case_id", selectedCase.id);
      formData.append("description", evidenceDesc);
      formData.append("is_sensitive", String(evidenceSensitive));

      const res = await apiFetch("/evidence/upload", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Evidence upload failed");
      }

      const uploaded: EvidenceItem = await res.json();
      setCaseEvidenceList((prev) => [uploaded, ...prev]);
      setEvidenceFile(null);
      setEvidenceDesc("");
      fetchCases();
      alert(`Proof encrypted & saved! Integrity stamp: ${uploaded.sha256_hash.slice(0, 12)}...`);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploadingEvidence(false);
    }
  };

  const handleDownloadEvidence = async (ev: EvidenceItem) => {
    try {
      const res = await apiFetch(`/evidence/${ev.id}/download`);
      if (!res.ok) throw new Error("Failed to download proof file");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = ev.original_filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Download failed");
    }
  };

  const handleDeleteEvidence = async (evidenceId: string) => {
    if (!confirm("Permanently shred and delete this proof file?")) return;
    try {
      const res = await apiFetch(`/evidence/${evidenceId}`, { method: "DELETE" });
      if (res.ok) {
        setCaseEvidenceList((prev) => prev.filter((item) => item.id !== evidenceId));
        fetchCases();
      }
    } catch {
      alert("Failed to delete file");
    }
  };

  const handleExportCaseJson = async (caseItem: CaseItem) => {
    try {
      const res = await apiFetch(`/cases/${caseItem.id}/export`);
      if (!res.ok) throw new Error("Export failed");
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${caseItem.case_number}_backup.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Export failed");
    }
  };

  const handleDeleteCase = async (caseId: string) => {
    if (!confirm("Permanently delete this case?")) return;
    try {
      const res = await apiFetch(`/cases/${caseId}`, { method: "DELETE" });
      if (res.ok) {
        setSelectedCase(null);
        fetchCases();
      }
    } catch {
      alert("Failed to delete case");
    }
  };

  return (
    <div className="space-y-7">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <Briefcase className="w-6 h-6 text-cyan-400" />
            My Cases & Locked Proof
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Organize incidents, store encrypted screenshots or files, and click any case row to manage proof or start removal.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setShowCreateModal(true)}
          className="btn-primary self-start sm:self-auto"
          title="Open a new case to track links and attach proof"
        >
          <PlusCircle className="w-4 h-4" /> Create New Case
        </button>
      </div>

      {/* Filter & Search Bar */}
      <div className="minimal-card p-3 grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="relative">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search case ID or title..."
            className="w-full pl-9 pr-3 py-2 rounded-xl border border-slate-800 bg-slate-950/90 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500"
          />
        </div>

        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="px-3 py-2 rounded-xl border border-slate-800 bg-slate-950/90 text-xs text-white focus:outline-none focus:border-cyan-500"
        >
          <option value="">All Incident Types</option>
          <option value="ncii">Non-Consensual Intimate Content</option>
          <option value="deepfake">Deepfake / Manipulated Media</option>
          <option value="impersonation">Fake Profile / Impersonation</option>
          <option value="harassment">Harassment / Bullying</option>
          <option value="threats">Violent Threats</option>
          <option value="misinformation">Fake News / Misinformation</option>
          <option value="phishing">Phishing / Scam</option>
          <option value="other">Other Harmful Content</option>
        </select>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 rounded-xl border border-slate-800 bg-slate-950/90 text-xs text-white focus:outline-none focus:border-cyan-500"
        >
          <option value="">All Progress Stages</option>
          <option value="detected">Detected</option>
          <option value="pending_verification">Pending Verification</option>
          <option value="verified">Verified</option>
          <option value="report_prepared">Report Prepared</option>
          <option value="submitted">Submitted to Platform</option>
          <option value="under_review">Under Review</option>
          <option value="confirmed_removed">Confirmed Removed</option>
          <option value="rejected">Rejected</option>
          <option value="unresolved">Unresolved</option>
        </select>

        <select
          value={riskFilter}
          onChange={(e) => setRiskFilter(e.target.value)}
          className="px-3 py-2 rounded-xl border border-slate-800 bg-slate-950/90 text-xs text-white focus:outline-none focus:border-cyan-500"
        >
          <option value="">All Severity Levels</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      {/* Cases Table */}
      <div className="minimal-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/70 text-slate-400 text-[11px] font-medium border-b border-slate-800/80">
              <tr>
                <th className="px-5 py-3.5">Case ID</th>
                <th className="px-5 py-3.5">Incident Summary</th>
                <th className="px-5 py-3.5">Type</th>
                <th className="px-5 py-3.5">Risk</th>
                <th className="px-5 py-3.5">Progress</th>
                <th className="px-5 py-3.5">Proof Files</th>
                <th className="px-5 py-3.5 text-right">Open</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {loading ? (
                <tr>
                  <td colSpan={7} className="text-center py-10 text-slate-500">
                    Loading your cases...
                  </td>
                </tr>
              ) : cases.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-12 text-slate-500 space-y-2">
                    <div className="text-xs font-medium text-slate-400">No cases found</div>
                    <div className="text-[11px]">Click “Create New Case” above to save an incident and attach proof.</div>
                  </td>
                </tr>
              ) : (
                cases.map((c) => (
                  <tr
                    key={c.id}
                    onClick={() => handleSelectCase(c)}
                    className="hover:bg-slate-800/40 cursor-pointer transition"
                  >
                    <td className="px-5 py-3.5 font-mono font-semibold text-cyan-400">{c.case_number}</td>
                    <td className="px-5 py-3.5 max-w-xs">
                      <div className="font-semibold text-white truncate">{c.title}</div>
                      <div className="text-[11px] text-slate-400 truncate">{c.description || "No description"}</div>
                    </td>
                    <td className="px-5 py-3.5 capitalize text-slate-300">{c.category}</td>
                    <td className="px-5 py-3.5">
                      <span
                        className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                          c.risk_level === "critical"
                            ? "bg-rose-500/20 text-rose-300"
                            : c.risk_level === "high"
                            ? "bg-orange-500/20 text-orange-300"
                            : c.risk_level === "medium"
                            ? "bg-amber-500/20 text-amber-300"
                            : "bg-emerald-500/20 text-emerald-300"
                        }`}
                      >
                        {c.risk_level}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="inline-block px-2.5 py-0.5 rounded-full text-[10px] font-medium capitalize bg-slate-800 text-slate-200">
                        {c.status.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-slate-400">
                      {c.evidence_count || 0} file(s)
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <ChevronRight className="w-4 h-4 text-slate-500 inline" />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Case Detail Drawer */}
      {selectedCase && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex justify-end" onClick={() => setSelectedCase(null)}>
          <div
            className="w-full max-w-2xl bg-slate-900 border-l border-slate-800 h-full overflow-y-auto p-6 space-y-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between pb-4 border-b border-slate-800">
              <div>
                <span className="text-[11px] font-mono font-semibold text-cyan-400">
                  {selectedCase.case_number}
                </span>
                <h2 className="text-lg font-bold text-white mt-0.5">{selectedCase.title}</h2>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsEditingCase(!isEditingCase)}
                  className="btn-ghost text-xs"
                  title="Edit title, description, links, or notes"
                >
                  <Pencil className="w-3.5 h-3.5" /> Edit
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedCase(null)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {isEditingCase ? (
              <form onSubmit={handleSaveCaseEdits} className="p-4 rounded-xl border border-cyan-500/30 bg-slate-950/80 space-y-3">
                <div className="text-xs font-semibold text-cyan-400">Edit Case Information</div>
                <input
                  type="text"
                  required
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-900 text-xs text-white"
                />
                <select
                  value={editRisk}
                  onChange={(e) => setEditRisk(e.target.value)}
                  className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-900 text-xs text-white"
                >
                  <option value="critical">Critical Risk</option>
                  <option value="high">High Risk</option>
                  <option value="medium">Medium Risk</option>
                  <option value="low">Low Risk</option>
                </select>
                <textarea
                  rows={3}
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  placeholder="Describe what happened..."
                  className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-900 text-xs text-white"
                />
                <textarea
                  rows={2}
                  value={editUrls}
                  onChange={(e) => setEditUrls(e.target.value)}
                  placeholder="Links to offending posts (one per line)"
                  className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-900 text-xs text-white"
                />
                <textarea
                  rows={2}
                  value={editNotes}
                  onChange={(e) => setEditNotes(e.target.value)}
                  placeholder="Personal notes or platform ticket numbers..."
                  className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-900 text-xs text-white"
                />
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setIsEditingCase(false)}
                    className="btn-secondary"
                  >
                    Cancel
                  </button>
                  <button type="submit" className="btn-primary">
                    <Save className="w-3.5 h-3.5" /> Save Changes
                  </button>
                </div>
              </form>
            ) : (
              <div className="space-y-2 text-xs text-slate-300">
                <p className="leading-relaxed">{selectedCase.description || "No description recorded yet."}</p>
                {selectedCase.notes && (
                  <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 text-[11px] text-slate-400">
                    <strong className="text-slate-200">Notes:</strong> {selectedCase.notes}
                  </div>
                )}
              </div>
            )}

            {/* Status Tracker */}
            <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-4 space-y-2.5">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-semibold text-slate-200">Case Progress</span>
                <ActionHint description="Click any stage to update where this investigation currently stands." />
              </div>
              <div className="flex flex-wrap gap-1.5">
                {[
                  "detected",
                  "pending_verification",
                  "verified",
                  "report_prepared",
                  "submitted",
                  "under_review",
                  "confirmed_removed",
                  "rejected",
                  "unresolved",
                ].map((st) => (
                  <button
                    key={st}
                    type="button"
                    onClick={() => handleUpdateStatus(st)}
                    className={`px-2.5 py-1 rounded-lg text-[11px] font-medium capitalize transition ${
                      selectedCase.status === st
                        ? "bg-cyan-500 text-slate-950 font-semibold"
                        : "bg-slate-800/80 text-slate-400 hover:text-white"
                    }`}
                  >
                    {st.replace(/_/g, " ")}
                  </button>
                ))}
              </div>
            </div>

            {/* Links */}
            <div className="space-y-2">
              <h3 className="text-xs font-semibold text-slate-300">Reported Links</h3>
              {selectedCase.urls?.length === 0 ? (
                <p className="text-xs text-slate-500 italic">No links saved yet. Click Edit to add URLs.</p>
              ) : (
                <div className="space-y-1.5">
                  {selectedCase.urls?.map((url, idx) => (
                    <a
                      key={idx}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950/80 border border-slate-800 text-xs text-cyan-400 hover:underline"
                    >
                      <span className="truncate">{url}</span>
                      <ExternalLink className="w-3.5 h-3.5 shrink-0 ml-2" />
                    </a>
                  ))}
                </div>
              )}
            </div>

            {/* Locked Proof Upload */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <h3 className="text-xs font-semibold text-slate-200">
                    Locked Proof Vault ({caseEvidenceList.length})
                  </h3>
                  <ActionHint
                    title="Encrypted Proof Storage"
                    description="Files uploaded here are encrypted on your disk, sealed with a SHA-256 tamper-proof digest, and kept private."
                  />
                </div>
                <span className="text-[10px] text-slate-500">Encrypted at rest</span>
              </div>

              <form onSubmit={handleUploadEvidence} className="p-4 rounded-xl bg-slate-950/70 border border-slate-800 space-y-3">
                <input
                  type="file"
                  required
                  onChange={(e) => setEvidenceFile(e.target.files?.[0] || null)}
                  className="w-full text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-800 file:text-cyan-400 cursor-pointer"
                />

                <input
                  type="text"
                  value={evidenceDesc}
                  onChange={(e) => setEvidenceDesc(e.target.value)}
                  placeholder="Short note about this file (e.g., Screenshot taken Nov 17)"
                  className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-900 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500"
                />

                <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                  <label className="flex items-center gap-2 text-xs text-slate-400 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={evidenceSensitive}
                      onChange={(e) => setEvidenceSensitive(e.target.checked)}
                      className="rounded border-slate-800 bg-slate-900 text-cyan-500"
                    />
                    <Lock className="w-3.5 h-3.5 text-rose-400" />
                    Mark as private / sensitive media
                  </label>

                  <button type="submit" disabled={uploadingEvidence} className="btn-primary">
                    {uploadingEvidence ? "Locking Proof..." : "Upload & Lock Proof"}
                  </button>
                </div>
              </form>

              {caseEvidenceList.length > 0 && (
                <div className="space-y-2">
                  {caseEvidenceList.map((ev) => (
                    <div
                      key={ev.id}
                      className="p-3 rounded-xl border border-slate-800 bg-slate-950/80 flex items-center justify-between gap-3 text-xs"
                    >
                      <div className="min-w-0 space-y-0.5">
                        <div className="font-semibold text-white flex items-center gap-2 truncate">
                          <span className="truncate">{ev.original_filename}</span>
                          {ev.is_sensitive && (
                            <span className="px-1.5 py-0.2 rounded-full text-[9px] bg-rose-500/20 text-rose-300">
                              Private
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] font-mono text-slate-400 truncate">
                          Stamp: {ev.sha256_hash.slice(0, 16)}... • {Math.max(1, Math.round(ev.file_size / 1024))} KB
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        <button
                          type="button"
                          onClick={() => handleDownloadEvidence(ev)}
                          className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-400"
                          title="Download original file"
                        >
                          <Download className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteEvidence(ev.id)}
                          className="p-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400"
                          title="Permanently shred & delete file"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Footer Action Bar */}
            <div className="pt-4 border-t border-slate-800 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-4">
                <button
                  type="button"
                  onClick={() => handleDeleteCase(selectedCase.id)}
                  className="inline-flex items-center gap-1.5 text-xs text-rose-400 hover:underline"
                >
                  <Trash2 className="w-4 h-4" /> Delete Case
                </button>
                <button
                  type="button"
                  onClick={() => handleExportCaseJson(selectedCase)}
                  className="inline-flex items-center gap-1.5 text-xs text-slate-300 hover:text-cyan-400"
                  title="Download all case details and hashes as a JSON backup"
                >
                  <FileDown className="w-4 h-4" /> Export Backup (JSON)
                </button>
              </div>

              <Link href={`/removal?case_id=${selectedCase.id}`} className="btn-primary">
                <FileCheck2 className="w-4 h-4" /> Request Removal & PDF
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Create Case Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <div>
                <h2 className="text-base font-bold text-white">Create New Investigation Case</h2>
                <p className="text-[11px] text-slate-400">Save details here so you can attach proof and draft a removal report.</p>
              </div>
              <button type="button" onClick={() => setShowCreateModal(false)} className="text-slate-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateCase} className="space-y-3.5">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Case Title</label>
                <input
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g., Fake news Instagram post or Impersonation account"
                  className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-950 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Type of Issue</label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-950 text-xs text-white focus:outline-none focus:border-cyan-500"
                  >
                    <option value="ncii">Non-Consensual Intimate Media</option>
                    <option value="deepfake">Deepfake / Altered Media</option>
                    <option value="impersonation">Impersonation / Fake Account</option>
                    <option value="harassment">Harassment</option>
                    <option value="threats">Threats / Violence</option>
                    <option value="misinformation">Fake News / Misinformation</option>
                    <option value="phishing">Phishing / Scam</option>
                    <option value="other">Other Harmful Content</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Urgency / Risk</label>
                  <select
                    value={riskLevel}
                    onChange={(e) => setRiskLevel(e.target.value)}
                    className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-950 text-xs text-white focus:outline-none focus:border-cyan-500"
                  >
                    <option value="critical">Critical (Immediate Harm)</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">What happened?</label>
                <textarea
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Briefly describe the post, account, or why this content should be removed..."
                  className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-950 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Links to the offending content (one per line)
                </label>
                <textarea
                  rows={2}
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  placeholder="https://instagram.com/p/..."
                  className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-950 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="pt-3 border-t border-slate-800 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button type="submit" className="btn-primary">
                  Save & Open Case
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default function CasesPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-xs text-slate-500">Loading your cases...</div>}>
      <CasesContent />
    </Suspense>
  );
}
