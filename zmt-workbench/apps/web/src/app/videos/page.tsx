"use client";

import { useCallback, useEffect, useState } from "react";
import { api, upload } from "@/lib/api";
import Nav from "@/components/Nav";

interface Project {
  id: number;
  status: string;
}

interface Job {
  id: number;
  project_id: number;
  job_type: string;
  status: string;
  progress: number;
  result: Record<string, unknown> | null;
}

export default function VideosPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [active, setActive] = useState<number | null>(null);
  const [assetRef, setAssetRef] = useState("");
  const [cuts, setCuts] = useState("[[1200, 3600]]");
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);

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

  const loadJobs = useCallback(async (projectId: number) => {
    try {
      setJobs(await api<Job[]>(`/videos/${projectId}/jobs`));
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  function selectProject(p: Project) {
    setActive(p.id);
    loadJobs(p.id);
  }

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || active === null) return;
    setUploading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("lifecycle", "user-uploads");
      form.append("project_id", String(active));
      const asset = await upload<{ key: string }>("/uploads", form);
      setAssetRef(asset.key);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  async function run(path: string, body: Record<string, unknown>) {
    if (active === null) return;
    setError("");
    try {
      await api(path, { method: "POST", body: JSON.stringify(body) });
      await loadJobs(active);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <>
      <Nav />
      <div className="container wide">
        <div className="card">
          <h1>视频制作</h1>
          {error && <div className="error">{error}</div>}
          <div className="row">
            <select
              value={active ?? ""}
              onChange={(e) => {
                const id = Number(e.target.value);
                const p = projects.find((x) => x.id === id);
                if (p) selectProject(p);
              }}
              style={{ flex: 1 }}
            >
              <option value="">选择项目…</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  项目 #{p.id}（{p.status}）
                </option>
              ))}
            </select>
          </div>

          {active !== null && (
            <div>
              <h3 style={{ marginTop: 16 }}>操作</h3>
              <div className="row">
                <input
                  id="video-file"
                  type="file"
                  accept="video/*"
                  style={{ display: "none" }}
                  onChange={onUpload}
                  disabled={uploading}
                />
                <label
                  htmlFor="video-file"
                  style={{
                    marginTop: 0,
                    padding: "10px 18px",
                    background: "#232c3b",
                    color: "#e8edf4",
                    borderRadius: 8,
                    fontWeight: 600,
                    cursor: uploading ? "not-allowed" : "pointer",
                    display: "inline-block",
                    opacity: uploading ? 0.5 : 1,
                  }}
                >
                  {uploading ? "上传中…" : "上传视频"}
                </label>
                <span className="muted">上传后自动填入媒体引用</span>
              </div>
              <div className="row">
                <input
                  placeholder="媒体引用（key/URL）"
                  value={assetRef}
                  onChange={(e) => setAssetRef(e.target.value)}
                  style={{ flex: 2 }}
                />
                <button className="secondary" onClick={() => run(`/videos/${active}/transcribe`, { asset_ref: assetRef })}>
                  转写
                </button>
              </div>
              <div className="row">
                <input
                  placeholder="删除区间（ms）"
                  value={cuts}
                  onChange={(e) => setCuts(e.target.value)}
                  style={{ flex: 2 }}
                />
                <button
                  className="secondary"
                  onClick={() => {
                    const parsed = JSON.parse(cuts);
                    run(`/videos/${active}/rough-cut`, { cuts: parsed });
                  }}
                >
                  粗剪
                </button>
                <button className="secondary" onClick={() => run(`/videos/${active}/storyboard`, {})}>
                  分镜
                </button>
                <button
                  className="secondary"
                  onClick={() => run(`/videos/${active}/render`, { composition: "default", resolution: "1080x1920", fps: 30 })}
                >
                  渲染
                </button>
              </div>

              <h3 style={{ marginTop: 16 }}>任务</h3>
              <ul className="list">
                {jobs.map((j) => (
                  <li key={j.id}>
                    <div>
                      <div>
                        #{j.id} · {j.job_type}
                      </div>
                      <div className="muted">{JSON.stringify(j.result ?? {})}</div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <span className="badge">{j.status}</span>
                      <button className="secondary" onClick={() => run(`/videos/jobs/${j.id}/qa`, {})}>
                        质检
                      </button>
                    </div>
                  </li>
                ))}
                {jobs.length === 0 && <li className="muted">暂无任务</li>}
              </ul>
            </div>
          )}
        </div>
      </div>
    </>
  );
}