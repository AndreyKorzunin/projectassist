import os
import uuid
import time
from datetime import datetime
from typing import Dict, Any
import structlog
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import shutil

from gigachat_client import GigaChatClient
from document_processor import DocumentProcessor
from rag_engine import RAGEngine
from text_analyzer import TextAnalyzer
from grammar_checker import GrammarChecker
from models import UploadResponse, QueryRequest, QueryResponse, HealthResponse

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


app = FastAPI(
    title="DocAssistant AI",
    description="Интеллектуальный помощник для обработки документов с интеграцией GigaChat",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

origins = os.getenv("CORS_ORIGINS", "http://localhost:8000,http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)
os.makedirs("documents", exist_ok=True)

logger.info("initializing_components")

try:
    doc_processor = DocumentProcessor()
    logger.info("document_processor_initialized")
except Exception as e:
    logger.error("document_processor_init_failed", error=str(e))
    doc_processor = None

try:
    rag_engine = RAGEngine()
    logger.info("rag_engine_initialized")
except Exception as e:
    logger.error("rag_engine_init_failed", error=str(e))
    rag_engine = None

try:
    text_analyzer = TextAnalyzer()
    logger.info("text_analyzer_initialized")
except Exception as e:
    logger.error("text_analyzer_init_failed", error=str(e))
    text_analyzer = None

try:
    grammar_checker = GrammarChecker()
    logger.info("grammar_checker_initialized")
except Exception as e:
    logger.error("grammar_checker_init_failed", error=str(e))
    grammar_checker = None

try:
    gigachat_client = GigaChatClient()
    logger.info("gigachat_client_initialized")
except Exception as e:
    logger.error("gigachat_client_init_failed", error=str(e))
    gigachat_client = None

active_sessions: Dict[str, Dict[str, Any]] = {}
start_time = datetime.now()

logger.info("all_components_initialized")




@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Логирование всех запросов"""
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    logger.info("request_processed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration=f"{duration:.3f}s")

    return response


# ==================== Эндпоинты ====================

@app.get("/")
async def root():
    return {
        "service": "DocAssistant AI",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    uptime = datetime.now() - start_time

    gigachat_status = {"status": "disabled"}
    if gigachat_client:
        try:
            gigachat_status = gigachat_client.health_check()
        except Exception as e:
            gigachat_status = {"status": "error", "message": str(e)}

    rag_status = {
        "status": "active" if rag_engine else "disabled",
        "chunks_indexed": rag_engine.get_document_summary()["chunks_count"] if rag_engine and hasattr(rag_engine,
                                                                                                      'chunks') else 0
    }

    return HealthResponse(
        status="ok",
        version="1.0.0",
        gigachat=gigachat_status,
        rag=rag_status,
        uptime=str(uptime).split('.')[0],
        cache_enabled=gigachat_status.get("cache_enabled", False)
    )


@app.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):

    allowed_extensions = os.getenv("ALLOWED_EXTENSIONS", ".docx,.xlsx,.xls,.pdf").split(",")
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in allowed_extensions:
        logger.warning("invalid_file_extension", filename=file.filename, extension=file_ext)
        raise HTTPException(
            status_code=400,
            detail=f"Неподдерживаемый формат файла. Допустимые форматы: {', '.join(allowed_extensions)}"
        )

    max_size = int(os.getenv("MAX_UPLOAD_SIZE", 50)) * 1024 * 1024

    session_id = str(uuid.uuid4())
    safe_filename = f"{session_id}_{file.filename}"
    file_path = os.path.join("uploads", safe_filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_size = os.path.getsize(file_path)
        logger.info("file_uploaded", filename=file.filename, size=file_size, session_id=session_id)

        if not doc_processor:
            raise HTTPException(503, "Document processor not available")

        content = doc_processor.process(file_path)


        indexed = False
        if rag_engine:
            try:
                indexed = rag_engine.index_document(content)
                logger.info("document_indexed", session_id=session_id,
                            chunks=rag_engine.get_document_summary()["chunks_count"])
            except Exception as e:
                logger.error("rag_indexing_failed", error=str(e))
                indexed = False


        active_sessions[session_id] = {
            "session_id": session_id,
            "filename": file.filename,
            "file_path": file_path,
            "doc_type": content["metadata"]["type"],
            "content": content,
            "created_at": datetime.now(),
            "last_accessed": datetime.now()
        }


        structure_preview = {}
        if content["metadata"]["type"] == "word":
            structure_preview = {
                "headings_count": len(content.get("headings", [])),
                "paragraphs_count": len(content.get("paragraphs", [])),
                "tables_count": len(content.get("tables", [])),
                "lists_count": len(content.get("lists", []))
            }
        elif content["metadata"]["type"] == "excel":
            structure_preview = {
                "sheets_count": len(content.get("sheets", {})),
                "total_rows": sum(sheet["rows"] for sheet in content.get("sheets", {}).values())
            }
        elif content["metadata"]["type"] == "pdf":
            structure_preview = {
                "pages": content["metadata"].get("pages", 0)
            }

        logger.info("upload_complete", session_id=session_id, doc_type=content["metadata"]["type"])

        return UploadResponse(
            session_id=session_id,
            filename=file.filename,
            doc_type=content["metadata"]["type"],
            statistics=content.get("statistics", {}),
            structure_preview=structure_preview,
            indexed=indexed
        )

    except HTTPException:
        raise
    except Exception as e:

        if os.path.exists(file_path):
            os.remove(file_path)
        logger.error("upload_failed", error=str(e), filename=file.filename)
        raise HTTPException(500, f"Ошибка обработки документа: {str(e)}")


@app.post("/query", response_model=QueryResponse)
async def query_document(request: QueryRequest):

    start = time.time()

    if request.session_id not in active_sessions:
        logger.warning("session_not_found", session_id=request.session_id)
        raise HTTPException(404, "Сессия не найдена. Загрузите документ снова.")

    session = active_sessions[request.session_id]
    session["last_accessed"] = datetime.now()
    content = session["content"]

    try:
        if request.task_type == "answer":

            if not gigachat_client:
                raise HTTPException(503, "GigaChat недоступен. Проверьте настройки API.")

            if not rag_engine or not rag_engine.chunk_embeddings:
                raise HTTPException(400, "Документ не проиндексирован. Перезагрузите документ.")


            context = rag_engine.generate_context(request.query, top_k=4)

            if not context:
                logger.info("no_relevant_context", query=request.query[:50])
                return QueryResponse(
                    task_type="answer",
                    result="Не удалось найти релевантную информацию в документе. Попробуйте переформулировать вопрос.",
                    cached=False,
                    processing_time=round(time.time() - start, 2),
                    from_cache=False
                )


            response = gigachat_client.generate(
                context=context,
                query=request.query,
                task_type="answer"
            )

            logger.info("query_processed",
                        task_type=request.task_type,
                        cached=response.get("from_cache", False),
                        time=round(time.time() - start, 2))

            return QueryResponse(
                task_type="answer",
                result=response["response"],
                cached=response.get("cached", False),
                processing_time=round(time.time() - start, 2),
                from_cache=response.get("from_cache", False)
            )

        elif request.task_type == "grammar_check":
            if not grammar_checker or not grammar_checker.enabled:
                logger.warning("grammar_checker_disabled")
                return QueryResponse(
                    task_type="grammar_check",
                    result={
                        "status": "disabled",
                        "message": "Проверка грамматики недоступна. Установите language-tool-python."
                    },
                    processing_time=round(time.time() - start, 2),
                    from_cache=False
                )

            text = content.get("full_text", "")
            if not text:
                raise HTTPException(400, "Документ не содержит текста для проверки")


            text_to_check = text[:5000] if len(text) > 5000 else text
            issues = grammar_checker.check(text_to_check)


            style_analysis = grammar_checker.check_style(text_to_check)

            logger.info("grammar_check_complete",
                        issues=issues.get("total_issues", 0),
                        style_issues=style_analysis.get("total_issues", 0))

            return QueryResponse(
                task_type="grammar_check",
                result={
                    "grammar": issues,
                    "style": style_analysis
                },
                processing_time=round(time.time() - start, 2),
                from_cache=False
            )

        elif request.task_type == "find_repeats":
            if not text_analyzer:
                raise HTTPException(503, "Text analyzer недоступен")

            text = content.get("full_text", "")
            if not text:
                raise HTTPException(400, "Документ не содержит текста для анализа")

            repeats = text_analyzer.find_repetitions(text)

            logger.info("repeats_analysis_complete",
                        duplicates=len(repeats.get("exact_duplicates", [])),
                        common_words=len(repeats.get("common_words", [])))

            return QueryResponse(
                task_type="find_repeats",
                result=repeats,
                processing_time=round(time.time() - start, 2),
                from_cache=False
            )

        elif request.task_type == "structure_analysis":
            if not text_analyzer:
                raise HTTPException(503, "Text analyzer недоступен")

            analysis = text_analyzer.analyze_structure(content)

            logger.info("structure_analysis_complete",
                        doc_type=analysis.get("document_type", "unknown"),
                        quality=analysis.get("structure_quality", {}).get("quality", "N/A"))

            return QueryResponse(
                task_type="structure_analysis",
                result=analysis,
                processing_time=round(time.time() - start, 2),
                from_cache=False
            )

        else:
            logger.error("unknown_task_type", task_type=request.task_type)
            raise HTTPException(400, f"Неизвестный тип задачи: {request.task_type}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("query_processing_failed", error=str(e), task_type=request.task_type)
        raise HTTPException(500, f"Ошибка обработки запроса: {str(e)}")


@app.get("/sessions/{session_id}")
async def get_session_info(session_id: str):
    "
    if session_id not in active_sessions:
        raise HTTPException(404, "Сессия не найдена")

    session = active_sessions[session_id]
    return {
        "session_id": session["session_id"],
        "filename": session["filename"],
        "doc_type": session["doc_type"],
        "created_at": session["created_at"],
        "last_accessed": session["last_accessed"],
        "statistics": session["content"].get("statistics", {})
    }


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):

    if session_id not in active_sessions:
        raise HTTPException(404, "Сессия не найдена")

    session = active_sessions[session_id]


    if os.path.exists(session["file_path"]):
        os.remove(session["file_path"])
        logger.info("file_deleted", session_id=session_id, path=session["file_path"])


    del active_sessions[session_id]
    logger.info("session_deleted", session_id=session_id)

    return {"status": "deleted", "session_id": session_id}



app.mount("/static", StaticFiles(directory="../frontend"), name="static")

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    debug = os.getenv("DEBUG", "True") == "True"

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )