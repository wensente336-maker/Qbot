"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import Nav from "@/components/Nav";

interface Topic {
  id: number;
  entry: string;
  base_topic: string | null;
  title: string | null;
  viewpoint: string | null;
  audience: string | null;
  angle: string | null;
  recommendation: string | null;
  status: string;
}

export default function TopicsPage() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [error, setError] = useState("");
  const [baseTopic, setBaseTopic] = useState("");
  const [count, setCount] = useState(10);

  const load = useCallback(async () => {
    try {
      setTopics(await api<Topic[]>("/topics"));
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function generate() {
    setError("");
    try {
      await api("/topics/generate", {
        method: "POST",
        body: JSON.stringify({ entry: "theme", base_topic: baseTopic, count }),
      });
      setBaseTopic("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <>
      <Nav />
      <div className="container wide">
        <div className="card">
          <h1>选题</h1>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              generate();
            }}
            className="row"
          >
            <input
              placeholder="主题（如：职场沟通）"
              value={baseTopic}
              onChange={(e) => setBaseTopic(e.target.value)}
              required
              style={{ flex: 2 }}
            />
            <input
              type="number"
              min={1}
              max={20}
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
              style={{ width: 90 }}
            />
            <button type="submit" className="secondary">
              生成选题
            </button>
          </form>
          {error && <div className="error">{error}</div>}
          <ul className="list">
            {topics.map((t) => (
              <li key={t.id}>
                <div>
                  <div>{t.title || t.base_topic}</div>
                  <div className="muted">{t.viewpoint || t.audience}</div>
                </div>
                <span className="badge">{t.status}</span>
              </li>
            ))}
            {topics.length === 0 && <li className="muted">暂无选题</li>}
          </ul>
        </div>
      </div>
    </>
  );
}