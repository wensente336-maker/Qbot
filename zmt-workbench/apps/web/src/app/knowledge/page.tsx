"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import Nav from "@/components/Nav";

interface Card {
  id: number;
  title: string | null;
  viewpoint: string | null;
  status: string;
  is_locked: boolean;
  current_version: number;
}

export default function KnowledgePage() {
  const [cards, setCards] = useState<Card[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setCards(await api<Card[]>("/knowledge/cards"));
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
      await api("/knowledge/cards", { method: "POST", body: JSON.stringify({}) });
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function toggleLock(c: Card) {
    setError("");
    try {
      await api(`/knowledge/cards/${c.id}/lock`, {
        method: "POST",
        body: JSON.stringify({ is_locked: !c.is_locked }),
      });
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
          <div className="topbar">
            <h1 style={{ margin: 0 }}>知识库</h1>
            <button className="secondary" onClick={generate}>
              生成知识卡片
            </button>
          </div>
          {error && <div className="error">{error}</div>}
          <ul className="list">
            {cards.map((c) => (
              <li key={c.id}>
                <div>
                  <div>{c.title || `卡片 #${c.id}`}</div>
                  <div className="muted">{c.viewpoint || "（观点占位）"}</div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <span className="badge">{c.status}</span>
                  <button className="secondary" onClick={() => toggleLock(c)}>
                    {c.is_locked ? "解锁" : "锁定"}
                  </button>
                </div>
              </li>
            ))}
            {cards.length === 0 && <li className="muted">暂无知识卡片</li>}
          </ul>
        </div>
      </div>
    </>
  );
}