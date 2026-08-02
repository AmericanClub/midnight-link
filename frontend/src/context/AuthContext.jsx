import React, { createContext, useContext, useEffect, useState } from "react";
import api, { setWorkspaceHeader } from "@/lib/api";

const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null = checking, false = anon, object = auth
  const [workspaces, setWorkspaces] = useState([]);
  const [workspace, setWorkspace] = useState(null);

  const applySession = (data) => {
    setUser(data.user || false);
    setWorkspaces(data.workspaces || []);
    const cur = data.current_workspace || (data.workspaces && data.workspaces[0]) || null;
    setWorkspace(cur);
    if (cur) setWorkspaceHeader(cur.id);
  };

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/auth/me");
        applySession(data);
      } catch {
        setUser(false);
      }
    })();
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    applySession(data);
    return data;
  };

  const register = async (name, email, password) => {
    const { data } = await api.post("/auth/register", { name, email, password });
    applySession(data);
    return data;
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } catch {}
    setUser(false);
    setWorkspaces([]);
    setWorkspace(null);
    setWorkspaceHeader(null);
  };

  const switchWorkspace = (ws) => {
    setWorkspace(ws);
    setWorkspaceHeader(ws.id);
  };

  const refreshSession = async () => {
    try {
      const { data } = await api.get("/auth/me");
      setWorkspaces(data.workspaces || []);
      const cur = (data.workspaces || []).find((w) => w.id === workspace?.id) || data.current_workspace;
      if (cur) {
        setWorkspace(cur);
        setWorkspaceHeader(cur.id);
      }
    } catch {}
  };

  return (
    <AuthContext.Provider
      value={{ user, workspaces, workspace, login, register, logout, switchWorkspace, refreshSession }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
