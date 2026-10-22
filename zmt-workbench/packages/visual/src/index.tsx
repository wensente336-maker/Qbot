// 品牌视觉组件（S0 占位，S3 供 frontend 与 renderer 共用同一套视觉组件）
import React from "react";

export function BrandFrame({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        width: 1080,
        height: 1920,
        background: "#0d1117",
        color: "#e8edf4",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {children}
    </div>
  );
}