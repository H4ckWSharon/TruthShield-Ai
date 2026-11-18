"use client";

import React, { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import type { FingerprintItem, FingerprintMatch, DuplicateMatchItem } from "@/types";
import { ActionHint } from "@/components/ActionHint";
import {
  Fingerprint,
  PlusCircle,
  Search,
  Trash2,
  AlertTriangle,
} from "lucide-react";

export default function FingerprintsPage() {
  const [fingerprints, setFingerprints] = useState<FingerprintItem[]>([]);
  const [matchHistory, setMatchHistory] = useState<DuplicateMatchItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showRegisterModal, setShowRegisterModal] = useState(false);

  const [regFile, setRegFile] = useState<File | null>(null);
  const [regTitle, setRegTitle] = useState("");
  const [regDesc, setRegDesc] = useState("");
  const [regMediaType, setRegMediaType] = useState("image");
  const [registering, setRegistering] = useState(false);

  const [searchFile, setSearchFile] = useState<File | null>(null);
  const [searchPHash, setSearchPHash] = useState("");
  const [searchOcrText, setSearchOcrText] = useState("");
  const [maxDistance, setMaxDistance] = useState(10);
  const [searchResults, setSearchResults] = useState<FingerprintMatch[] | null>(null);
  const [searching, setSearching] = useState(false);

  const fetchVaultData = useCallback(async () => {
    setLoading(true);
    try {
      const [fpRes, matchRes] = await Promise.all([
        apiFetch("/fingerprints"),
        apiFetch("/fingerprints/matches?limit=20"),
      ]);
      if (fpRes.ok) setFingerprints(await fpRes.json());
      if (matchRes.ok) setMatchHistory(await matchRes.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchVaultData();
  }, [fetchVaultData]);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!regFile) return;
    setRegistering(true);

    try {
      const formData = new FormData();
      formData.append("file", regFile);
      formData.append("title", regTitle);
      formData.append("description", regDesc);
      formData.append("media_type", regMediaType);

      const res = await apiFetch("/fingerprints/register", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Could not protect media");
      }

      setShowRegisterModal(false);
      setRegFile(null);
      setRegTitle("");
      setRegDesc("");
      fetchVaultData();
      alert("Original asset signature saved! TruthShield can now catch exact or edited re-uploads.");
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setRegistering(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setSearching(true);
    setSearchResults(null);

    try {
      const formData = new FormData();
      if (searchFile) formData.append("file", searchFile);
      if (searchPHash) formData.append("phash", searchPHash);
      if (searchOcrText) formData.append("ocr_text", searchOcrText);
      formData.append("max_distance", String(maxDistance));

      const res = await apiFetch("/fingerprints/search", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Search failed");
      }

      const matches: FingerprintMatch[] = await res.json();
      setSearchResults(matches);
      fetchVaultData();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Search failed");
    } finally {
      setSearching(false);
    }
  };

  const handleDeleteFingerprint = async (fpId: string) => {
    if (!confirm("Remove this protected signature?")) return;
    try {
      const res = await apiFetch(`/fingerprints/${fpId}`, { method: "DELETE" });
      if (res.ok) fetchVaultData();
    } catch {
      alert("Failed to remove fingerprint");
    }
  };

  const sensitivityLabel =
    maxDistance <= 3 ? "Strict (Near-Exact)" : maxDistance <= 10 ? "Balanced (Catches Edits)" : "Broad (Catches Heavy Crops)";

  return (
    <div className="space-y-7">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <Fingerprint className="w-6 h-6 text-cyan-400" />
            Protect Originals & Catch Copies
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Save a private digital signature of your photos, videos, or audio so you can spot exact or edited copies later.
          </p>
        </div>

        <button
          type="button"
          onClick={() => setShowRegisterModal(true)}
          className="btn-primary self-start sm:self-auto"
          title="Save a digital signature of your original file"
        >
          <PlusCircle className="w-4 h-4" /> Protect Original Media
        </button>
      </div>

      {/* Check for Copies Card */}
      <div className="minimal-card p-6 space-y-5">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <Search className="w-4 h-4 text-cyan-400" /> Check If a Suspect File Matches Your Originals
              <ActionHint
                title="How Similarity Matching Works"
                description="Upload any suspicious image, video, or audio file. Even if someone cropped, resized, or re-compressed your original, perceptual hashing still spots the match."
              />
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Upload a suspect file (or paste text/hash) to compare against all protected originals below.
            </p>
          </div>
        </div>

        <form onSubmit={handleSearch} className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
          <div className="md:col-span-4">
            <label className="block text-xs font-medium text-slate-300 mb-1">Upload Suspect File</label>
            <input
              type="file"
              accept="image/*,video/*,audio/*"
              onChange={(e) => setSearchFile(e.target.files?.[0] || null)}
              className="w-full text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-800 file:text-cyan-400 cursor-pointer"
            />
          </div>

          <div className="md:col-span-3">
            <label className="block text-xs font-medium text-slate-300 mb-1">Or Search Embedded Text</label>
            <input
              type="text"
              value={searchOcrText}
              onChange={(e) => setSearchOcrText(e.target.value)}
              placeholder="Words visible in the media..."
              className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-950/90 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500"
            />
          </div>

          <div className="md:col-span-3">
            <label className="block text-xs font-medium text-slate-300 mb-1">Or Hash Code (Optional)</label>
            <input
              type="text"
              value={searchPHash}
              onChange={(e) => setSearchPHash(e.target.value)}
              placeholder="e.g. e3a1c8f07b42..."
              className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-950/90 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500 font-mono"
            />
          </div>

          <div className="md:col-span-2">
            <label className="block text-[11px] font-medium text-slate-300 mb-1">
              Sensitivity: <span className="text-cyan-400">{sensitivityLabel}</span>
            </label>
            <input
              type="range"
              min="0"
              max="20"
              value={maxDistance}
              onChange={(e) => setMaxDistance(Number(e.target.value))}
              className="w-full accent-cyan-500 cursor-pointer"
            />
          </div>

          <div className="md:col-span-12 flex justify-end">
            <button type="submit" disabled={searching} className="btn-primary">
              {searching ? "Checking Protected Library..." : "Check for Copies"}
            </button>
          </div>
        </form>

        {searchResults !== null && (
          <div className="pt-4 border-t border-slate-800 space-y-3">
            <h3 className="text-xs font-semibold text-slate-300">
              Results ({searchResults.length} match{searchResults.length === 1 ? "" : "es"} found)
            </h3>
            {searchResults.length === 0 ? (
              <p className="text-xs text-slate-500 italic">
                No matching protected originals found at this sensitivity level.
              </p>
            ) : (
              <div className="space-y-2">
                {searchResults.map((m) => (
                  <div
                    key={m.id}
                    className="p-3.5 rounded-xl border border-slate-800 bg-slate-950/80 flex items-center justify-between text-xs"
                  >
                    <div className="space-y-0.5">
                      <div className="font-semibold text-white flex items-center gap-2">
                        {m.title}
                        <span
                          className={`px-2 py-0.2 rounded-full text-[10px] font-semibold uppercase ${
                            m.match_type === "exact"
                              ? "bg-rose-500/20 text-rose-300"
                              : "bg-amber-500/20 text-amber-300"
                          }`}
                        >
                          {m.match_type} match
                        </span>
                      </div>
                      <div className="text-[11px] font-mono text-slate-400 truncate max-w-md">
                        SHA-256: {m.sha256_hash.slice(0, 24)}...
                      </div>
                    </div>

                    <div className="text-right">
                      <div className="text-sm font-bold text-cyan-400">
                        {Math.round(m.similarity_score * 100)}% Match
                      </div>
                      <div className="text-[10px] text-slate-500">
                        Difference: {m.hamming_distance} bits
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Protected Originals Grid */}
      <div className="minimal-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-white">
            Your Protected Originals ({fingerprints.length})
          </h2>
          <span className="text-[11px] text-slate-500">Stored privately on this machine</span>
        </div>

        {loading ? (
          <p className="text-xs text-slate-500 py-6 text-center">Loading protected originals...</p>
        ) : fingerprints.length === 0 ? (
          <div className="text-center py-10 text-slate-500 space-y-2">
            <Fingerprint className="w-8 h-8 mx-auto text-slate-600" />
            <p className="text-xs text-slate-400">No originals protected yet.</p>
            <p className="text-[11px]">Click “Protect Original Media” at the top right to save your first digital signature.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {fingerprints.map((fp) => {
              const ocrSnippet = typeof fp.metadata_json?.ocr_text === "string" ? fp.metadata_json.ocr_text : "";
              return (
                <div
                  key={fp.id}
                  className="p-4 rounded-xl border border-slate-800 bg-slate-950/40 text-xs space-y-2.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-white truncate max-w-[180px]">{fp.title}</span>
                    <div className="flex items-center gap-1.5">
                      <span className="px-2 py-0.5 rounded-full text-[10px] uppercase bg-slate-800 text-slate-300">
                        {fp.media_type}
                      </span>
                      <button
                        type="button"
                        onClick={() => handleDeleteFingerprint(fp.id)}
                        className="p-1 rounded text-slate-500 hover:text-rose-400"
                        title="Delete signature"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  <div className="space-y-1 font-mono text-[11px] bg-slate-900/70 p-2.5 rounded-lg border border-slate-800/80">
                    <div className="text-slate-400 truncate">
                      <strong className="text-cyan-400">Visual ID:</strong> {fp.phash || "N/A"}
                    </div>
                    <div className="text-slate-400 truncate">
                      <strong className="text-cyan-400">Exact Hash:</strong> {fp.sha256_hash.slice(0, 14)}...
                    </div>
                    {ocrSnippet && (
                      <div className="text-slate-400 truncate" title={ocrSnippet}>
                        <strong className="text-cyan-400">Text Found:</strong> {ocrSnippet}
                      </div>
                    )}
                  </div>

                  {fp.description && (
                    <p className="text-[11px] text-slate-400 truncate">{fp.description}</p>
                  )}

                  <div className="text-[10px] text-slate-500 pt-1 border-t border-slate-800/70">
                    Saved {new Date(fp.created_at).toLocaleDateString()}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Match History */}
      <div className="minimal-card p-6 space-y-3">
        <h2 className="text-sm font-bold text-white flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400" /> Detected Copy Alerts ({matchHistory.length})
        </h2>

        {matchHistory.length === 0 ? (
          <p className="text-xs text-slate-500 italic py-3">No duplicate matches detected yet.</p>
        ) : (
          <div className="space-y-2">
            {matchHistory.map((dm) => (
              <div
                key={dm.id}
                className="p-3 rounded-xl border border-slate-800 bg-slate-950/60 flex items-center justify-between text-xs"
              >
                <div>
                  <div className="font-semibold text-white">
                    Matched “{dm.matched_title}”{" "}
                    <span className="ml-1.5 px-2 py-0.2 rounded-full text-[10px] uppercase bg-amber-500/20 text-amber-300">
                      {dm.match_type}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Checked file: {String(dm.details?.evidence_filename || dm.details?.source_label || dm.source_id.slice(0, 8))}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-bold text-cyan-400">{Math.round(dm.similarity_score * 100)}% Match</div>
                  <div className="text-[10px] text-slate-500">{new Date(dm.detected_at).toLocaleString()}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Register Modal */}
      {showRegisterModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl space-y-4">
            <div>
              <h2 className="text-base font-bold text-white">Protect Original Media</h2>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Creates a private signature of your original file to recognize re-uploads later.
              </p>
            </div>

            <form onSubmit={handleRegister} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Give this original a name</label>
                <input
                  type="text"
                  required
                  value={regTitle}
                  onChange={(e) => setRegTitle(e.target.value)}
                  placeholder="e.g., Official Company Logo or Personal Photo"
                  className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-950 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Media Type</label>
                <select
                  value={regMediaType}
                  onChange={(e) => setRegMediaType(e.target.value)}
                  className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-950 text-xs text-white focus:outline-none focus:border-cyan-500"
                >
                  <option value="image">Image (Visual & Text Signature)</option>
                  <option value="video">Video (Keyframe Signatures)</option>
                  <option value="audio">Audio (Sound Signature)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Choose Original File</label>
                <input
                  type="file"
                  required
                  accept="image/*,video/*,audio/*"
                  onChange={(e) => setRegFile(e.target.files?.[0] || null)}
                  className="w-full text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-cyan-500 file:text-slate-950 cursor-pointer"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Ownership Note (Optional)</label>
                <textarea
                  rows={2}
                  value={regDesc}
                  onChange={(e) => setRegDesc(e.target.value)}
                  placeholder="Who owns this file or why it is protected..."
                  className="w-full p-2.5 rounded-xl border border-slate-800 bg-slate-950 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="pt-3 border-t border-slate-800 flex justify-end gap-3">
                <button type="button" onClick={() => setShowRegisterModal(false)} className="btn-secondary">
                  Cancel
                </button>
                <button type="submit" disabled={registering} className="btn-primary">
                  {registering ? "Creating Signature..." : "Save Signature"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
