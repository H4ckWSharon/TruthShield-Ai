"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { apiFetch, getAuthToken, setAuthToken, clearAuthToken } from "./api";
import type { User } from "@/types";

export type { User };

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<boolean>;
  register: (email: string, password: string, fullName: string) => Promise<boolean>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  loading: true,
  login: async () => false,
  register: async () => false,
  logout: () => {},
  refreshUser: async () => {},
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchCurrentUser = useCallback(async () => {
    try {
      const res = await apiFetch("/auth/me");
      if (res.ok) {
        const userData: User = await res.json();
        setUser(userData);
      } else {
        clearAuthToken();
        setUser(null);
        setToken(null);
      }
    } catch (e) {
      console.error("Failed to fetch workspace profile", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const savedToken = getAuthToken();
    if (savedToken) {
      setToken(savedToken);
    }
    // Always attempt resolving active operator (seamless when REQUIRE_AUTH=False)
    fetchCurrentUser();
  }, [fetchCurrentUser]);

  const login = async (email: string, password: string): Promise<boolean> => {
    try {
      const res = await apiFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Authentication failed");
      }
      const data = await res.json();
      setAuthToken(data.access_token);
      setToken(data.access_token);
      setUser(data.user);
      return true;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Login failed";
      alert(msg);
      return false;
    }
  };

  const register = async (email: string, password: string, fullName: string): Promise<boolean> => {
    try {
      const res = await apiFetch("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password, full_name: fullName }),
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Registration failed");
      }
      return await login(email, password);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Registration failed";
      alert(msg);
      return false;
    }
  };

  const logout = () => {
    clearAuthToken();
    setToken(null);
    fetchCurrentUser();
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, refreshUser: fetchCurrentUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
