"use client";

import React, { useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/authContext";
import type { SystemHealth, UserAdminItem, AIModelItem, AuditLogItem } from "@/types";
import { ActionHint } from "@/components/ActionHint";
import {
  ShieldAlert,
  Server,
  Database,
  Cpu,
  Users,
  Activity,
  RefreshCw,
} from "lucide-react";

export default function AdminPage() {
  const { user } = useAuth();
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [usersList, setUsersList] = useState<UserAdminItem[]>([]);
  const [modelsList, setModelsList] = useState<AIModelItem[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAllAdminData = useCallback(async () => {
    setLoading(true);
    try {
      const [hRes, uRes, mRes, lRes] = await Promise.all([
        apiFetch("/admin/system-health"),
        apiFetch("/admin/users"),
        apiFetch("/admin/models"),
        apiFetch("/admin/audit-logs?limit=40"),
      ]);

      if (hRes.ok) setHealth(await hRes.json());
      if (uRes.ok) setUsersList(await uRes.json());
      if (mRes.ok) setModelsList(await mRes.json());
      if (lRes.ok) setAuditLogs(await lRes.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAllAdminData();
  }, [user, fetchAllAdminData]);

  const handleUpdateRole = async (userId: string, newRole: string) => {
    try {
      const res = await apiFetch(`/admin/users/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({ role: newRole }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to update role");
      }
      fetchAllAdminData();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Failed to update role");
    }
  };

  const handleToggleActive = async (userId: string, currentActive: boolean) => {
    try {
      const res = await apiFetch(`/admin/users/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !currentActive }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to update account status");
      }
      fetchAllAdminData();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Failed to update status");
    }
  };

  const handleToggleModel = async (modelId: string, currentActive: boolean) => {
    try {
      const res = await apiFetch(`/admin/models/${modelId}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !currentActive }),
      });
      if (res.ok) fetchAllAdminData();
    } catch {
      alert("Failed to toggle model");
    }
  };

  return (
    <div className="space-y-7">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <ShieldAlert className="w-6 h-6 text-cyan-400" /> System Settings & Diagnostics
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Check service health, turn local AI engines on or off, manage operator permissions, and inspect security logs.
          </p>
        </div>

        <button type="button" onClick={fetchAllAdminData} className="btn-secondary self-start sm:self-auto">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /> Check Health Now
        </button>
      </div>

      {/* Health Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="minimal-card p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">API Server</span>
            <Server className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-3 text-lg font-bold text-white capitalize">{health?.status || "..."}</div>
          <p className="text-[11px] text-slate-500 mt-0.5">
            v{health?.version || "2.0.0"} • {health?.environment || "local"}
          </p>
        </div>

        <div className="minimal-card p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Database & Storage</span>
            <Database className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="mt-3 text-lg font-bold text-white capitalize">{health?.database_status || "..."}</div>
          <p className="text-[11px] text-slate-500 mt-0.5">
            {health?.active_cases ?? 0} cases • Vault {health?.storage_accessible ? "ready" : "error"}
          </p>
        </div>

        <div className="minimal-card p-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1">
              <span className="text-xs font-medium text-slate-400">Local AI & Queue</span>
              <ActionHint description="Shows whether Ollama LLM is running on port 11434; deterministic local rules, RapidOCR, and Whisper always run even when Ollama is offline." />
            </div>
            <Cpu className="w-4 h-4 text-purple-400" />
          </div>
          <div className="mt-3 text-sm font-bold text-white capitalize">
            Ollama: {health?.ollama_status?.replace(/_/g, " ") || "..."}
          </div>
          <p className="text-[11px] text-slate-500 mt-1">
            Worker: {health?.redis_status?.replace(/_/g, " ") || "checking"}
          </p>
        </div>

        <div className="minimal-card p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Operators</span>
            <Users className="w-4 h-4 text-blue-400" />
          </div>
          <div className="mt-3 text-lg font-bold text-white">{health?.total_users ?? 0} Accounts</div>
          <p className="text-[11px] text-slate-500 mt-0.5">Role-based access enabled</p>
        </div>
      </div>

      {/* AI Engine Switches */}
      <div className="minimal-card p-6 space-y-4">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-bold text-white flex items-center gap-2">
            <Cpu className="w-4 h-4 text-cyan-400" /> Analysis Engines
          </h2>
          <ActionHint description="Click Enabled/Disabled to turn an engine on or off across the whole application." />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {modelsList.map((m) => (
            <div
              key={m.id}
              className="p-4 rounded-xl border border-slate-800 bg-slate-950/60 text-xs flex items-center justify-between gap-4"
            >
              <div className="space-y-1">
                <div className="font-semibold text-white">{m.model_name}</div>
                <p className="text-[11px] text-slate-400 leading-relaxed">{m.description}</p>
                <span className="inline-block px-2 py-0.5 rounded-full text-[10px] bg-slate-800 text-slate-300">
                  {m.provider}
                </span>
              </div>

              <button
                type="button"
                onClick={() => handleToggleModel(m.id, m.is_active)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition shrink-0 ${
                  m.is_active
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/30"
                    : "bg-slate-800 text-slate-400 hover:text-white"
                }`}
              >
                {m.is_active ? "Enabled" : "Disabled"}
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* User Management */}
      <div className="minimal-card p-6 space-y-4">
        <h2 className="text-sm font-bold text-white flex items-center gap-2">
          <Users className="w-4 h-4 text-cyan-400" /> Operator Accounts
        </h2>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 text-slate-400 text-[11px] font-medium border-b border-slate-800">
              <tr>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Email</th>
                <th className="px-4 py-3">Role</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Cases</th>
                <th className="px-4 py-3 text-right">Manage</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {usersList.map((u) => (
                <tr key={u.id} className="hover:bg-slate-800/30">
                  <td className="px-4 py-3 font-semibold text-white">{u.full_name}</td>
                  <td className="px-4 py-3 text-slate-400 font-mono">{u.email}</td>
                  <td className="px-4 py-3 capitalize text-slate-300">{u.role}</td>
                  <td className="px-4 py-3">
                    <span className={`text-[11px] font-semibold ${u.is_active ? "text-emerald-400" : "text-rose-400"}`}>
                      {u.is_active ? "Active" : "Disabled"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-400">{u.case_count}</td>
                  <td className="px-4 py-3 text-right space-x-2">
                    <select
                      value={u.role}
                      onChange={(e) => handleUpdateRole(u.id, e.target.value)}
                      className="px-2 py-1 rounded-lg border border-slate-800 bg-slate-950 text-xs text-white"
                    >
                      <option value="user">User</option>
                      <option value="analyst">Analyst</option>
                      <option value="admin">Admin</option>
                    </select>
                    <button
                      type="button"
                      onClick={() => handleToggleActive(u.id, u.is_active)}
                      className={`px-2.5 py-1 rounded-lg text-[10px] font-semibold border ${
                        u.is_active
                          ? "border-rose-500/30 text-rose-300 hover:bg-rose-500/10"
                          : "border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/10"
                      }`}
                    >
                      {u.is_active ? "Disable" : "Enable"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Audit Log */}
      <div className="minimal-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-white flex items-center gap-2">
            <Activity className="w-4 h-4 text-cyan-400" /> Security Activity Log
          </h2>
          <span className="text-[11px] text-slate-500">Latest 40 events</span>
        </div>

        <div className="overflow-x-auto max-h-72 overflow-y-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 text-slate-400 text-[11px] font-medium sticky top-0 border-b border-slate-800">
              <tr>
                <th className="px-4 py-2">Time</th>
                <th className="px-4 py-2">Action</th>
                <th className="px-4 py-2">Area</th>
                <th className="px-4 py-2">Client IP</th>
                <th className="px-4 py-2">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
              {auditLogs.map((log) => (
                <tr key={log.id} className="hover:bg-slate-800/30">
                  <td className="px-4 py-2 text-slate-500">{new Date(log.timestamp).toLocaleString()}</td>
                  <td className="px-4 py-2 font-semibold text-cyan-400">{log.action}</td>
                  <td className="px-4 py-2 uppercase text-slate-300">{log.resource_type}</td>
                  <td className="px-4 py-2 text-slate-400">{log.ip_address}</td>
                  <td className="px-4 py-2 text-slate-400 truncate max-w-xs">{JSON.stringify(log.details)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
