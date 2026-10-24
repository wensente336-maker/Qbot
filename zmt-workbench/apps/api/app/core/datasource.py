"""抖音数据源客户端（占位，P0 授权验证后填充）。

未授权时统一抛错，由 service 层走"手动录入 / 文件导入"兜底路径。
"""

from app.core.config import settings


class DouyinSource:
    @property
    def enabled(self) -> bool:
        return bool(settings.douyin_access_token)

    async def fetch_creator(self, share_url: str) -> dict:
        """按分享链接解析创作者档案。"""
        if not self.enabled:
            raise RuntimeError("抖音数据源未授权，请走手动录入")
        # TODO(补充 API)：接入抖音开放平台，返回 {platform_uid, nickname, avatar_url, ...}
        raise NotImplementedError("抖音 API 待接入，请提供 DOUYIN_ACCESS_TOKEN")

    async def list_works(self, platform_uid: str, limit: int = 20) -> list[dict]:
        """按创作者 UID 拉取作品列表（增量）。"""
        if not self.enabled:
            raise RuntimeError("抖音数据源未授权，请走手动录入")
        raise NotImplementedError("抖音 API 待接入")


douyin_source = DouyinSource()
