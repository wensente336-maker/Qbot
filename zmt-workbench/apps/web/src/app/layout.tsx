import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "自媒体 AI 工作台",
  description: "自媒体 AI 工作台（S0 工程基座）",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}