"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/authContext";
import { apiFetch } from "@/lib/api";
import type { DashboardStats } from "@/types";
import { ActionHint } from "@/components/ActionHint";
import {
  FileSearch,
  Briefcase,
  FileCheck2,
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  ScanSearch,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export default function DashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const res = await apiFetch("/dashboard/stats");
      if (!res.ok) {
        throw new Error(`Dashboard metrics unavailable (HTTP ${res.status})`);
      }
      const data: DashboardStats = await res.json();
      setStats(data);
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : "Failed to load dashboard metrics");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [user, fetchStats]);

  const quickActions = [
    {
      step: "Step 1",
      title: "Check Content",
      description: "Scan a photo, video, audio clip, text message, or website link for scams, threats, or hidden text.",
      buttonLabel: "Scan Content",
      href: "/analysis",
      icon: ScanSearch,
      accent: "text-cyan-400 bg-cyan-500/10",
    },
    {
      step: "Step 2",
      title: "Save Case & Proof",
      description: "Open an investigation case, track suspicious links, and lock screenshots or files with encryption.",
      buttonLabel: "Manage Cases",
      href: "/cases",
      icon: Briefcase,
      accent: "text-blue-400 bg-blue-500/10",
    },
    {
      step: "Step 3",
      title: "Request Removal",
      description: "Create an official PDF report, follow guided platform reporting steps, and verify if a post was removed.",
      buttonLabel: "Removal & PDFs",
      href: "/removal",
      icon: FileCheck2,
      accent: "text-emerald-400 bg-emerald-500/10",
    },
  ];

  const primaryKpis = [
    {
      label: "Total Cases",
      hint: "Active and archived incidents opened in your workspace.",
      value: stats?.total_cases ?? 0,
      icon: Briefcase,
      color: "text-blue-400",
    },
    {
      label: "Content Scanned",
      hint: "Total images, videos, audio clips, texts, and links analyzed.",
      value: stats?.content_analyzed ?? 0,
      icon: FileSearch,
      color: "text-cyan-400",
    },
    {
      label: "High-Priority Alerts",
      hint: "Cases rated High or Critical risk requiring attention.",
      value: stats?.high_risk_cases ?? 0,
      icon: AlertTriangle,
      color: "text-rose-400",
    },
    {
      label: "Confirmed Removals",
      hint: "Cases verified offline (HTTP 404/410) after removal.",
      value: stats?.confirmed_removal_cases ?? 0,
      icon: ShieldCheck,
      color: "text-emerald-400",
    },
  ];

  return (
    <div className="space-y-8">
      {/* Minimal Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            Content Protection Overview
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Inspect suspicious content, store encrypted proof, and track official takedowns in three simple steps.
          </p>
        </div>

        <button
          type="button"
          onClick={fetchStats}
          className="btn-ghost self-start sm:self-auto border border-slate-800/80"
          title="Reload live database numbers"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh Stats
        </button>
      </div>

      {errorMsg && (
        <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* 3-Step Quick Launch Guide */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            What would you like to do?
          </h2>
          <ActionHint
            title="Recommended Workflow"
            description="Follow Steps 1 to 3 in order, or jump straight to the tool you need."
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {quickActions.map((action) => {
            const Icon = action.icon;
            return (
              <div
                key={action.href}
                className="minimal-card-interactive p-5 flex flex-col justify-between gap-4"
              >
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                      {action.step}
                    </span>
                    <div className={`p-2 rounded-xl ${action.accent}`}>
                      <Icon className="w-4 h-4" />
                    </div>
                  </div>
                  <h3 className="text-sm font-bold text-white">{action.title}</h3>
                  <p className="text-xs text-slate-400 leading-relaxed">{action.description}</p>
                </div>

                <Link href={action.href} className="btn-secondary w-full justify-between">
                  <span>{action.buttonLabel}</span>
                  <ArrowRight className="w-3.5 h-3.5 text-cyan-400" />
                </Link>
              </div>
            );
          })}
        </div>
      </section>

      {/* Primary KPI Summary */}
      <section className="space-y-3">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {primaryKpis.map((kpi) => {
            const Icon = kpi.icon;
            return (
              <div key={kpi.label} className="minimal-card p-4 sm:p-5">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-medium text-slate-400">{kpi.label}</span>
                    <ActionHint description={kpi.hint} />
                  </div>
                  <Icon className={`w-4 h-4 ${kpi.color}`} />
                </div>
                <div className="mt-3 text-2xl sm:text-3xl font-bold text-white tracking-tight">
                  {loading ? "—" : kpi.value}
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex flex-wrap items-center gap-4 px-4 py-2.5 rounded-xl border border-slate-800/60 bg-slate-900/30 text-xs text-slate-400">
          <span>
            Cases Under Review:{" "}
            <strong className="text-slate-200">{loading ? "—" : stats?.cases_under_review ?? 0}</strong>
          </span>
          <span className="text-slate-700">•</span>
          <span>
            Generated PDF Reports:{" "}
            <strong className="text-slate-200">{loading ? "—" : stats?.pending_reports ?? 0}</strong>
          </span>
        </div>
      </section>

      {/* Clean Analytics Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="minimal-card p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-white">Risk Breakdown</h3>
              <p className="text-[11px] text-slate-400">Severity across your saved cases</p>
            </div>
          </div>

          <div className="h-56 w-full flex items-center justify-center">
            {stats?.risk_distribution && stats.risk_distribution.some((d) => d.count > 0) ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={stats.risk_distribution}
                    dataKey="count"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={52}
                    outerRadius={80}
                    paddingAngle={4}
                  >
                    {stats.risk_distribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0F172A",
                      borderColor: "#1E293B",
                      borderRadius: "10px",
                      fontSize: "12px",
                    }}
                    itemStyle={{ color: "#F1F5F9" }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="text-center text-xs text-slate-500">
                No cases yet — open a case to see your risk chart.
              </div>
            )}
          </div>

          <div className="grid grid-cols-4 gap-2 pt-3 border-t border-slate-800/70 text-center">
            {stats?.risk_distribution?.map((r) => (
              <div key={r.name}>
                <div className="text-xs font-bold text-white">{r.count}</div>
                <div className="text-[10px] text-slate-400">{r.name}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="minimal-card p-6 space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-white">Case Progress</h3>
            <p className="text-[11px] text-slate-400">Where each case sits in the removal lifecycle</p>
          </div>

          <div className="h-64 w-full">
            {stats?.case_status_distribution && stats.case_status_distribution.some((s) => s.count > 0) ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={stats.case_status_distribution} margin={{ top: 10, right: 10, left: -24, bottom: 24 }}>
                  <XAxis
                    dataKey="label"
                    tick={{ fill: "#64748B", fontSize: 10 }}
                    interval={0}
                    angle={-30}
                    textAnchor="end"
                  />
                  <YAxis tick={{ fill: "#64748B", fontSize: 10 }} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0F172A",
                      borderColor: "#1E293B",
                      borderRadius: "10px",
                      fontSize: "12px",
                    }}
                    itemStyle={{ color: "#38BDF8" }}
                  />
                  <Bar dataKey="count" fill="#00B4D8" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-center text-xs text-slate-500">
                No status history yet.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Recent Scans & Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="minimal-card p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Recent Scans</h3>
            <Link href="/analysis" className="text-xs text-cyan-400 hover:underline inline-flex items-center gap-1">
              Scan New <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="space-y-2">
            {!stats?.recent_analyses || stats.recent_analyses.length === 0 ? (
              <p className="text-xs text-slate-500 py-6 text-center">No scans performed yet.</p>
            ) : (
              stats.recent_analyses.map((ana) => (
                <div
                  key={ana.id}
                  className="flex items-center justify-between p-3 rounded-xl border border-slate-800/70 bg-slate-950/40 text-xs"
                >
                  <div className="min-w-0 pr-3">
                    <div className="font-semibold text-slate-200 capitalize">{ana.content_type} Scan</div>
                    <div className="text-[11px] text-slate-400 truncate max-w-xs">
                      {ana.input_reference || ana.id.slice(0, 8)}
                    </div>
                  </div>

                  <div className="text-right shrink-0">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                        ana.risk_level === "critical"
                          ? "bg-rose-500/20 text-rose-300"
                          : ana.risk_level === "high"
                          ? "bg-orange-500/20 text-orange-300"
                          : ana.risk_level === "medium"
                          ? "bg-amber-500/20 text-amber-300"
                          : "bg-emerald-500/20 text-emerald-300"
                      }`}
                    >
                      {ana.risk_level}
                    </span>
                    <div className="text-[10px] text-slate-500 mt-1">
                      {Math.round(ana.confidence * 100)}% confidence
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="minimal-card p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Recent Activity</h3>
            <span className="text-[11px] text-slate-500">Latest actions</span>
          </div>

          <div className="space-y-2">
            {!stats?.recent_activities || stats.recent_activities.length === 0 ? (
              <p className="text-xs text-slate-500 py-6 text-center">No activity logged yet.</p>
            ) : (
              stats.recent_activities.map((act) => (
                <div
                  key={act.id}
                  className="flex items-center justify-between p-3 rounded-xl border border-slate-800/70 bg-slate-950/40 text-xs"
                >
                  <div className="space-y-0.5 min-w-0 pr-3">
                    <div className="font-semibold text-slate-200">{act.action}</div>
                    <div className="text-[11px] text-slate-400 truncate">{act.description}</div>
                  </div>
                  <div className="text-right shrink-0">
                    <span className="inline-block px-2 py-0.5 rounded-full text-[10px] font-medium uppercase bg-slate-800 text-slate-300">
                      {act.category}
                    </span>
                    <div className="text-[10px] text-slate-500 mt-1">
                      {new Date(act.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
