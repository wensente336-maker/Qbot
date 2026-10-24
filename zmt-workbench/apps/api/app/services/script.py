"""文案服务：大纲生成/审批、全文生成（300/500/800 字）、局部重写（版本化）。"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import llm
from app.models.project import ContentProject
from app.models.script import Outline, Script, ScriptVersion
from app.services.billing import record_llm_usage

LENGTH_OPTIONS = (300, 500, 800)


def _mock_outline(project_id: int) -> dict:
    return {
        "title": f"项目 #{project_id} 大纲（占位）",
        "sections": [
            {"name": "开场钩子", "point": "3 秒内抓住注意力（占位）"},
            {"name": "核心论点", "point": "1 个强观点 + 1 个反常识（占位）"},
            {"name": "情绪递进", "point": "中段制造悬念与共鸣（占位）"},
            {"name": "结尾引导", "point": "互动引导（占位）"},
        ],
    }


def _mock_script(project_id: int, length: int) -> str:
    sentence = f"这是项目 #{project_id} 的口播脚本（占位，目标 {length} 字）。"
    return (sentence * ((length // len(sentence)) + 1))[:length]


async def _get_owned_project(db: AsyncSession, project_id: int, user_id: int) -> ContentProject:
    project = await db.get(ContentProject, project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")
    return project


async def generate_outline(db: AsyncSession, project_id: int, user_id: int) -> Outline:
    await _get_owned_project(db, project_id, user_id)

    latest = await db.scalar(
        select(Outline).where(Outline.project_id == project_id).order_by(Outline.version.desc())
    )
    version = (latest.version + 1) if latest else 1

    if llm.mock_enabled:
        content = _mock_outline(project_id)
    else:
        content = await llm.json(
            "你是短视频大纲专家，输出 JSON 对象 {title, sections:[{name, point}]}。",
            f"项目 #{project_id}，为其生成口播大纲。",
        )
        await record_llm_usage(db, project_id=project_id)

    outline = Outline(project_id=project_id, version=version, content=content, status="draft")
    db.add(outline)
    await db.commit()
    await db.refresh(outline)
    return outline


async def approve_outline(
    db: AsyncSession, project_id: int, user_id: int, approved: bool
) -> Outline:
    project = await _get_owned_project(db, project_id, user_id)
    outline = await db.scalar(
        select(Outline).where(Outline.project_id == project_id).order_by(Outline.version.desc())
    )
    if outline is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "尚未生成大纲")

    outline.status = "approved" if approved else "rejected"
    if approved and project.status == "topic_confirmed":
        project.status = "outline_confirmed"
    await db.commit()
    await db.refresh(outline)
    return outline


async def generate_script(
    db: AsyncSession,
    project_id: int,
    user_id: int,
    skill: str = "default",
    intensity: int = 3,
    length: int = 500,
) -> Script:
    if length not in LENGTH_OPTIONS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"length 只能为 {LENGTH_OPTIONS} 中之一"
        )
    project = await _get_owned_project(db, project_id, user_id)

    if llm.mock_enabled:
        content = _mock_script(project_id, length)
    else:
        system = (
            "你是短视频口播文案专家，按给定写作技巧/情绪强度输出 JSON 对象 {content}，"
            f"字数约 {length} 字。"
        )
        data = await llm.json(
            system,
            f"项目 #{project_id}，写作技巧={skill}，情绪强度={intensity}/5。",
        )
        content = data.get("content", "")
        await record_llm_usage(db, project_id=project_id)

    script = await db.scalar(select(Script).where(Script.project_id == project_id))
    if script is None:
        script = Script(project_id=project_id, current_version=1, content=content)
        db.add(script)
        await db.flush()
        new_version = 1
    else:
        new_version = script.current_version + 1
        script.current_version = new_version
        script.content = content

    db.add(
        ScriptVersion(
            script_id=script.id,
            version=new_version,
            content=content,
            note=f"全文生成（skill={skill}, intensity={intensity}, length={length}）",
        )
    )

    # 文案定稿推进状态机：outline_confirmed → script_finalized
    if project.status == "outline_confirmed":
        project.status = "script_finalized"

    await db.commit()
    await db.refresh(script)
    return script


async def rewrite_segment(
    db: AsyncSession, script_id: int, user_id: int, segment: str, instruction: str
) -> Script:
    script = await db.get(Script, script_id)
    if script is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文案不存在")
    project = await db.get(ContentProject, script.project_id)
    if project is None or project.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "项目不存在")

    if llm.mock_enabled:
        new_segment = f"{segment}「已按：{instruction} 改写（占位）」"
    else:
        data = await llm.json(
            "你是文案编辑，仅按指令改写给定段落，输出 JSON 对象 {content}。",
            f"原段落：{segment}\n改写指令：{instruction}",
        )
        new_segment = data.get("content", segment)
        await record_llm_usage(db, project_id=script.project_id)

    if script.content is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "文案为空，无法局部重写")

    replaced = script.content.replace(segment, new_segment, 1)
    new_version = script.current_version + 1
    script.content = replaced
    script.current_version = new_version

    db.add(
        ScriptVersion(
            script_id=script.id,
            version=new_version,
            content=replaced,
            note=f"局部重写：{instruction}",
        )
    )
    await db.commit()
    await db.refresh(script)
    return script
