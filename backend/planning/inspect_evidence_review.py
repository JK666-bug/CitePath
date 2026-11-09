"""第七步开发入口。

默认只准备输入；--call-model 才调用模型。
--allow-images 显式启用图片输入。
"""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

from planning.document_reader import open_document_reader
from planning.evidence_review import (
    REVIEW_PROMPT,
    ReviewLimits,
    load_candidate_input,
    make_review_decider,
    run_evidence_review,
    safe_api_error,
)


BACKEND_DIR = Path(__file__).resolve().parents[1]


def save_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    for name in ("user-id", "course-id", "document-id"):
        parser.add_argument(f"--{name}", type=int, required=True)

    parser.add_argument("--candidates-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--resume", type=Path)

    parser.add_argument("--call-model", action="store_true")
    parser.add_argument("--allow-images", action="store_true")

    parser.add_argument("--max-model-calls", type=int, default=8)
    parser.add_argument("--max-tool-pages", type=int, default=16)
    parser.add_argument("--max-image-pages", type=int, default=2)
    parser.add_argument("--max-input-chars", type=int, default=60000)
    parser.add_argument("--max-output-tokens", type=int, default=3000)
    parser.add_argument("--max-no-progress", type=int, default=2)
    parser.add_argument("--image-side", type=int, default=1600)

    args = parser.parse_args()

    limits = ReviewLimits(
        max_model_calls=args.max_model_calls,
        max_tool_pages=args.max_tool_pages,
        max_image_pages=args.max_image_pages,
        max_input_chars=args.max_input_chars,
        max_output_tokens=args.max_output_tokens,
        max_no_progress=args.max_no_progress,
        image_side=args.image_side,
    )
    limits.validate()

    output = args.output_dir.expanduser().resolve()

    # 必须使用新目录，避免混入上次的报告或图片。
    output.mkdir(parents=True, exist_ok=False)

    # 输入报告不匹配、原件不可读等入口错误，也保存明确的失败报告。
    save_json(output / "request.json", {
        "identity": {"user_id": args.user_id, "course_id": args.course_id,
                     "document_id": args.document_id},
        "source_report": str(args.candidates_report),
        "limits": asdict(limits),
        "allow_images": args.allow_images,
    })
    try:
        return execute(args, limits, output)
    except (Exception, KeyboardInterrupt) as error:
        report_path = output / "review.json"
        # 尽可能保留已经读取的证据与调用轨迹，不用入口错误覆盖已完成工作。
        retained = {}
        if report_path.is_file():
            try:
                retained = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
        interrupted = isinstance(error, KeyboardInterrupt)
        retained.update({
            "stage": "evidence_review",
            "status": "interrupted" if interrupted else "failed",
            "error": {**safe_api_error(error),
                      "code": getattr(error, "code", "review_entry_failed"),
                      "issue": getattr(error, "issue", None)},
            "ready_for_practice": False,
            "semantic_coverage_verified": False,
        })
        save_json(report_path, retained)
        print("Status:", retained["status"], flush=True)
        print("Report:", report_path, flush=True)
        print("Error:", retained["error"], flush=True)
        return 130 if interrupted else 1


def execute(args, limits, output):
    """已创建独立目录后执行；所有入口异常由 main 记录。"""
    load_dotenv(BACKEND_DIR / ".env")

    reader = open_document_reader(
        user_id=args.user_id,
        course_id=args.course_id,
        document_id=args.document_id,
    )

    source = load_candidate_input(
        reader,
        args.candidates_report.expanduser().resolve(),
    )

    save_json(
        output / "request.json",
        {
            "system_prompt": REVIEW_PROMPT,
            "identity": source["identity"],
            "input_fingerprint": source["fingerprint"],
            "source_report": str(args.candidates_report),
            "limits": asdict(limits),
            "allow_images": args.allow_images,
            "questions": source["questions"],
        },
    )

    print("Questions:", len(source["questions"]), flush=True)

    if not args.call_model:
        save_json(
            output / "review.json",
            {
                "stage": "evidence_review",
                "status": "prepared",
                "source": source,
            },
        )
        print("Status: prepared")
        print("No model was called.")
        return 0

    resume = None

    if args.resume is not None:
        resume = json.loads(
            args.resume.read_text(encoding="utf-8")
        )

    def checkpoint(state, store):
        save_json(output / "review.json", state)

        if store.images:
            image_dir = output / "images"
            image_dir.mkdir(exist_ok=True)

            for number, png in store.images.items():
                destination = image_dir / f"page-{number:04d}.png"

                if not destination.exists():
                    destination.write_bytes(png)

    # 没有待解决问题时直接进入第八步，不额外初始化模型连接。
    decider = None

    def decide(payload, images):
        nonlocal decider
        if decider is None:
            decider = make_review_decider(limits.max_output_tokens)
        return decider(payload, images)

    result = run_evidence_review(
        reader,
        source,
        decide,
        limits=limits,
        allow_images=args.allow_images,
        resume=resume,
        on_update=checkpoint,
    )

    print("Status:", result["status"])
    print("Report:", output / "review.json")
    print("Model calls:", result["model_calls"])
    print("Tool pages:", result["tool_pages"])
    print("Stop reason:", result["stop_reason"])
    print("Published chapters: False")

    return (
        0
        if result["status"] == "ready_for_coverage_review"
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
