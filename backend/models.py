from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime




class UploadResponse(BaseModel):

    session_id: str = Field(..., description="Уникальный идентификатор сессии")
    filename: str = Field(..., description="Имя файла")
    doc_type: str = Field(..., description="Тип документа: word, excel, pdf")
    statistics: Dict[str, Any] = Field(..., description="Статистика документа")
    structure_preview: Dict[str, Any] = Field(..., description="Превью структуры")
    indexed: bool = Field(..., description="Успешно ли проиндексирован документ")


class QueryRequest(BaseModel):

    session_id: str = Field(..., description="Идентификатор сессии", min_length=1)
    query: str = Field(..., description="Вопрос или запрос пользователя", min_length=1, max_length=1000)
    task_type: str = Field(
        default="answer",
        description="Тип задачи",
        pattern="^(answer|grammar_check|find_repeats|structure_analysis)$"
    )

    @field_validator('query')
    @classmethod
    def validate_query(cls, v):
        if len(v.strip()) < 3:
            raise ValueError('Запрос должен содержать минимум 3 символа')
        return v.strip()


class QueryResponse(BaseModel):

    task_type: str = Field(..., description="Тип задачи")
    result: Any = Field(..., description="Результат обработки")
    cached: Optional[bool] = Field(default=False, description="Ответ из кэша")
    processing_time: Optional[float] = Field(default=None, description="Время обработки в секундах")
    from_cache: Optional[bool] = Field(default=False, description="Получено из кэша")



class HealthResponse(BaseModel):

    status: str = Field(..., description="Статус сервиса: ok/error")
    version: str = Field(default="1.0.0", description="Версия сервиса")
    gigachat: Dict[str, Any] = Field(..., description="Статус подключения к GigaChat")
    rag: Dict[str, Any] = Field(..., description="Статус RAG системы")
    uptime: str = Field(..., description="Время работы сервиса")
    cache_enabled: bool = Field(..., description="Включено ли кэширование")