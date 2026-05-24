from __future__ import annotations

"""Command-line debugging interface for the AI learning core."""

from pathlib import Path
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ai_core.config import get_settings
from ai_core.model_factory import get_chat_model
from ai_core.rag.pdf_loader import PDFLoaderManager
from ai_core.rag.retriever import PDFRetriever
from ai_core.rag.text_splitter import PDFTextSplitter
from ai_core.rag.vector_store import DocumentKnowledgeBase
from ai_core.schemas import Quiz
from ai_core.service import LearningAIService


app = typer.Typer(help="AI programming learning core CLI")
console = Console()


@app.command()
def health() -> None:
    """Check environment, providers, API keys, and local directories."""

    settings = get_settings()
    table = Table(title="AI Core Health")
    table.add_column("Item")
    table.add_column("Value")
    table.add_column("Status")

    env_path = Path(".env")
    vector_path = settings.vector_db_path
    vector_path.mkdir(parents=True, exist_ok=True)

    table.add_row("Python", "3.10+", "OK")
    table.add_row(".env", str(env_path.resolve()), "OK" if env_path.exists() else "Missing, using environment/defaults")
    table.add_row("AI_PROVIDER", settings.ai_provider, "OK")
    table.add_row("EMBEDDING_PROVIDER", settings.embedding_provider, "OK")
    table.add_row("VECTOR_DB_DIR", str(vector_path.resolve()), "OK")

    api_key_status = _api_key_status(settings.ai_provider)
    embedding_key_status = _api_key_status(settings.embedding_provider, embedding=True)
    table.add_row("Chat API key", settings.ai_provider, api_key_status)
    if settings.embedding_provider.lower() == "huggingface":
        table.add_row("Embedding", f"Local embedding: {settings.huggingface_embedding_model}", "OK")
    else:
        table.add_row("Embedding API key", settings.embedding_provider, embedding_key_status)
    console.print(table)


@app.command("test-model")
def test_model(provider: str = typer.Option(..., help="openai, gemini, or deepseek")) -> None:
    """Test one chat model provider with a small prompt."""

    model = get_chat_model(provider)
    response = model.invoke("Reply in one short sentence: the AI programming learning platform model connection is working.")
    console.print(getattr(response, "content", response))


@app.command("load-pdf")
def load_pdf(file_path: str = typer.Option(..., help="Path to a local PDF file")) -> None:
    """Load and split a PDF without calling AI or vector search."""

    loader = PDFLoaderManager()
    splitter = PDFTextSplitter()
    documents = loader.load_pdf(file_path=file_path, course_id="debug", chapter_title="debug")
    chunks = splitter.split_documents(documents)
    preview = chunks[0].page_content[:500] if chunks else ""
    console.print(f"Pages: {len(documents)}")
    console.print(f"Chunks: {len(chunks)}")
    console.print("[bold]Preview[/bold]")
    console.print(preview)


@app.command()
def ingest(
    course_id: str = typer.Option(...),
    file_path: str = typer.Option(...),
    chapter_title: Optional[str] = typer.Option(None),
) -> None:
    """Import a PDF into the local Chroma knowledge base."""

    service = LearningAIService()
    result = service.ingest_pdf(course_id=course_id, file_path=file_path, chapter_title=chapter_title)
    _print_model_json(result)


@app.command()
def search(
    course_id: str = typer.Option(...),
    query: str = typer.Option(...),
    chapter_title: Optional[str] = typer.Option(None),
    top_k: int = typer.Option(5),
) -> None:
    """Search the vector database without calling a chat model."""

    retriever = PDFRetriever(DocumentKnowledgeBase())
    chunks = retriever.retrieve(query=query, course_id=course_id, chapter_title=chapter_title, top_k=top_k)
    table = Table(title="Search Results")
    table.add_column("chunk_id")
    table.add_column("score")
    table.add_column("page")
    table.add_column("preview")
    for chunk in chunks:
        table.add_row(
            chunk.chunk_id,
            f"{chunk.score:.4f}" if chunk.score is not None else "",
            str(chunk.page_number or ""),
            _safe_console_text(chunk.content[:240].replace("\n", " ")),
        )
    console.print(table)


@app.command()
def ask(
    course_id: str = typer.Option(...),
    question: str = typer.Option(...),
    chapter_title: Optional[str] = typer.Option(None),
) -> None:
    """Ask a PDF-grounded question using the reading agent."""

    service = LearningAIService()
    result = service.ask_pdf(course_id=course_id, question=question, chapter_title=chapter_title)
    _print_model_json(result)


@app.command()
def summarize(
    course_id: str = typer.Option(...),
    chapter_title: str = typer.Option(...),
    output: Optional[str] = typer.Option(None),
) -> None:
    """Generate a structured chapter summary."""

    service = LearningAIService()
    result = service.summarize_chapter(course_id=course_id, chapter_title=chapter_title)
    _print_or_write(result.model_dump_json(indent=2, ensure_ascii=False), output)


@app.command()
def quiz(
    course_id: str = typer.Option(...),
    chapter_title: str = typer.Option(...),
    programming_language: str = typer.Option("cpp"),
    difficulty: str = typer.Option("medium"),
    question_types: str = typer.Option(..., help="Comma-separated question types"),
    question_count: int = typer.Option(5),
    output: Optional[str] = typer.Option(None),
) -> None:
    """Generate a structured programming quiz."""

    service = LearningAIService()
    type_list = [item.strip() for item in question_types.split(",") if item.strip()]
    result = service.generate_programming_quiz(
        course_id=course_id,
        chapter_title=chapter_title,
        programming_language=programming_language,
        difficulty=difficulty,
        question_types=type_list,
        question_count=question_count,
    )
    _print_or_write(result.model_dump_json(indent=2, ensure_ascii=False), output)


@app.command()
def evaluate(
    quiz_file: str = typer.Option(...),
    answers_file: str = typer.Option(...),
    output: Optional[str] = typer.Option(None),
) -> None:
    """Evaluate answers from JSON files."""

    quiz_data = Quiz.model_validate_json(Path(quiz_file).read_text(encoding="utf-8"))
    answers_data = Path(answers_file).read_text(encoding="utf-8")
    import json

    user_answers = json.loads(answers_data)
    service = LearningAIService()
    result = service.evaluate_answers(quiz=quiz_data, user_answers=user_answers)
    _print_or_write(result.model_dump_json(indent=2, ensure_ascii=False), output)


def _print_or_write(content: str, output: str | None) -> None:
    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        console.print(f"Saved to {output_path}")
    else:
        console.print(_safe_console_text(content))


def _print_model_json(model: object) -> None:
    content = model.model_dump_json(indent=2, ensure_ascii=False)  # type: ignore[attr-defined]
    console.print(_safe_console_text(content))


def _api_key_status(provider: str, embedding: bool = False) -> str:
    settings = get_settings()
    selected = provider.lower()
    if selected == "openai":
        return "OK" if settings.openai_api_key else "Missing OPENAI_API_KEY"
    if selected == "gemini":
        return "OK" if settings.google_api_key else "Missing GOOGLE_API_KEY"
    if selected == "huggingface":
        return "OK" if embedding else "Unsupported chat provider"
    if selected == "deepseek":
        if embedding:
            return "Unsupported for embeddings; use huggingface, openai, or gemini"
        return "OK" if settings.deepseek_api_key else "Missing DEEPSEEK_API_KEY"
    return "Unsupported provider"


def _safe_console_text(text: str) -> str:
    """Replace characters the active Windows console encoding cannot print."""

    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


if __name__ == "__main__":
    app()


