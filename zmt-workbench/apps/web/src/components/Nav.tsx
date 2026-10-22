"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearToken, getToken } from "@/lib/api";
import { useEffect } from "react";

const LINKS = [
  { href: "/projects", label: "项目" },
  { href: "/materials", label: "素材" },
  { href: "/knowledge", label: "知识库" },
  { href: "/topics", label: "选题" },
  { href: "/scripts", label: "文案" },
  { href: "/videos", label: "视频" },
  { href: "/dashboard", label: "复盘" },
];

export default function Nav() {
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!getToken()) router.push("/");
  }, [router]);

  function logout() {
    clearToken();
    router.push("/");
  }

  return (
    <nav className="nav">
      <div className="nav-inner">
        <span className="brand">自媒体 AI 工作台</span>
        <div className="nav-links">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={pathname.startsWith(l.href) ? "active" : ""}
            >
              {l.label}
            </Link>
          ))}
        </div>
        <button className="secondary" onClick={logout}>
          退出
        </button>
      </div>
    </nav>
  );
}