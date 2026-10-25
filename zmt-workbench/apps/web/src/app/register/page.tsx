"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api("/auth/register", {
        method: "POST",
        body: JSON.stringify({ username, password, phone: phone || null }),
      });
      router.push("/");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="container">
      <div className="card">
        <h1>注册</h1>
        <p className="muted">创建自媒体 AI 工作台账号</p>
        <form onSubmit={onSubmit}>
          <label htmlFor="username">用户名</label>
          <input
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            minLength={3}
            autoComplete="username"
            required
          />
          <label htmlFor="password">密码</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={6}
            autoComplete="new-password"
            required
          />
          <label htmlFor="phone">手机号（可选）</label>
          <input
            id="phone"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            autoComplete="tel"
          />
          {error && <div className="error">{error}</div>}
          <button type="submit" disabled={loading}>
            {loading ? "注册中…" : "注册"}
          </button>
        </form>
        <p className="muted" style={{ marginTop: 12 }}>
          已有账号？<Link href="/">去登录</Link>
        </p>
      </div>
    </div>
  );
}