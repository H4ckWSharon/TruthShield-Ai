"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/authContext";
import { apiFetch } from "@/lib/api";
import type { NotificationItem } from "@/types";
import { Logo } from "./Logo";
import { HowItWorksModal } from "./HowItWorksModal";
import {
  Bell,
  CheckCheck,
  Menu,
  X,
  LayoutDashboard,
  ScanSearch,
  Briefcase,
  Fingerprint,
  FileCheck2,
  ShieldAlert,
  HelpCircle,
} from "lucide-react";

export const Navbar: React.FC = () => {
  const { user } = useAuth();
  const pathname = usePathname();
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [showNotifMenu, setShowNotifMenu] = useState(false);
  const [showMobileNav, setShowMobileNav] = useState(false);
  const [showGuide, setShowGuide] = useState(false);

  const fetchNotifications = useCallback(async () => {
    try {
      const res = await apiFetch("/notifications?limit=10");
      if (res.ok) {
        const data: NotificationItem[] = await res.json();
        setNotifications(data);
      }
    } catch (e) {
      console.error("Failed to load notifications", e);
    }
  }, []);

  useEffect(() => {
    fetchNotifications();
  }, [user, pathname, fetchNotifications]);

  const markOneRead = async (id: string) => {
    try {
      const res = await apiFetch(`/notifications/${id}/read`, { method: "PATCH" });
      if (res.ok) {
        setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
      }
    } catch (e) {
      console.error(e);
    }
  };

  const markAllRead = async () => {
    try {
      const res = await apiFetch("/notifications/read-all", { method: "POST" });
      if (res.ok) {
        setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      }
    } catch (e) {
      console.error(e);
    }
  };

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  const navItems = [
    { label: "Home Overview", href: "/", icon: LayoutDashboard },
    { label: "Check Content", href: "/analysis", icon: ScanSearch },
    { label: "My Cases & Proof", href: "/cases", icon: Briefcase },
    { label: "Protect Originals", href: "/fingerprints", icon: Fingerprint },
    { label: "Removal & PDFs", href: "/removal", icon: FileCheck2 },
    ...(!user || user.role === "admin"
      ? [{ label: "System Settings", href: "/admin", icon: ShieldAlert }]
      : []),
  ];

  return (
    <>
      <header className="sticky top-0 z-40 w-full border-b border-slate-800/70 bg-navy-950/85 backdrop-blur-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setShowMobileNav(!showMobileNav)}
              className="md:hidden p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800"
              aria-label="Toggle Menu"
            >
              {showMobileNav ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>

            <Link href="/" className="hover:opacity-90 transition">
              <Logo size="md" />
            </Link>
          </div>

          <div className="flex items-center gap-2.5 sm:gap-3.5">
            {/* How It Works Guide Button */}
            <button
              type="button"
              onClick={() => setShowGuide(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-700/80 bg-slate-900/70 hover:border-cyan-500/40 hover:text-cyan-300 text-slate-300 text-xs font-medium transition"
              title="Open step-by-step guide explaining what each button does"
            >
              <HelpCircle className="w-3.5 h-3.5 text-cyan-400" />
              <span className="hidden sm:inline">How to Use</span>
            </button>

            {/* Live Status Pill */}
            <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[11px] font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              Ready to Use
            </div>

            {/* Notifications Bell */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowNotifMenu(!showNotifMenu)}
                className="relative p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800/80 transition"
                title="View alerts & status updates"
                aria-label="Notifications"
              >
                <Bell className="w-4.5 h-4.5 w-5 h-5" />
                {unreadCount > 0 && (
                  <span className="absolute top-1 right-1 w-4 h-4 rounded-full bg-cyan-500 text-[10px] font-bold text-slate-950 flex items-center justify-center">
                    {unreadCount}
                  </span>
                )}
              </button>

              {showNotifMenu && (
                <div className="absolute right-0 mt-2 w-80 rounded-2xl bg-slate-900 border border-slate-800 shadow-2xl p-3.5 z-50">
                  <div className="flex items-center justify-between pb-2.5 border-b border-slate-800">
                    <span className="text-xs font-semibold text-slate-200">Recent Updates</span>
                    {unreadCount > 0 && (
                      <button
                        type="button"
                        onClick={markAllRead}
                        className="text-[11px] text-cyan-400 hover:underline flex items-center gap-1"
                      >
                        <CheckCheck className="w-3.5 h-3.5" /> Mark all read
                      </button>
                    )}
                  </div>

                  <div className="mt-2.5 max-h-64 overflow-y-auto space-y-2">
                    {notifications.length === 0 ? (
                      <p className="text-xs text-slate-500 text-center py-4">No notifications yet</p>
                    ) : (
                      notifications.map((n) => (
                        <div
                          key={n.id}
                          onClick={() => !n.is_read && markOneRead(n.id)}
                          className={`p-2.5 rounded-xl text-xs border cursor-pointer transition ${
                            n.is_read
                              ? "bg-slate-950/40 border-slate-800/50 text-slate-400"
                              : "bg-slate-800/70 border-cyan-500/30 text-slate-200 hover:border-cyan-400"
                          }`}
                        >
                          <div className="font-semibold text-slate-200 mb-0.5">{n.title}</div>
                          <p className="text-[11px] text-slate-400 leading-relaxed">{n.message}</p>
                          <span className="text-[10px] text-slate-500 block mt-1">
                            {new Date(n.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Workspace Profile */}
            <div className="hidden md:flex items-center gap-2.5 pl-3 border-l border-slate-800/80">
              <div className="text-right">
                <div className="text-xs font-semibold text-slate-200 leading-tight">
                  {user?.full_name || "Workspace Operator"}
                </div>
                <div className="text-[10px] text-slate-400 capitalize">
                  {user?.role || "admin"} access
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        {showMobileNav && (
          <nav className="md:hidden border-t border-slate-800 bg-navy-950 px-4 py-3 space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setShowMobileNav(false)}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition ${
                    isActive
                      ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/30"
                      : "text-slate-400 hover:text-white hover:bg-slate-800/60"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
        )}
      </header>

      <HowItWorksModal isOpen={showGuide} onClose={() => setShowGuide(false)} />
    </>
  );
};
