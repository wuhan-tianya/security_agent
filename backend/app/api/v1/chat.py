from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import get_agent_service
from app.api.v1.schemas import ChatStreamRequest
from app.services.agent_service import AgentService

# 上传文件保存目录
UPLOAD_DIR = Path(__file__).resolve().parents[3] / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {".apk"}
# 最大文件大小 500MB
MAX_FILE_SIZE = 500 * 1024 * 1024

router = APIRouter(tags=["chat"])


@router.post("/chat/stream")
async def chat_stream(req: ChatStreamRequest, service: AgentService = Depends(get_agent_service)):
    return StreamingResponse(
        service.stream_sse_events(
            session_id=req.session_id,
            user_input=req.user_input,
            model=None,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/chat/stream/upload")
async def chat_stream_with_upload(
    session_id: str = Form(...),
    user_input: str = Form(...),
    file: UploadFile | None = File(None),
    service: AgentService = Depends(get_agent_service),
):
    """支持文件上传的对话流式接口。

    接收 multipart/form-data，可选上传一个 APK 文件。
    文件会保存到 data/uploads/ 目录，文件路径会注入到 agent state 中
    供 skill 使用。
    """
    apk_path: str | None = None

    if file and file.filename:
        # 验证文件扩展名
        suffix = Path(file.filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型: {suffix}，仅支持 {', '.join(ALLOWED_EXTENSIONS)}",
            )

        # 生成唯一文件名，避免冲突
        unique_name = f"{uuid.uuid4().hex[:12]}_{file.filename}"
        save_path = UPLOAD_DIR / unique_name

        # 流式写入文件，避免内存溢出
        total_size = 0
        with open(save_path, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    save_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=400,
                        detail=f"文件大小超过限制 ({MAX_FILE_SIZE // (1024*1024)}MB)",
                    )
                f.write(chunk)

        apk_path = str(save_path)

    return StreamingResponse(
        service.stream_sse_events(
            session_id=session_id,
            user_input=user_input,
            model=None,
            apk_path=apk_path,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
