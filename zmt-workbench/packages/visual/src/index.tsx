// 品牌视觉组件：供 renderer（Remotion）复用同一套 1080×1920 竖屏视觉语言。
import React from "react";

const SAFE_TOP = 0.15; // 上下安全区 15%
const SAFE_SIDE = 0.08; // 左右安全区 8%

export function BrandFrame({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        position: "relative",
        width: 1080,
        height: 1920,
        background: "#0d1117",
        color: "#e8edf4",
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif',
        overflow: "hidden",
      }}
    >
      {children}
    </div>
  );
}

export function Subtitle({
  text,
  tone = "#ffffff",
}: {
  text: string;
  tone?: string;
}) {
  return (
    <div
      style={{
        position: "absolute",
        left: 1080 * SAFE_SIDE,
        right: 1080 * SAFE_SIDE,
        bottom: 1920 * SAFE_TOP,
        fontSize: 54,
        lineHeight: 1.4,
        fontWeight: 600,
        color: tone,
        textShadow: "0 4px 24px rgba(0,0,0,0.7)",
        textAlign: "center",
      }}
    >
      {text}
    </div>
  );
}

export function SceneFrame({
  index,
  visual,
  subtitle,
  accent = "#4da3ff",
}: {
  index: number;
  visual: string;
  subtitle?: string;
  accent?: string;
}) {
  return (
    <BrandFrame>
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: `radial-gradient(ellipse at 50% 35%, ${accent}22, transparent 60%), #0d1117`,
        }}
      />
      <div
        style={{
          position: "absolute",
          top: 1920 * SAFE_TOP,
          left: 1080 * SAFE_SIDE,
          right: 1080 * SAFE_SIDE,
          fontSize: 40,
          color: "#98a3b3",
        }}
      >
        SCENE {String(index).padStart(2, "0")}
      </div>
      <div
        style={{
          position: "absolute",
          top: "42%",
          left: 1080 * SAFE_SIDE,
          right: 1080 * SAFE_SIDE,
          fontSize: 72,
          fontWeight: 700,
          textAlign: "center",
        }}
      >
        {visual}
      </div>
      {subtitle ? <Subtitle text={subtitle} /> : null}
    </BrandFrame>
  );
}