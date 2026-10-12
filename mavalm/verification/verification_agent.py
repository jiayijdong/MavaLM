#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import tool, ToolRuntime
from langgraph.checkpoint.memory import InMemorySaver

try:
    from mavalm.skill_registry import verification_contract
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from mavalm.skill_registry import verification_contract


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


#JUDGE_MODEL_NAME = "gpt-4o"
JUDGE_MODEL_NAME = "gpt-5-mini"
MODEL_FILE_PATTERN = "Device_BestPCE_*.json"
GROUND_TRUTH_PATTERN = "ground_truth_*.json"
SKIP_EXISTING = True


@dataclass
class EvaluationContext:
    model_data: Dict[str, Any]
    ground_truth_data: Dict[str, Any]
    model_filename: str
    ground_truth_filename: str


@tool
def get_comparison_data(runtime: ToolRuntime[EvaluationContext]) -> str:
    """
    Retrieve field-by-field comparison data between the model extraction
    and the ground-truth reference JSON for PSC evaluation.
    """
    model_data = runtime.context.model_data
    ground_truth_data = runtime.context.ground_truth_data

    all_fields = sorted(set(model_data.keys()) | set(ground_truth_data.keys()))

    comparisons = {}
    for field_name in all_fields:
        comparisons[field_name] = {
            "candidate": str(model_data.get(field_name, "Null")),
            "reference": str(ground_truth_data.get(field_name, "Null")),
        }

    return json.dumps(comparisons, indent=2, ensure_ascii=False)


JUDGE_SYSTEM_PROMPT = """You are a meticulous data evaluator for perovskite solar cell (PSC) research data extraction. Your task is to compare candidate values (from model extraction) with reference values (ground truth) for multiple fields and classify each according to your domain knowledge.

## Classification Rules:
- TN (True Negative): Both values are null/empty (including "Null", "nan", "Unknown", empty string)
- FP (False Positive): Reference is null/empty but candidate has a value
- FN (False Negative): Reference has a value but candidate is null/empty
- TP (True Positive): Both have values and they are equivalent
- FP_mismatch: Both have values but they are NOT equivalent

## Equivalence Guidelines:

### General Rules:
- Journal abbreviations equal full names (e.g., "Adv. Funct. Mater." = "Advanced Functional Materials")
- Ignore case differences (e.g., "NIP" = "nip")
- Same value in different notation is equivalent (e.g., "MAPbI3" = "CH3NH3PbI3")
- Similar descriptions are equivalent (e.g., "Thermal evaporation" = "Evaporation")
- Ignore unit format differences if values match (e.g., "100 nm" = "100.0")
- Ignore upper/lower case if clearly the same material (e.g., "Spiro-OMeTAD" = "Spiro-MeOTAD")

### Boolean Equivalence:
- "False" = "1" = "1.0", "True" = "2" = "2.0" (for "Perovskite_deposition_sequential_spin_coating")

### Chemical Notation:
- Common chemical notation variations are equivalent (e.g., hyphens, capitalization in chemical names)
- Perovskite long form could contain x, y, z, etc unknown variables

### Ratio Comparison:
- 4:1 and 4;1 and 1:4 and 1;4 are equal in ratio comparison

### Atmosphere:
- Glovebox = N2 = Nitrogen

### Unit Conversion:
- JV_measured_scan_speed: 0.03 V/s = 30 mV/s = 30
- Stability_PCE_after_time: 720 hours = 30 d = 1 month
- Light intensity: 1 sun = 100 mW/cm^2 = 100

### Comparison Symbols:
- Ignore comparison symbols: >1000 hours = 1000 hours; <10^-6 torr = 10^-6 torr; <90% = <=90% = 90%

### PCE and FF:
- Ignore '%' when comparing PCE and FF: 16.2% = 16.2; 80% = 80 = 0.8

### Light Spectra:
- 1 sun = AM1.5G = 100 mW/cm2

### Floating Range:
- 50±5% = 50%; 50±5°C = 50°C; 20-25°C = 25°C

### Layer Descriptions:
- Description of each layer in thickness, atmosphere, pressure, etc is allowed
- e.g., NiOx:Null/PTAA:Null = Null/Null

### Missing Items in Multiple Layers/Steps:
- Air = Air/Null/Null
- 3000 rpm = 3000 rpm/Null/Null
- Spin-coating = Spin-coating/Null
- BUT: Spin-coating ≠ Spin-coating/Spin-coating
- 1 mg/mL ≠ 30mg/mL/1mg/mL/0.5wt%
- 6000rpm ≠ 5000rpm/6000rpm
- N2 ≠ N2/Air/Air

### Cell Stack Sequence Special Rules:
- Ignore substrate layer (SLG) if only present in one sequence
- Metal oxide equivalences: TiOx = TiO2 = TiO2-c = TiO2-mp; NiOx = NiO = NiO2
- If multiple layers of same material are merged into one, consider equivalent
- Perovskite layer names are equivalent: "Perovskite" = "CH3NH3PbI3" = "MAPbI3"
- Ignore separator differences (/, |, >>, etc.)

### Atmosphere Pressure Special Rules:
- If Reference is 'Null' or '1 atm' or 'Null or 1 atm' and candidate value is 'Null' or '1 atm', classify as TN
- The pressure of both Air and Nitrogen atmosphere is considered as 1 atm by default

### Concentration Special Rules:
- As long as concentration is specified, expanded notation equals abbreviated form
- e.g., "17uL of 520 mg/mL Li-TFSI per ml, 28.5 uL 4-tert-butylpyridine per mL" = "520 mg/mL; Null"

## Instructions:
1. Use the get_comparison_data tool to retrieve the field-by-field comparison data
2. Evaluate each field according to the classification rules above
3. Return ONLY a valid JSON object with field names as keys and classification (TN, FP, FN, TP, or FP_mismatch) as values
4. Do not include any explanation or additional text
"""

# Load the exact, SemVer-pinned verification policy used by the harness.
VERIFICATION_SKILL, JUDGE_SYSTEM_PROMPT = verification_contract()


def find_repo_root(start_path: Path) -> Path:
    current = start_path.resolve()
    if current.is_file():
        current = current.parent

    for path in [current, *current.parents]:
        if (path / "dataset").exists():
            return path

    raise FileNotFoundError(
        "Could not find MavaLM repo root. Run inside MavaLM or pass --repo-root /path/to/MavaLM."
    )


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"JSON root is not an object: {path}")

    return data


def parse_json_response(response_text: str) -> Optional[Dict[str, str]]:
    if not response_text:
        return None

    text = response_text.strip()

    if text.startswith("```json"):
        text = text.removeprefix("```json").strip()
    elif text.startswith("```"):
        text = text.removeprefix("```").strip()

    if text.endswith("```"):
        text = text.removesuffix("```").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", response_text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None

    return None


def calculate_metrics(classifications: Dict[str, str]) -> Dict[str, Any]:
    tp_count = sum(1 for c in classifications.values() if c == "TP")
    tn_count = sum(1 for c in classifications.values() if c == "TN")
    fp_count = sum(1 for c in classifications.values() if c == "FP")
    fn_count = sum(1 for c in classifications.values() if c == "FN")
    fp_mismatch_count = sum(1 for c in classifications.values() if c == "FP_mismatch")
    error_count = sum(1 for c in classifications.values() if c == "ERROR")

    total_fields = len(classifications)
    valid_fields = total_fields - error_count

    if valid_fields > 0:
        accuracy = (tp_count + tn_count) / valid_fields
        precision = (
            tp_count / (tp_count + fp_count + fp_mismatch_count)
            if (tp_count + fp_count + fp_mismatch_count) > 0
            else 0
        )
        recall = (
            tp_count / (tp_count + fn_count)
            if (tp_count + fn_count) > 0
            else 0
        )
        f1_score = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0
        )
    else:
        accuracy = precision = recall = f1_score = 0

    return {
        "total_fields_compared": total_fields,
        "valid_fields": valid_fields,
        "true_positives": tp_count,
        "true_negatives": tn_count,
        "false_positives": fp_count,
        "false_negatives": fn_count,
        "false_positive_mismatches": fp_mismatch_count,
        "errors": error_count,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1_score": round(f1_score, 3),
        "accuracy": round(accuracy, 3),
    }


def safe_name(text: str) -> str:
    return text.replace("-", "_").replace(".", "_").replace("/", "_")


def get_output_filename(model_file: Path, judge_model: str) -> str:
    return f"Evaluation_{model_file.stem}_by_{safe_name(judge_model)}.json"


def evaluate_single_file(
    model_file_path: Path,
    ground_truth_file_path: Path,
    agent,
    judge_model_name: str,
) -> Dict[str, Any]:
    model_data = read_json(model_file_path)
    ground_truth_data = read_json(ground_truth_file_path)

    context = EvaluationContext(
        model_data=model_data,
        ground_truth_data=ground_truth_data,
        model_filename=model_file_path.name,
        ground_truth_filename=ground_truth_file_path.name,
    )

    config = {
        "configurable": {
            "thread_id": f"eval-{model_file_path.parent.name}-{model_file_path.stem}"
        }
    }

    user_message = (
        "Evaluate the model extraction results against ground truth. "
        "Use get_comparison_data to retrieve the field-by-field comparison. "
        "Classify each field according to the rules. "
        "Return only a valid JSON object with classifications."
    )

    start_time = time.time()

    response = agent.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        config=config,
        context=context,
    )

    time_taken = time.time() - start_time

    messages = response.get("messages", [])
    if not messages:
        raise RuntimeError(f"No messages returned by agent for {model_file_path}")

    last_message = messages[-1]
    response_text = last_message.content if hasattr(last_message, "content") else str(last_message)

    classifications = parse_json_response(response_text)

    all_fields = sorted(set(model_data.keys()) | set(ground_truth_data.keys()))
    valid_values = {"TN", "FP", "FN", "TP", "FP_mismatch"}

    if not classifications:
        classifications = {field: "ERROR" for field in all_fields}

    for field in all_fields:
        if field not in classifications:
            classifications[field] = "FP_mismatch"
        elif classifications[field] not in valid_values:
            classifications[field] = "FP_mismatch"

    field_evaluations = {}
    for field in all_fields:
        field_evaluations[field] = {
            "candidate_value": str(model_data.get(field, "Null")),
            "reference_value": str(ground_truth_data.get(field, "Null")),
            "classification": classifications[field],
        }

    summary = calculate_metrics(classifications)

    return {
        "doi_folder": model_file_path.parent.name,
        "model_file": str(model_file_path),
        "ground_truth_file": str(ground_truth_file_path),
        "processing_timestamp": datetime.now().isoformat(),
        "judge_model": judge_model_name,
        "verification_skill": VERIFICATION_SKILL.identity,
        "timing": {
            "evaluation_time_seconds": round(time_taken, 2),
            "evaluation_time_formatted": f"{int(time_taken // 60)}m {int(time_taken % 60)}s",
        },
        "field_evaluations": field_evaluations,
        "summary": summary,
    }


def main() -> None:
    args = parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Run:\n"
            'export OPENAI_API_KEY="your_api_key"'
        )

    repo_root = Path(args.repo_root).expanduser().resolve() if args.repo_root else find_repo_root(Path.cwd())

    annotation_recent_dir = repo_root / "dataset" / "annotation" / "recent"
    gt_recent_dir = repo_root / "dataset" / "GT" / "recent"
    evaluation_recent_dir = repo_root / "dataset" / "evaluation" / "recent"

    if not annotation_recent_dir.exists():
        raise FileNotFoundError(f"Annotation folder not found: {annotation_recent_dir}")

    if not gt_recent_dir.exists():
        raise FileNotFoundError(f"GT folder not found: {gt_recent_dir}")

    evaluation_recent_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Annotation folder: %s", annotation_recent_dir)
    logger.info("GT folder: %s", gt_recent_dir)
    logger.info("Evaluation output folder: %s", evaluation_recent_dir)
    logger.info("Judge model: %s", args.judge_model)

    model = init_chat_model(args.judge_model, temperature=0)
    checkpointer = InMemorySaver()

    agent = create_agent(
        model=model,
        system_prompt=JUDGE_SYSTEM_PROMPT,
        tools=[get_comparison_data],
        context_schema=EvaluationContext,
        checkpointer=checkpointer,
    )

    doi_folders = sorted([p for p in annotation_recent_dir.iterdir() if p.is_dir()])

    total_files = 0
    successful = 0
    failed = 0
    skipped = 0
    results = []

    for annotation_doi_folder in doi_folders:
        doi_folder_name = annotation_doi_folder.name
        gt_doi_folder = gt_recent_dir / doi_folder_name
        output_doi_folder = evaluation_recent_dir / doi_folder_name
        output_doi_folder.mkdir(parents=True, exist_ok=True)

        if not gt_doi_folder.exists():
            logger.warning("Skipping %s: matching GT folder not found", doi_folder_name)
            skipped += 1
            continue

        ground_truth_files = sorted(gt_doi_folder.glob(GROUND_TRUTH_PATTERN))
        if not ground_truth_files:
            logger.warning("Skipping %s: no ground_truth_*.json found", doi_folder_name)
            skipped += 1
            continue

        ground_truth_file = ground_truth_files[0]
        model_files = sorted(annotation_doi_folder.glob(MODEL_FILE_PATTERN))

        if not model_files:
            logger.warning("Skipping %s: no Device_BestPCE_*.json found", doi_folder_name)
            skipped += 1
            continue

        for model_file in model_files:
            total_files += 1
            output_file = output_doi_folder / get_output_filename(model_file, args.judge_model)

            if args.skip_existing and output_file.exists():
                logger.info("Skipping existing evaluation: %s", output_file)
                skipped += 1
                continue

            logger.info("Evaluating %s against %s", model_file, ground_truth_file)

            try:
                result = evaluate_single_file(
                    model_file_path=model_file,
                    ground_truth_file_path=ground_truth_file,
                    agent=agent,
                    judge_model_name=args.judge_model,
                )

                with output_file.open("w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)

                successful += 1
                results.append(
                    {
                        "doi_folder": doi_folder_name,
                        "model_file": model_file.name,
                        "accuracy": result["summary"]["accuracy"],
                        "precision": result["summary"]["precision"],
                        "recall": result["summary"]["recall"],
                        "f1_score": result["summary"]["f1_score"],
                    }
                )

                logger.info(
                    "Saved %s | Accuracy %.3f | F1 %.3f",
                    output_file,
                    result["summary"]["accuracy"],
                    result["summary"]["f1_score"],
                )

            except Exception as e:
                failed += 1
                logger.error("Failed evaluating %s: %s", model_file, e)

    summary_file = evaluation_recent_dir / f"Summary_Evaluation_by_{safe_name(args.judge_model)}.json"

    summary = {
        "processing_timestamp": datetime.now().isoformat(),
        "judge_model": args.judge_model,
        "annotation_recent_dir": str(annotation_recent_dir),
        "gt_recent_dir": str(gt_recent_dir),
        "evaluation_recent_dir": str(evaluation_recent_dir),
        "total_files": total_files,
        "successful": successful,
        "failed": failed,
        "skipped": skipped,
        "results": results,
    }

    if results:
        summary["average_accuracy"] = round(sum(r["accuracy"] for r in results) / len(results), 3)
        summary["average_f1_score"] = round(sum(r["f1_score"] for r in results) / len(results), 3)

    with summary_file.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print("EVALUATION COMPLETE")
    print("=" * 70)
    print(f"Judge model: {args.judge_model}")
    print(f"Total model files: {total_files}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped}")
    print(f"Summary file: {summary_file}")
    if results:
        print(f"Average Accuracy: {summary['average_accuracy']:.3f}")
        print(f"Average F1 Score: {summary['average_f1_score']:.3f}")
    print("=" * 70)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate MavaLM/dataset/annotation/recent against MavaLM/dataset/GT/recent."
    )

    parser.add_argument(
        "--repo-root",
        type=str,
        default=None,
        help="Path to MavaLM repo root. Default: search upward from current directory.",
    )

    parser.add_argument(
        "--judge-model",
        type=str,
        default=JUDGE_MODEL_NAME,
        help="Judge model name. Default: gpt-4o.",
    )

    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=SKIP_EXISTING,
        help="Skip evaluation files that already exist.",
    )

    parser.add_argument(
        "--no-skip-existing",
        action="store_false",
        dest="skip_existing",
        help="Re-evaluate even if evaluation files already exist.",
    )

    return parser.parse_args()


if __name__ == "__main__":
    main()
