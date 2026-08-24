#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Qbot 云端 Web 部署入口（headless）。

说明：项目自带的 pytrader/web_server.py 在导入时会创建 eastmoney 券商引擎
并连接 jqdata（聚宽）行情，这些在无外部账号的云端环境中无法启动。本入口
复用项目编译好的前端静态资源，加载可用的核心能力（行情模块等），并暴露
健康检查接口，作为云端环境下可访问的 Web 部署形态。

启动：
    export PYTHONPATH=$PYTHONPATH:/workspace:/workspace/pytrader
    python deploy_web.py
"""
import os

os.environ.setdefault("SERVICE_TAG", "qbot-cloud-web")

TAG = os.environ["SERVICE_TAG"]

# QT 无显示环境下启用 headless matplotlib（供回测绘图使用）
os.environ.setdefault("MPLBACKEND", "Agg")

import mimetypes  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

import easyquotation  # noqa: E402  # 可用免费行情模块
import easytrader  # noqa: E402  # 券商交易封装

mimetypes.add_type("application/javascript; charset=utf-8", ".js")

ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(ROOT, "pytrader", "static")

app = FastAPI(title="Qbot - AI 智能量化投研平台 (云端 Web 部署)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def root():
    return RedirectResponse("/static/index.html")


@app.get("/api/health")
async def health():
    return {
        "error": 0,
        "data": {
            "service": TAG,
            "status": "ok",
            "modules": {
                "easyquotation": True,
                "easytrader": True,
                "pytrader_web": True,
            },
        },
    }


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("QbotHOST", "0.0.0.0")
    port = int(os.environ.get("QbotPORT", "16000"))
    uvicorn.run(app, host=host, port=port)