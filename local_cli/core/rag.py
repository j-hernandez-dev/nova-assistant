"""Coarse project-retrieval port; no conversational memory or algorithm policy."""

from typing import Any, Protocol


class RAGError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.safe_message = code, message

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "category": "RAG", "message": self.safe_message}


class ProjectRetrievalPort(Protocol):
    def index(self) -> dict[str, int]: ...
    def query(self, text: str, top_k: int) -> list[dict[str, Any]]: ...
