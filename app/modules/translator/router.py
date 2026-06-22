"""HTTP API for document and subtitle translation."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app.modules.translator.service import TranslationJob, TranslatorService

router = APIRouter(prefix="/translator", tags=["translator"])
_SERVICE = TranslatorService()


class TranslateReadmeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    markdown: str = Field(min_length=1)
    target_language: str
    llm_provider: str | None = None
    translation_mode: Literal["literal", "combined"] = "literal"
    thematic_block: str | None = None
    title_seed: str | None = None


class TranslateStartResponse(BaseModel):
    request_id: str


class TranslateStatusResponse(BaseModel):
    request_id: str
    status: str
    phase: str | None = None
    original_markdown: str | None = None
    translated_markdown: str | None = None
    target_language: str | None = None
    error: str | None = None
    job_type: str | None = None
    translated_subtitles: str | None = None
    original_transcript: str | None = None
    progress: float | None = None
    error_code: str | None = None
    result_links: dict[str, str] | None = None
    source_filename: str | None = None
    source_format: str | None = None


def get_translator_service() -> TranslatorService:
    return _SERVICE


@router.post("/translate/readme", response_model=TranslateStartResponse)
def translate_readme(
    payload: TranslateReadmeRequest,
    service: TranslatorService = Depends(get_translator_service),
) -> TranslateStartResponse:
    job = service.start_readme(
        payload.markdown,
        payload.target_language.lower().strip(),
        translation_mode=payload.translation_mode,
        llm_provider=payload.llm_provider,
    )
    _raise_if_failed(job)
    return TranslateStartResponse(request_id=job.request_id)


@router.post("/translate/document", response_model=TranslateStartResponse)
async def translate_document(
    file: UploadFile = File(...),
    target_language: str = Form(...),
    translation_mode: Literal["literal", "combined"] = Form("literal"),
    llm_provider: str | None = Form(None),
    service: TranslatorService = Depends(get_translator_service),
) -> TranslateStartResponse:
    content = await file.read()
    job = service.start_document(
        file.filename or "document.txt",
        content,
        target_language.lower().strip(),
        translation_mode=translation_mode,
        llm_provider=llm_provider,
    )
    _raise_if_failed(job)
    return TranslateStartResponse(request_id=job.request_id)


@router.post("/translate/video", response_model=TranslateStartResponse)
async def translate_video(
    file: UploadFile = File(...),
    target_language: str = Form(...),
    output_mode: Literal["subtitles_only", "burned_video", "both"] = Form("subtitles_only"),
    subtitle_style: Literal["boxed", "outline"] = Form("boxed"),
    transcript_text: str | None = Form(None),
    llm_provider: str | None = Form(None),
    service: TranslatorService = Depends(get_translator_service),
) -> TranslateStartResponse:
    content = await file.read()
    job = service.start_video(
        file.filename or "transcript.txt",
        content,
        target_language.lower().strip(),
        transcript_text=transcript_text,
        output_mode=output_mode,
        subtitle_style=subtitle_style,
        llm_provider=llm_provider,
    )
    _raise_if_failed(job)
    return TranslateStartResponse(request_id=job.request_id)


@router.get("/translate/status/{request_id}", response_model=TranslateStatusResponse)
def translation_status(
    request_id: str,
    service: TranslatorService = Depends(get_translator_service),
) -> TranslateStatusResponse:
    job = _job_or_404(service, request_id)
    return TranslateStatusResponse.model_validate(job.status_payload())


@router.get("/translate/subtitles/{request_id}")
def download_subtitles(
    request_id: str,
    service: TranslatorService = Depends(get_translator_service),
) -> Response:
    artifact = service.get_artifact(request_id, "srt")
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Субтитры не найдены")
    return _artifact_response(artifact.content, artifact.media_type, artifact.filename)


@router.get("/translate/download/{request_id}")
def download_artifact(
    request_id: str,
    type: str = Query(..., alias="type"),
    service: TranslatorService = Depends(get_translator_service),
) -> Response:
    artifact = service.get_artifact(request_id, type.lower().strip())
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Файл типа {type!r} недоступен")
    return _artifact_response(artifact.content, artifact.media_type, artifact.filename)


def _job_or_404(service: TranslatorService, request_id: str) -> TranslationJob:
    job = service.get_job(request_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="translation job not found")
    return job


def _raise_if_failed(job: TranslationJob) -> None:
    if job.status == "failed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=job.error or "translation failed")


def _artifact_response(content: bytes, media_type: str, filename: str) -> Response:
    return Response(content=content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
