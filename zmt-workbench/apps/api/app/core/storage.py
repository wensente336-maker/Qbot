"""对象存储：COS 预签名（私有读写）+ 本地磁盘兜底。

生命周期前缀策略（TD 第 7 章）：
- benchmark/      7 天
- user-uploads/   30 天
- render-output/  永久
"""

from app.core.config import settings

PREFIXES = ("benchmark", "user-uploads", "render-output")


class Storage:
    @property
    def use_cos(self) -> bool:
        return bool(settings.cos_secret_id and settings.cos_secret_key and settings.cos_bucket)

    def presign_get(self, key: str, expires: int = 900) -> str:
        """返回 15 分钟有效私有访问 URL（前端播放用）。"""
        if self.use_cos:
            # TODO(补充 API)：接入腾讯云 COS SDK 生成预签名 GET URL
            raise NotImplementedError("COS SDK 待接入，请配置 COS_SECRET_ID/KEY/BUCKET/REGION")
        return f"/media/{key}"

    def presign_upload(
        self, key: str, content_type: str = "application/octet-stream", expires: int = 3600
    ) -> str:
        """返回预签名直传 URL（大文件不经 API 进程）。"""
        if self.use_cos:
            # TODO(补充 API)：接入 COS SDK 生成预签名 PUT URL
            raise NotImplementedError("COS 预签名上传待接入")
        return f"/api/v1/upload/local/{key}"

    @staticmethod
    def build_key(lifecycle: str, project_id: int, filename: str) -> str:
        if lifecycle not in PREFIXES:
            raise ValueError(f"非法生命周期前缀：{lifecycle}")
        return f"{lifecycle}/{project_id}/{filename}"


storage = Storage()
