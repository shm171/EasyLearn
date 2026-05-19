from __future__ import annotations

"""End-to-end debugging script for the AI learning core."""

import argparse
from pathlib import Path

from rich.console import Console
from rich.json import JSON

from ai_core.service import LearningAIService


console = Console()


def main() -> None:
    """Run a small manual debugging flow."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--course-id", default="debug_course")
    parser.add_argument("--file-path", required=True)
    parser.add_argument("--chapter-title", default="debug_chapter")
    parser.add_argument("--question", default="杩欑珷鐨勬牳蹇冨唴瀹规槸浠€涔堬紵")
    args = parser.parse_args()

    service = LearningAIService()
    ingest_result = service.ingest_pdf(args.course_id, args.file_path, args.chapter_title)
    console.print("[bold]Ingest[/bold]")
    console.print(JSON(ingest_result.model_dump_json(ensure_ascii=False)))

    answer = service.ask_pdf(args.course_id, args.question, args.chapter_title)
    console.print("[bold]Ask[/bold]")
    console.print(JSON(answer.model_dump_json(ensure_ascii=False)))

    summary = service.summarize_chapter(args.course_id, args.chapter_title)
    console.print("[bold]Summary[/bold]")
    console.print(JSON(summary.model_dump_json(ensure_ascii=False)))

    quiz = service.generate_programming_quiz(
        course_id=args.course_id,
        chapter_title=args.chapter_title,
        programming_language="cpp",
        difficulty="medium",
        question_types=["true_false", "fill_blank", "programming"],
        question_count=5,
    )
    output_path = Path("debug_outputs") / "quiz.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(quiz.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")
    console.print("[bold]Quiz[/bold]")
    console.print(JSON(quiz.model_dump_json(ensure_ascii=False)))
    console.print(f"Saved quiz to {output_path}")


if __name__ == "__main__":
    main()


