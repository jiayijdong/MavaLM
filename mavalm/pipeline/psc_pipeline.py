#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


SCRIPT_PATH = Path(__file__).resolve()
PACKAGE_ROOT = SCRIPT_PATH.parents[1]
DEFAULT_REPO_ROOT = Path.cwd()
ANNOTATION_AGENT_PATH = PACKAGE_ROOT / "annotation" / "annotation_agent.py"
EVALUATION_AGENT_PATH = PACKAGE_ROOT / "verification" / "verification_agent.py"


class PipelineState(TypedDict):
    repo_root: str
    doi_folder: str
    extraction_model: str
    judge_model: str
    skip_extraction: bool
    dry_run: bool
    force_evaluation: bool
    pdf_folder: NotRequired[str]
    annotation_output_folder: NotRequired[str]
    evaluation_output_folder: NotRequired[str]
    ground_truth_file: NotRequired[str]
    candidate_file: NotRequired[str]
    evaluation_file: NotRequired[str]
    result: NotRequired[dict[str, Any]]
    evaluation: NotRequired[dict[str, Any]]
    summary: NotRequired[dict[str, Any]]


def load_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


annotation_agent = load_module("mavalm_annotation_agent", ANNOTATION_AGENT_PATH)
evaluation_agent = load_module("mavalm_verification_agent", EVALUATION_AGENT_PATH)


def require_openai_key(dry_run: bool) -> None:
    if dry_run:
        return

    if not os.environ.get("OPENAI_API_KEY"):
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Export it before running without --dry-run."
        )


def first_file(folder: Path, pattern: str) -> Path:
    files = sorted(folder.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No file matching {pattern!r} in {folder}")
    return files[0]


def newest_candidate_file(folder: Path) -> Path:
    files = sorted(
        folder.glob(evaluation_agent.MODEL_FILE_PATTERN),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not files:
        raise FileNotFoundError(
            f"No file matching {evaluation_agent.MODEL_FILE_PATTERN!r} in {folder}"
        )

    non_dry_run_files = [path for path in files if "dry_run" not in path.name]
    return non_dry_run_files[0] if non_dry_run_files else files[0]


def save_json(data: dict[str, Any], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def resolve_inputs(state: PipelineState) -> PipelineState:
    repo_root = Path(state["repo_root"]).expanduser().resolve()
    doi_folder = state["doi_folder"]

    pdf_folder = repo_root / "KB" / doi_folder
    annotation_output_folder = repo_root / "dataset" / "annotation" / "recent" / doi_folder
    evaluation_output_folder = repo_root / "dataset" / "evaluation" / "recent" / doi_folder
    gt_folder = repo_root / "dataset" / "GT" / "recent" / doi_folder
    ground_truth_file = first_file(gt_folder, evaluation_agent.GROUND_TRUTH_PATTERN)

    if not state["skip_extraction"] and not state["dry_run"] and not pdf_folder.exists():
        raise FileNotFoundError(f"PDF folder does not exist: {pdf_folder}")

    return {
        **state,
        "repo_root": str(repo_root),
        "pdf_folder": str(pdf_folder),
        "annotation_output_folder": str(annotation_output_folder),
        "evaluation_output_folder": str(evaluation_output_folder),
        "ground_truth_file": str(ground_truth_file),
    }


def extract_annotation(state: PipelineState) -> PipelineState:
    pdf_folder = Path(state["pdf_folder"])
    annotation_output_folder = Path(state["annotation_output_folder"])

    if state["skip_extraction"]:
        candidate_file = newest_candidate_file(annotation_output_folder)
        logger.info("Skipping extraction; using existing candidate: %s", candidate_file)
        return {**state, "candidate_file": str(candidate_file)}

    if state["dry_run"]:
        output_file = annotation_output_folder / (
            f"Device_BestPCE_langgraph_dry_run_{state['doi_folder']}.json"
        )
        result = annotation_agent.normalize_result_keys(
            {
                "Ref_DOI": state["doi_folder"].replace("_", "/"),
                "Ref_title": "Dry run placeholder",
                "JV_measured_reverse_scan_PCE": "Null",
            }
        )
        save_json(result, output_file)
        logger.info("Dry-run extraction wrote placeholder candidate: %s", output_file)
        return {**state, "candidate_file": str(output_file), "result": result}

    logger.info("Loading PDFs from %s", pdf_folder)
    combined_text = annotation_agent.load_all_pdfs_from_folder(pdf_folder)

    result = annotation_agent.run_extraction_agent(
        model_name=state["extraction_model"],
        folder_path=pdf_folder,
        combined_text=combined_text,
    )

    output_file = annotation_agent.save_result(
        result=result,
        output_folder=annotation_output_folder,
        model_name=state["extraction_model"],
        doi_folder=state["doi_folder"],
    )
    logger.info("Extraction saved candidate: %s", output_file)
    return {**state, "candidate_file": str(output_file), "result": result}


def build_evaluation_agent(judge_model: str):
    model = init_chat_model(judge_model, temperature=0)
    return create_agent(
        model=model,
        system_prompt=evaluation_agent.JUDGE_SYSTEM_PROMPT,
        tools=[evaluation_agent.get_comparison_data],
        context_schema=evaluation_agent.EvaluationContext,
        checkpointer=InMemorySaver(),
    )


def evaluate_annotation(state: PipelineState) -> PipelineState:
    candidate_file = Path(state["candidate_file"])
    ground_truth_file = Path(state["ground_truth_file"])
    evaluation_output_folder = Path(state["evaluation_output_folder"])
    evaluation_output_folder.mkdir(parents=True, exist_ok=True)

    output_file = evaluation_output_folder / evaluation_agent.get_output_filename(
        candidate_file,
        state["judge_model"],
    )
    if state["dry_run"]:
        output_file = output_file.with_name(f"{output_file.stem}_dry_run{output_file.suffix}")

    if output_file.exists() and not state["force_evaluation"]:
        logger.info("Skipping existing evaluation: %s", output_file)
        evaluation = evaluation_agent.read_json(output_file)
        return {
            **state,
            "evaluation_file": str(output_file),
            "evaluation": evaluation,
        }

    if state["dry_run"]:
        candidate_data = evaluation_agent.read_json(candidate_file)
        ground_truth_data = evaluation_agent.read_json(ground_truth_file)
        all_fields = sorted(set(candidate_data) | set(ground_truth_data))
        classifications = {
            field: "TP" if str(candidate_data.get(field, "Null")) == str(ground_truth_data.get(field, "Null")) else "FP_mismatch"
            for field in all_fields
        }
        summary = evaluation_agent.calculate_metrics(classifications)
        evaluation = {
            "doi_folder": state["doi_folder"],
            "model_file": str(candidate_file),
            "ground_truth_file": str(ground_truth_file),
            "judge_model": f"dry-run:{state['judge_model']}",
            "field_evaluations": {
                field: {
                    "candidate_value": str(candidate_data.get(field, "Null")),
                    "reference_value": str(ground_truth_data.get(field, "Null")),
                    "classification": classifications[field],
                }
                for field in all_fields
            },
            "summary": summary,
        }
        save_json(evaluation, output_file)
        logger.info("Dry-run evaluation wrote placeholder report: %s", output_file)
        return {
            **state,
            "evaluation_file": str(output_file),
            "evaluation": evaluation,
        }

    judge_agent = build_evaluation_agent(state["judge_model"])
    evaluation = evaluation_agent.evaluate_single_file(
        model_file_path=candidate_file,
        ground_truth_file_path=ground_truth_file,
        agent=judge_agent,
        judge_model_name=state["judge_model"],
    )
    save_json(evaluation, output_file)
    logger.info("Evaluation saved report: %s", output_file)
    return {
        **state,
        "evaluation_file": str(output_file),
        "evaluation": evaluation,
    }


def summarize(state: PipelineState) -> PipelineState:
    evaluation = state.get("evaluation", {})
    summary = {
        "doi_folder": state["doi_folder"],
        "candidate_file": state.get("candidate_file"),
        "ground_truth_file": state.get("ground_truth_file"),
        "evaluation_file": state.get("evaluation_file"),
        "skills": {
            "annotation": annotation_agent.ANNOTATION_SKILL.identity,
            "verification": evaluation_agent.VERIFICATION_SKILL.identity,
        },
        "metrics": evaluation.get("summary", {}),
    }
    return {**state, "summary": summary}


def build_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("resolve_inputs", resolve_inputs)
    graph.add_node("extract_annotation", extract_annotation)
    graph.add_node("evaluate_annotation", evaluate_annotation)
    graph.add_node("summarize", summarize)

    graph.add_edge(START, "resolve_inputs")
    graph.add_edge("resolve_inputs", "extract_annotation")
    graph.add_edge("extract_annotation", "evaluate_annotation")
    graph.add_edge("evaluate_annotation", "summarize")
    graph.add_edge("summarize", END)
    return graph.compile()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the MavaLM PSC annotation agent and verification agent as one "
            "LangGraph pipeline over a paper package."
        )
    )
    parser.add_argument(
        "--repo-root",
        default=str(DEFAULT_REPO_ROOT),
        help="Workspace root containing KB/<doi>/*.pdf and dataset/GT/recent/<doi>/ground_truth_*.json (default: current directory).",
    )
    parser.add_argument(
        "--doi-folder",
        default="stead-demo-psc-2026",
        help="DOI folder name under KB/, dataset/annotation/recent/, and dataset/GT/recent/.",
    )
    parser.add_argument(
        "--extraction-model",
        default="gpt-5-mini",
        help="Model used by the annotation/extraction agent.",
    )
    parser.add_argument(
        "--judge-model",
        default=evaluation_agent.JUDGE_MODEL_NAME,
        help="Model used by the evaluation judge agent.",
    )
    parser.add_argument(
        "--skip-extraction",
        action="store_true",
        help="Reuse the newest existing Device_BestPCE_*.json for this DOI instead of extracting from PDFs.",
    )
    parser.add_argument(
        "--force-evaluation",
        action="store_true",
        help="Re-run evaluation even if the expected evaluation JSON already exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the graph and write placeholder outputs without calling LLMs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    require_openai_key(args.dry_run)

    pipeline = build_graph()
    final_state = pipeline.invoke(
        {
            "repo_root": args.repo_root,
            "doi_folder": args.doi_folder,
            "extraction_model": args.extraction_model,
            "judge_model": args.judge_model,
            "skip_extraction": args.skip_extraction,
            "dry_run": args.dry_run,
            "force_evaluation": args.force_evaluation,
        }
    )

    print("\n" + "=" * 70)
    print("MAVALM PIPELINE COMPLETE")
    print("=" * 70)
    print(json.dumps(final_state["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
