"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import Nav from "@/components/Nav";

interface Material {
  id: number;
  platform: string;
  work_id: string;
  title: string | null;
  author_name: string | null;
  source_url: string | null;
  parse_status: string;
}

export default function MaterialsPage() {
  const [items, setItems] = useState<Material[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ platform: "douyin", work_id: "", title: "", source_url: "" });

  const load = useCallback(async () => {
    try {
      setItems(await api<Material[]>("/materials"));
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api("/materials", { method: "POST", body: JSON.stringify(form) });
      setForm({ platform: "douyin", work_id: "", title: "", source_url: "" });
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function extractFeatures(id: number) {
    setError("");
    try {
      await api("/materials/feature-extract", {
        method: "POST",
        body: JSON.stringify({ work_id: id }),
      });
      alert("特征提取完成（占位结果）");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <>
      <Nav />
      <div className="container wide">
        <div className="card">
          <h1>素材库</h1>
          <p className="muted">素材主要来自抖音对标账号（TODO：配置 DOUYIN_ACCESS_TOKEN 后自动同步）。</p>
          <form onSubmit={submit} className="row">
            <input
              placeholder="作品 ID"
              value={form.work_id}
              onChange={(e) => setForm({ ...form, work_id: e.target.value })}
              required
              style={{ flex: 1 }}
            />
            <input
              placeholder="标题"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              style={{ flex: 2 }}
            />
            <input
              placeholder="来源 URL"
              value={form.source_url}
              onChange={(e) => setForm({ ...form, source_url: e.target.value })}
              style={{ flex: 2 }}
            />
            <button type="submit" className="secondary">
              录入素材
            </button>
          </form>
          {error && <div className="error">{error}</div>}

          <ul className="list">
            {items.map((m) => (
              <li key={m.id}>
                <div>
                  <div>{m.title || m.work_id}</div>
                  <div className="muted">
                    {m.platform} · {m.author_name || "未知作者"}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <span className="badge">{m.parse_status}</span>
                  <button className="secondary" onClick={() => extractFeatures(m.id)}>
                    提取特征
                  </button>
                </div>
              </li>
            ))}
            {items.length === 0 && <li className="muted">暂无素材</li>}
          </ul>
        </div>
      </div>
    </>
  );
}