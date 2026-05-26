from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from tickerlens_api.auth.dependencies import require_admin_if_auth_enabled
from tickerlens_api.db.session import get_db
from tickerlens_api.documents.service import get_document
from tickerlens_api.pipeline.schemas import ProcessDocumentRequest, ProcessDocumentResponse
from tickerlens_api.pipeline.service import plan_document_processing, run_document_processing


router = APIRouter(tags=["pipeline"], dependencies=[Depends(require_admin_if_auth_enabled)])


@router.post("/documents/{doc_id}/process", response_model=ProcessDocumentResponse)
def process_document(
    doc_id: str,
    req: ProcessDocumentRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ProcessDocumentResponse:
    """
    Phase 9: Incremental processing orchestrator.

    Returns run ids for each stage and kicks off a best-effort sequential in-process execution.
    Clients can poll existing stage endpoints to observe completion:
    - GET /parse-runs/{run_id}
    - GET /chunk-runs/{run_id}
    - GET /embed-runs/{run_id}
    - GET /index-runs/{run_id}
    """

    doc = get_document(db, doc_id=doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        plan = plan_document_processing(db, doc_id=doc_id, req=req)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    should_run = any(
        s is not None and s.status != "succeeded" for s in (plan.parse, plan.chunk, plan.embed, plan.index)
    )
    if should_run:
        background_tasks.add_task(run_document_processing, doc_id=doc_id, req=req)

    return ProcessDocumentResponse(
        doc_id=doc_id,
        goal=req.goal,
        parse=plan.parse,
        chunk=plan.chunk,
        embed=plan.embed,
        index=plan.index,
        embedding_target=plan.embedding_target,
        index_target=plan.index_target,
    )
