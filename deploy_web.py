#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Qbot 云端 Web 部署入口（headless）。

复用项目编译好的前端与登录/用户服务，补齐 /api/login 等无需券商/聚宽
账号的认证接口，使前端可正常登录。实盘数据类接口（需 eastmoney 券商 +
jqdata 聚宽账号）在云端不可用，统一返回提示信息。

数据库：SQLite pytrader.db，工作目录切换至 pytrader。
默认账号（与项目 env_setup.sh 一致）：
    username: admin    password: admin1234.

启动：
    export PYTHONPATH=$PYTHONPATH:/workspace:/workspace/pytrader
    python deploy_web.py
"""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
PTRADER_DIR = os.path.join(ROOT, "pytrader")
os.chdir(PTRADER_DIR)  # 使 SQLite 路径与项目相对路径一致

# headless matplotlib（供回测绘图）
os.environ.setdefault("MPLBACKEND", "Agg")

import mimetypes  # noqa: E402

from fastapi import Depends, FastAPI, HTTPException, status  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from sqlalchemy import create_engine  # noqa: E402

from web.database import Base, Database  # noqa: E402
import web.models  # noqa: E402  # 注册 ORM 表
from web.db_service import DbService  # noqa: E402
from web.dto import LoginRequest, StrategyModel  # noqa: E402
from web.settings import APISettings  # noqa: E402
from web.user_service import (  # noqa: E402
    Token,
    UserModel,
    UserService,
    get_password_hash,
    oauth2_scheme,
    route_data,
)
from web.models import User  # noqa: E402

import easyquotation  # noqa: E402  # 可用免费行情模块
import easytrader  # noqa: E402  # 券商交易封装

mimetypes.add_type("application/javascript; charset=utf-8", ".js")

# 初始化数据库表
_engine = create_engine("sqlite:///pytrader.db", pool_pre_ping=True)
Base.metadata.create_all(bind=_engine)

settings = APISettings()
database = Database()
db_service = DbService(settings, database)
user_service = UserService(db_service)

DEFAULT_USER = os.environ.get("QbotADMIN", "admin")
DEFAULT_PASS = os.environ.get("QbotPASS", "admin1234.")
# 首次启动写入默认账号
if not user_service.get_user(DEFAULT_USER):
    db_service.add_user(DEFAULT_USER, get_password_hash(DEFAULT_PASS))

app = FastAPI(title="Qbot - AI 智能量化投研平台 (云端 Web 部署)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        import json

        from jose import jwt
        from web.user_service import SECRET_KEY, ALGORITHM, TokenData

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except Exception:
        raise credentials_exception
    user = user_service.get_user(token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    return current_user


@app.get("/")
async def root():
    return RedirectResponse("/static/index.html")


@app.get("/api/health")
async def health():
    return {
        "error": 0,
        "data": {
            "status": "ok",
            "modules": {
                "easyquotation": True,
                "easytrader": True,
                "web_auth": True,
            },
        },
    }


@app.post("/api/login", response_model=Token)
async def login_for_access_token(login: LoginRequest):
    user = user_service.authenticate_user(login.username, login.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    from datetime import timedelta

    from web.user_service import ACCESS_TOKEN_EXPIRE_MINUTES

    access_token = user_service.create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/me/", response_model=UserModel)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    import json

    return UserModel(
        email=current_user.email,
        full_name=current_user.full_name,
        roles=json.loads(current_user.roles),
        username=current_user.username,
        disabled=False,
    )


@app.get("/api/route")
async def read_user_routes(current_user: User = Depends(get_current_active_user)):
    assert current_user is not None
    return route_data


@app.get("/api/strategies")
async def list_strategies():
    return {"error": 0, "data": db_service.list_strategies()}


@app.post("/api/strategies")
def add_strategy(model: StrategyModel):
    return {"error": 0, "data": db_service.add_strategy(model.name, model.code)}


@app.put("/api/strategies/{id}")
def update_strategy(model: StrategyModel, id: int):
    return {"error": 0, "data": db_service.update_strategy(id, model.name, model.code)}


# 以下接口依赖实盘券商/聚宽数据，云端无账号时给提示
@app.get("/api/balance")
def get_balance(current_user: User = Depends(get_current_active_user)):
    return {"error": 1, "msg": "云端环境暂未接入实盘券商，无法获取资金账户"}


@app.get("/api/position")
def get_position(current_user: User = Depends(get_current_active_user)):
    return {"error": 1, "msg": "云端环境暂未接入实盘券商，无法获取持仓"}


@app.get("/api/stocks")
async def get_stocks(current_user: User = Depends(get_current_active_user)):
    return {"error": 1, "msg": "云端环境暂未接入 jqdata 聚宽行情"}


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("QbotHOST", "0.0.0.0")
    port = int(os.environ.get("QbotPORT", "16000"))
    uvicorn.run(app, host=host, port=port)