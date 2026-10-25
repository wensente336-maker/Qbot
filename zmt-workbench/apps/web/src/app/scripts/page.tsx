"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import Nav from "@/components/Nav";

interface Project {
  id: number;
  status: string;
}

interface Script {
  id: number;
  project_id: number;
  current_version: number;
  content: string | null;
}

export default function ScriptsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [scripts, setScripts] = useState<Record<number, Script>>({});
  const [error, setError] = useState("");
  const [length, setLength] = useState(500);

  const loadProjects = useCallback(async () => {
    try {
      setProjects(await api<Project[]>("/projects"));
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  async function genOutline(projectId: number) {
    setError("");
    try {
      await api("/outlines/generate", {
        method: "POST",
        body: JSON.stringify({ project_id: projectId }),
      });
      await api(`/outlines/${projectId}/approve`, {
        method: "POST",
        body: JSON.stringify({ approved: true }),
      });
      alert("大纲已生成并确认（占位内容）");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function genScript(projectId: number) {
    setError("");
    try {
      const s = await api<Script>("/scripts/generate", {
        method: "POST",
        body: JSON.stringify({ project_id: projectId, length }),
      });
      setScripts((prev) => ({ ...prev, [projectId]: s }));
      await loadProjects();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function loadScript(projectId: number) {
    try {
      const s = await api<Script>(`/scripts/${projectId}`);
      setScripts((prev) => ({ ...prev, [projectId]: s }));
    } catch {
      /* 尚未生成文案时忽略 */
    }
  }

  useEffect(() => {
    projects.forEach((p) => {
      if (p.status !== "topic_confirmed") loadScript(p.id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projects]);

  return (
    <>
      <Nav />
      <div className="container wide">
        <div className="card">
          <div className="topbar">
            <h1 style={{ margin: 0 }}>文案</h1>
            <div className="row" style={{ margin: 0 }}>
              <select
                value={length}
                onChange={(e) => setLength(Number(e.target.value))}
                style={{ width: 120 }}
              >
                <option value={300}>300 字</option>
                <option value={500}>500 字</option>
                <option value={800}>800 字</option>
              </select>
            </div>
          </div>
          {error && <div className="error">{error}</div>}
          <ul className="list">
            {projects.map((p) => (
              <li key={p.id} style={{ flexDirection: "column", alignItems: "stretch" }}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <div>
                    <div>项目 #{p.id}</div>
                    <span className="badge">{p.status}</span>
                  </div>
                  <div>
                    <button className="secondary" onClick={() => genOutline(p.id)}>
                      生成大纲
                    </button>{" "}
                    <button className="secondary" onClick={() => genScript(p.id)}>
                      生成文案
                    </button>
                  </div>
                </div>
                {scripts[p.id]?.content && (
                  <p className="muted" style={{ whiteSpace: "pre-wrap" }}>
                    {scripts[p.id]!.content}
                  </p>
                )}
              </li>
            ))}
            {projects.length === 0 && <li className="muted">暂无项目</li>}
          </ul>
        </div>
      </div>
    </>
  );
}