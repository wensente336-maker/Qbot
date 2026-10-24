// 跨端共享的类型与常量（前后端契约的单一事实来源）

export const PROJECT_STATUSES = [
  "topic_confirmed",
  "outline_confirmed",
  "script_finalized",
  "video_uploaded",
  "ai_editing",
  "video_reviewed",
  "published",
  "weekly_reviewed",
] as const;

export type ProjectStatus = (typeof PROJECT_STATUSES)[number];

export const VIDEO_JOB_STATUSES = [
  "queued",
  "running",
  "succeeded",
  "failed",
] as const;

export type VideoJobStatus = (typeof VIDEO_JOB_STATUSES)[number];