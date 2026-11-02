"""Read-only views of what static analysis found in a repository's latest analysis."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.api.deps import get_completed_analysis
from app.db.session import get_db
from app.models import (
    AnalysisFile,
    CodeImport,
    CodeSymbol,
    ProjectDependency,
    RepositoryAnalysis,
)
from app.schemas.repository import (
    DependencyOut,
    FileContent,
    FileEntry,
    ImportOut,
    SymbolMatch,
    SymbolOut,
)
from app.storage import artifacts

router = APIRouter(prefix="/repositories/{repository_id}", tags=["code"])

MAX_IMPORTED_BY = 200


@router.get("/files", response_model=list[FileEntry])
def list_files(
    analysis: RepositoryAnalysis = Depends(get_completed_analysis), db: Session = Depends(get_db)
) -> list[AnalysisFile]:
    return list(
        db.scalars(
            select(AnalysisFile)
            .where(AnalysisFile.analysis_id == analysis.id)
            .order_by(AnalysisFile.path)
        )
    )


@router.get("/files/content", response_model=FileContent)
def read_file(
    path: str = Query(min_length=1, max_length=1000),
    analysis: RepositoryAnalysis = Depends(get_completed_analysis),
    db: Session = Depends(get_db),
) -> FileContent:
    # Only paths recorded in the database as stored files are served, so a crafted
    # path like "../../etc/passwd" never reaches the filesystem lookup.
    record = db.scalar(
        select(AnalysisFile).where(
            AnalysisFile.analysis_id == analysis.id,
            AnalysisFile.path == path,
            AnalysisFile.skipped_reason.is_(None),
        )
    )
    data = artifacts.read_source_file(analysis.id, path) if record else None
    if record is None or data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found")

    symbols = db.scalars(
        select(CodeSymbol).where(CodeSymbol.file_id == record.id).order_by(CodeSymbol.start_line)
    )
    target = aliased(AnalysisFile)
    import_rows = db.execute(
        select(CodeImport, target.path)
        .outerjoin(target, CodeImport.resolved_file_id == target.id)
        .where(CodeImport.file_id == record.id)
        .order_by(CodeImport.line, CodeImport.module)
    )
    imported_by = db.scalars(
        select(AnalysisFile.path)
        .join(CodeImport, CodeImport.file_id == AnalysisFile.id)
        .where(CodeImport.resolved_file_id == record.id)
        .distinct()
        .order_by(AnalysisFile.path)
        .limit(MAX_IMPORTED_BY)
    )
    return FileContent(
        path=record.path,
        language=record.language,
        size_bytes=record.size_bytes,
        line_count=record.line_count,
        content=data.decode("utf-8", errors="replace"),
        parse_error=record.parse_error,
        importance_reasons=record.importance_reasons or [],
        symbols=[SymbolOut.model_validate(s) for s in symbols],
        imports=[
            ImportOut(
                module=row.module, names=row.names or [], line=row.line, resolved_path=resolved
            )
            for row, resolved in import_rows
        ],
        imported_by=list(imported_by),
    )


@router.get("/dependencies", response_model=list[DependencyOut])
def list_dependencies(
    analysis: RepositoryAnalysis = Depends(get_completed_analysis), db: Session = Depends(get_db)
) -> list[ProjectDependency]:
    return list(
        db.scalars(
            select(ProjectDependency)
            .where(ProjectDependency.analysis_id == analysis.id)
            .order_by(
                ProjectDependency.source_file,
                ProjectDependency.line.nulls_last(),
                ProjectDependency.name,
            )
        )
    )


@router.get("/symbols", response_model=list[SymbolMatch])
def search_symbols(
    q: str = Query(default="", max_length=100),
    kind: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=50, ge=1, le=200),
    analysis: RepositoryAnalysis = Depends(get_completed_analysis),
    db: Session = Depends(get_db),
) -> list[SymbolMatch]:
    """Find functions, classes and methods by name."""
    query = (
        select(CodeSymbol, AnalysisFile.path)
        .join(AnalysisFile, AnalysisFile.id == CodeSymbol.file_id)
        .where(CodeSymbol.analysis_id == analysis.id)
        .order_by(CodeSymbol.name, AnalysisFile.path, CodeSymbol.start_line)
        .limit(limit)
    )
    if q:
        # Escape LIKE wildcards so a search for "100%" or "a_b" means exactly that.
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(CodeSymbol.qualified_name.ilike(f"%{escaped}%", escape="\\"))
    if kind:
        query = query.where(CodeSymbol.kind == kind)
    return [
        SymbolMatch(**SymbolOut.model_validate(symbol).model_dump(), path=path)
        for symbol, path in db.execute(query)
    ]
