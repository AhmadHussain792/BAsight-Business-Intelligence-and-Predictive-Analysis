"""
FastAPI application entrypoint. LLM chat is intentionally left out —
that lands separately once it's built as a constrained tool-calling
agent rather than open code-gen (see project notes).
"""
from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .ingestion import EmptyFileError, UnsupportedFileError, clean_dataframe, read_uploaded_file
from .insights import compute_insights
from .models import ChatRequest, ChatResponse, ChatToolCall, DatasetListItem, DatasetResponse, SchemaResponse
from .schema_detection import build_column_schema, build_data_quality_report, detect_core_columns
from .storage import DatasetNotFoundError, dataset_store
from .agent.conversation_store import conversation_store
from .agent.llm_factory import get_llm_client
from .agent.orchestrator import run_agent_turn

app = FastAPI(
    title="GenAI Business Analyst API",
    version="0.2.0",
    description="Data ingestion, cleaning, schema detection, and insights for the SME analytics platform.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _record_to_response(dataset_id: str) -> DatasetResponse:
    record = dataset_store.get(dataset_id)
    insights = compute_insights(record.df, record.core_columns)
    schema = SchemaResponse(
        row_count=len(record.df),
        column_count=len(record.columns),
        columns=record.columns,
        detected_roles=record.core_columns,
        data_quality=record.data_quality,
    )
    return DatasetResponse(
        dataset_id=dataset_id,
        filename=record.filename,
        schema_summary=schema,
        insights=insights,
    )


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/datasets", response_model=DatasetResponse)
async def upload_dataset(file: UploadFile):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file was uploaded.")

    extension = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if extension not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{extension}'. Allowed: {', '.join(sorted(settings.ALLOWED_EXTENSIONS))}",
        )

    contents = await file.read()
    if len(contents) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB}MB upload limit.",
        )

    try:
        raw_df = read_uploaded_file(file.filename, contents)
        clean_df, cleaning_report = clean_dataframe(raw_df)
    except (UnsupportedFileError, EmptyFileError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # last-resort guard so a bad file 500s cleanly, not silently
        raise HTTPException(status_code=400, detail=f"Could not process file: {exc}") from exc

    if clean_df.empty:
        raise HTTPException(
            status_code=400,
            detail="After removing empty rows/columns, no usable data remained in this file.",
        )

    columns = build_column_schema(clean_df)
    core_columns = detect_core_columns(columns)
    data_quality = build_data_quality_report(clean_df, columns)
    # Surface cleaning-time assumptions (e.g. ambiguous date format guesses)
    # as warnings too, rather than dropping them on the floor.
    data_quality.warnings.extend(
        f"Column '{col}': {note}" for col, note in cleaning_report.date_format_notes.items()
    )

    dataset_id = dataset_store.put(
        filename=file.filename,
        df=clean_df,
        columns=columns,
        core_columns=core_columns,
        data_quality=data_quality,
    )

    return _record_to_response(dataset_id)


@app.get("/api/datasets", response_model=list[DatasetListItem])
def list_datasets():
    return [
        DatasetListItem(
            dataset_id=r.dataset_id,
            filename=r.filename,
            row_count=len(r.df),
            column_count=len(r.columns),
            uploaded_at=r.created_at.isoformat(),
        )
        for r in dataset_store.list_all()
    ]


@app.get("/api/datasets/{dataset_id}", response_model=DatasetResponse)
def get_dataset(dataset_id: str):
    try:
        return _record_to_response(dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/datasets/{dataset_id}/schema", response_model=SchemaResponse)
def get_dataset_schema(dataset_id: str):
    try:
        record = dataset_store.get(dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return SchemaResponse(
        row_count=len(record.df),
        column_count=len(record.columns),
        columns=record.columns,
        detected_roles=record.core_columns,
        data_quality=record.data_quality,
    )


@app.get("/api/datasets/{dataset_id}/insights")
def get_dataset_insights(dataset_id: str):
    try:
        record = dataset_store.get(dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return compute_insights(record.df, record.core_columns)


@app.delete("/api/datasets/{dataset_id}")
def delete_dataset(dataset_id: str):
    try:
        dataset_store.delete(dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "deleted", "dataset_id": dataset_id}


@app.post("/api/datasets/{dataset_id}/chat", response_model=ChatResponse)
def chat_with_dataset(dataset_id: str, request: ChatRequest, llm=Depends(get_llm_client)):
    try:
        record = dataset_store.get(dataset_id)
    except DatasetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    history = conversation_store.get_history(dataset_id)
    try:
        result = run_agent_turn(llm, record, history, request.message)
    except Exception as exc:  # noqa: BLE001 — a request-time LLM call failure (auth, network,
        # quota) should reach the client as a clean 503, not an unhandled 500 with a raw
        # traceback. Broad on purpose: the failure modes here span multiple exception types
        # (google.auth errors, google.genai API errors, network errors) that aren't worth
        # enumerating individually — anything from the LLM call itself is a service
        # availability problem from the caller's point of view, not a client error.
        raise HTTPException(status_code=503, detail=f"Chat is temporarily unavailable: {exc}") from exc

    conversation_store.save_history(dataset_id, result.messages)

    return ChatResponse(
        answer=result.answer,
        tool_calls=[ChatToolCall(name=tc.name, ok=tc.ok, summary=tc.summary) for tc in result.tool_calls],
        hit_iteration_limit=result.hit_iteration_limit,
    )


@app.delete("/api/datasets/{dataset_id}/chat")
def reset_chat(dataset_id: str):
    conversation_store.clear(dataset_id)
    return {"status": "cleared", "dataset_id": dataset_id}
