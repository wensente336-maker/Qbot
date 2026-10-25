"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import Nav from "@/components/Nav";

interface Dashboard {
  project_count: number;
  published_count: number;
  total_views: number;
}

interface WeeklyReport {
  period: string;
  metrics: Record<string, number>;
  summary: string;
}

export default function DashboardPage() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [weekly, setWeekly] = useState<WeeklyReport | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [d, w] = await Promise.all([
        api<Dashboard>("/dashboard"),
        api<WeeklyReport>("/weekly-report"),
      ]);
      setDashboard(d);
      setWeekly(w);
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <Nav />
      <div className="container wide">
        <div className="card">
          <h1>复盘驾驶舱</h1>
          {error && <div className="error">{error}</div>}
          {dashboard && (
            <div className="row">
              <div className="card" style={{ flex: 1 }}>
                <div className="muted">项目数</div>
                <div style={{ fontSize: "2rem", fontWeight: 700 }}>{dashboard.project_count}</div>
              </div>
              <div className="card" style={{ flex: 1 }}>
                <div className="muted">已发布</div>
                <div style={{ fontSize: "2rem", fontWeight: 700 }}>{dashboard.published_count}</div>
              </div>
              <div className="card" style={{ flex: 1 }}>
                <div className="muted">总播放</div>
                <div style={{ fontSize: "2rem", fontWeight: 700 }}>{dashboard.total_views}</div>
              </div>
            </div>
          )}

          {weekly && (
            <div style={{ marginTop: 20 }}>
              <h3>近 7 日周报</h3>
              <p className="muted">{weekly.summary}</p>
              <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.85rem" }}>
                {JSON.stringify(weekly.metrics, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </>
  );
}