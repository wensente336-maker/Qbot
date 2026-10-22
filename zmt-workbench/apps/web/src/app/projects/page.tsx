"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, clearToken, getToken } from "@/lib/api";

const STATUSES = [
  "topic_confirmed",
  "outline_confirmed",
  "script_finalized",
  "video_uploaded",
  "ai_editing",
  "video_reviewed",
  "published",
  "weekly_reviewed",
];

interface Project {
  id: number;
  topic_id: number | null;
  user_id: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export default function ProjectsPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setProjects(await api<Project[]>("/projects"));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.push("/");
      return;
    }
    load();
  }, [router, load]);

  async function createProject() {
    setError("");
    try {
      await api<Project>("/projects", { method: "POST", body: "{}" });
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function advance(project: Project) {
    setError("");
    const next = STATUSES[STATUSES.indexOf(project.status) + 1];
    if (!next) return;
    try {
      await api<Project>(`/projects/${project.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: next }),
      });
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function logout() {
    clearToken();
    router.push("/");
  }

  return (
    <div className="container">
      <div className="card">
        <div className="topbar">
          <h1 style={{ margin: 0 }}>内容项目</h1>
          <div>
            <button className="secondary" onClick={createProject}>
              新建项目
            </button>{" "}
            <button className="secondary" onClick={logout}>
              退出
            </button>
          </div>
        </div>

        {loading && <p className="muted">加载中…</p>}
        {error && <div className="error">{error}</div>}

        <ul className="list">
          {projects.map((p) => (
            <li key={p.id}>
              <div>
                <div>项目 #{p.id}</div>
                <div className="muted">{p.updated_at}</div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span className="badge">{p.status}</span>
                {STATUSES.indexOf(p.status) < STATUSES.length - 1 && (
                  <button className="secondary" onClick={() => advance(p)}>
                    推进
                  </button>
                )}
              </div>
            </li>
          ))}
          {!loading && projects.length === 0 && (
            <li className="muted">暂无项目，点击「新建项目」开始</li>
          )}
        </ul>
      </div>
    </div>
  );
}