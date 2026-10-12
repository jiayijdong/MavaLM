#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import tool, ToolRuntime
from langgraph.checkpoint.memory import InMemorySaver
from pypdf import PdfReader
from pypdf.errors import DependencyError

try:
    from mavalm.skill_registry import annotation_contract
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from mavalm.skill_registry import annotation_contract


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


PSC_TEMPLATE: Dict[str, str] = {
    "Ref_DOI": "",
    "Ref_journal": "",
    "Ref_publication_year": "",
    "Ref_title": "",
    "Cell_architecture": "",
    "Cell_stack_sequence": "",
    "Cell_area_measured": "",
    "ETL_thickness": "",
    "ETL_stack_sequence": "",
    "ETL_additive_compound": "",
    "ETL_additive_concentration": "",
    "ETL_deposition_method": "",
    "ETL_deposition_solution_concentration": "",
    "ETL_deposition_solvents_compound": "",
    "ETL_deposition_synthesis_atmosphere": "",
    "ETL_deposition_synthesis_atmosphere_pressure": "",
    "ETL_deposition_synthesis_atmosphere_relative_humidity": "",
    "ETL_deposition_spin_coating_speed": "",
    "ETL_deposition_spin_coating_time": "",
    "ETL_deposition_thermal_annealing_temperature": "",
    "ETL_deposition_thermal_annealing_time": "",
    "Perovskite_dimension": "",
    "Perovskite_thickness": "",
    "Perovskite_composition_long_form": "",
    "Perovskite_additive_compound": "",
    "Perovskite_additive_concentration": "",
    "Perovskite_bandgap": "",
    "Perovskite_deposition_method": "",
    "Perovskite_deposition_sequential_spin_coating": "",
    "Perovskite_deposition_spin_coating_antisolvent": "",
    "Perovskite_deposition_reaction_solutions_compounds": "",
    "Perovskite_deposition_reaction_solutions_concentrations": "",
    "Perovskite_deposition_final_solutions_concentration_before_deposition": "",
    "Perovskite_deposition_solvents_compound": "",
    "Perovskite_deposition_solvents_mixing_ratio": "",
    "Perovskite_deposition_synthesis_atmosphere": "",
    "Perovskite_deposition_synthesis_atmosphere_pressure": "",
    "Perovskite_deposition_synthesis_atmosphere_relative_humidity": "",
    "Perovskite_deposition_spin_coating_speed": "",
    "Perovskite_deposition_spin_coating_time": "",
    "Perovskite_deposition_thermal_annealing_atmosphere": "",
    "Perovskite_deposition_thermal_annealing_temperature": "",
    "Perovskite_deposition_thermal_annealing_time": "",
    "Perovskite_surface_treatment_material": "",
    "Perovskite_surface_treatment_method": "",
    "Perovskite_surface_treatment_solution_concentration": "",
    "Perovskite_surface_treatment_solvents_compound": "",
    "Perovskite_surface_treatment_synthesis_atmosphere": "",
    "Perovskite_surface_treatment_synthesis_atmosphere_pressure": "",
    "Perovskite_surface_treatment_synthesis_atmosphere_relative_humidity": "",
    "Perovskite_surface_treatment_deposition_spin_coating_speed": "",
    "Perovskite_surface_treatment_deposition_spin_coating_time": "",
    "Perovskite_surface_treatment_deposition_thermal_annealing_temperature": "",
    "Perovskite_surface_treatment_deposition_thermal_annealing_time": "",
    "HTL_thickness": "",
    "HTL_stack_sequence": "",
    "HTL_additive_compound": "",
    "HTL_additive_concentration": "",
    "HTL_deposition_method": "",
    "HTL_deposition_solution_concentration": "",
    "HTL_deposition_solvents_compound": "",
    "HTL_deposition_synthesis_atmosphere": "",
    "HTL_deposition_synthesis_atmosphere_pressure": "",
    "HTL_deposition_synthesis_atmosphere_relative_humidity": "",
    "HTL_deposition_spin_coating_speed": "",
    "HTL_deposition_spin_coating_time": "",
    "HTL_deposition_thermal_annealing_temperature": "",
    "HTL_deposition_thermal_annealing_time": "",
    "Backcontact_thickness": "",
    "Backcontact_deposition_method": "",
    "Backcontact_deposition_atmosphere_pressure": "",
    "Encapsulation_method": "",
    "Encapsulation_atmosphere": "",
    "JV_measured_device_matching": "",
    "JV_measured_reverse_scan_Voc": "",
    "JV_measured_reverse_scan_Jsc": "",
    "JV_measured_reverse_scan_FF": "",
    "JV_measured_reverse_scan_PCE": "",
    "JV_measured_forward_scan_Voc": "",
    "JV_measured_forward_scan_Jsc": "",
    "JV_measured_forward_scan_FF": "",
    "JV_measured_forward_scan_PCE": "",
    "JV_measured_light_spectra": "",
    "JV_measured_light_spectra_intensity": "",
    "JV_measured_scan_speed": "",
    "JV_measured_scan_delay_time": "",
    "JV_certified_PCE": "",
    "Stabilized_measured_PCE": "",
    "Stabilized_certified_PCE": "",
    "Stability_test_device_matching": "",
    "Stability_test_temperature": "",
    "Stability_test_atmosphere": "",
    "Stability_test_light_spectra": "",
    "Stability_test_light_intensity": "",
    "Stability_test_relative_humidity": "",
    "Stability_PCE_after_time": "",
    "Stability_PCE_after_time_value": "",
}


@dataclass
class ExtractionContext:
    folder_path: str
    combined_text: str


def find_mavalm_repo_root(start_path: Path) -> Path:
    """
    Find MavaLM repo root by walking upward until a folder containing KB/ is found.
    This allows running the script from MavaLM/, MavaLM/MAS/annotation/, etc.
    """
    current = start_path.resolve()

    if current.is_file():
        current = current.parent

    for path in [current, *current.parents]:
        if (path / "KB").exists() and (path / "KB").is_dir():
            return path

    raise FileNotFoundError(
        "Could not find MavaLM repo root. "
        "Please run inside the MavaLM repo or pass --repo-root /path/to/MavaLM"
    )


def clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_text_from_pdf(pdf_path: Path) -> str:
    try:
        reader = PdfReader(str(pdf_path))
    except (DependencyError, Exception) as e:
        logger.warning("Failed to open PDF %s: %s", pdf_path, e)
        return ""

    if reader.is_encrypted:
        try:
            decrypt_result = reader.decrypt("")
            if decrypt_result == 0:
                logger.warning("Encrypted PDF cannot be decrypted: %s", pdf_path)
                return ""
        except Exception as e:
            logger.warning("Failed to decrypt PDF %s: %s", pdf_path, e)
            return ""

    chunks: List[str] = []

    for page_index, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
            if page_text.strip():
                chunks.append(page_text)
        except Exception as e:
            logger.warning("Failed to read page %d in %s: %s", page_index, pdf_path, e)

    return clean_text("\n".join(chunks))


def load_all_pdfs_from_folder(folder_path: Path) -> str:
    if not folder_path.exists():
        raise FileNotFoundError(f"PDF folder does not exist: {folder_path}")

    if not folder_path.is_dir():
        raise NotADirectoryError(f"Path is not a folder: {folder_path}")

    pdf_files = sorted(folder_path.glob("*.pdf"))

    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in: {folder_path}")

    logger.info("Found %d PDF files in %s", len(pdf_files), folder_path)

    text_parts: List[str] = []

    for pdf_file in pdf_files:
        logger.info("Reading PDF: %s", pdf_file.name)
        text = extract_text_from_pdf(pdf_file)

        if text:
            text_parts.append(f"\n\n--- Content from {pdf_file.name} ---\n{text}")
        else:
            logger.warning("No extractable text from PDF: %s", pdf_file.name)

    combined_text = clean_text("\n".join(text_parts))

    if not combined_text:
        raise ValueError(f"No extractable text found from PDFs in: {folder_path}")

    logger.info("Combined text length: %d characters", len(combined_text))

    return combined_text


@tool
def get_document_text(runtime: ToolRuntime[ExtractionContext]) -> str:
    """Return the combined text from all PDF files for PSC data extraction."""
    return runtime.context.combined_text


PSC_INSTRUCTIONS = (
    "You are an assistant designed to read perovskite solar cell literature "
    "and fill a JSON template with experimental details for dataset curation.\n\n"
    "You must extract information for the CHAMPION device, meaning the device "
    "with the highest reported power conversion efficiency in the paper.\n\n"
    "## JSON Template to Fill:\n"
    + json.dumps(PSC_TEMPLATE, indent=2)
    + """

## Field Instructions:
- Ref_DOI: Insert DOI; strictly follow the format: 10.1234/abcd.efgh
- Ref_journal: Insert journal
- Ref_publication_year: Insert year
- Ref_title: Insert title
- Cell_architecture: PIN or NIP
- Cell_stack_sequence: Each layer in the stack should be separated by a forward slash
- Cell_area_measured: Mask area or effective area, including unit cm2 or mm2

- ETL_thickness: Unit nm; multiple layers separated by /
- ETL_stack_sequence: Multiple layers separated by /
- ETL_additive_compound: Additive mixed with ETL solution
- ETL_additive_concentration: Unit mg/mL, M, mM, mol%, or wt%
- ETL_deposition_method: For example, Spin-coating; multiple layers separated by /
- ETL_deposition_solution_concentration: Unit mg/mL, M, mM, mol%, or wt%
- ETL_deposition_solvents_compound: For example, Ethanol
- ETL_deposition_synthesis_atmosphere: For example, Air
- ETL_deposition_synthesis_atmosphere_pressure: Unit atm; if air, write 1 atm
- ETL_deposition_synthesis_atmosphere_relative_humidity: Unit %
- ETL_deposition_spin_coating_speed: Unit rpm
- ETL_deposition_spin_coating_time: Unit s
- ETL_deposition_thermal_annealing_temperature: Unit C
- ETL_deposition_thermal_annealing_time: Unit min

- Perovskite_dimension: 3D, 2D, 1D, 0D, or 3D/2D
- Perovskite_thickness: Unit nm
- Perovskite_composition_long_form: Use long-form composition, e.g. FAPbI3
- Perovskite_additive_compound: Additive mixed into perovskite precursor
- Perovskite_additive_concentration: Unit mg/mL, M, mM, mol%, or wt%; multiple additives separated by ;
- Perovskite_bandgap: Unit eV
- Perovskite_deposition_method: For example, Spin-coating
- Perovskite_deposition_sequential_spin_coating: True for sequential deposition; False if all mixed before deposition
- Perovskite_deposition_spin_coating_antisolvent: For example, Chlorobenzene; if sequential deposition, write Null
- Perovskite_deposition_reaction_solutions_compounds: Each solution separated by ;
- Perovskite_deposition_reaction_solutions_concentrations: Each concentration separated by ;
- Perovskite_deposition_final_solutions_concentration_before_deposition: Unit mg/mL
- Perovskite_deposition_solvents_compound: Each solvent separated by ;
- Perovskite_deposition_solvents_mixing_ratio: Each solvent ratio separated by ;
- Perovskite_deposition_synthesis_atmosphere: For example, Nitrogen
- Perovskite_deposition_synthesis_atmosphere_pressure: Unit atm; if air, write 1 atm
- Perovskite_deposition_synthesis_atmosphere_relative_humidity: Unit %
- Perovskite_deposition_spin_coating_speed: Unit rpm; multiple steps separated by ;
- Perovskite_deposition_spin_coating_time: Unit s; multiple steps separated by ;
- Perovskite_deposition_thermal_annealing_atmosphere: For example, Air
- Perovskite_deposition_thermal_annealing_temperature: Unit C; multiple steps separated by ;
- Perovskite_deposition_thermal_annealing_time: Unit min; multiple steps separated by ;

- Perovskite_surface_treatment_material: Material deposited after perovskite layer is formed
- Perovskite_surface_treatment_method: For example, Spin-coating
- Perovskite_surface_treatment_solution_concentration: Unit mg/mL
- Perovskite_surface_treatment_solvents_compound: For example, IPA
- Perovskite_surface_treatment_synthesis_atmosphere: For example, Air
- Perovskite_surface_treatment_synthesis_atmosphere_pressure: Unit atm; if air, write 1 atm
- Perovskite_surface_treatment_synthesis_atmosphere_relative_humidity: Unit %
- Perovskite_surface_treatment_deposition_spin_coating_speed: Unit rpm
- Perovskite_surface_treatment_deposition_spin_coating_time: Unit s
- Perovskite_surface_treatment_deposition_thermal_annealing_temperature: Unit C
- Perovskite_surface_treatment_deposition_thermal_annealing_time: Unit min

- HTL_thickness: Unit nm; multiple layers separated by /
- HTL_stack_sequence: Multiple layers separated by /
- HTL_additive_compound: Additive mixed with HTL solution, e.g. Li-TFSI, tBP
- HTL_additive_concentration: Unit mg/mL, M, mM, mol%, or wt%
- HTL_deposition_method: For example, Spin-coating
- HTL_deposition_solution_concentration: Unit mg/mL
- HTL_deposition_solvents_compound: For example, Chlorobenzene
- HTL_deposition_synthesis_atmosphere: For example, Air
- HTL_deposition_synthesis_atmosphere_pressure: Unit atm; if air, write 1 atm
- HTL_deposition_synthesis_atmosphere_relative_humidity: Unit %
- HTL_deposition_spin_coating_speed: Unit rpm
- HTL_deposition_spin_coating_time: Unit s
- HTL_deposition_thermal_annealing_temperature: Unit C
- HTL_deposition_thermal_annealing_time: Unit min

- Backcontact_thickness: Unit nm
- Backcontact_deposition_method: For example, Thermal evaporation
- Backcontact_deposition_atmosphere_pressure: Unit torr or atm
- Encapsulation_method: For example, UV adhesive
- Encapsulation_atmosphere: For example, Air

- JV_measured_device_matching: True if JV data comes from the best-PCE single-junction PSC
- JV_measured_reverse_scan_Voc: Unit V
- JV_measured_reverse_scan_Jsc: Unit mA/cm2
- JV_measured_reverse_scan_FF: Unit %
- JV_measured_reverse_scan_PCE: Unit %
- JV_measured_forward_scan_Voc: Unit V
- JV_measured_forward_scan_Jsc: Unit mA/cm2
- JV_measured_forward_scan_FF: Unit %
- JV_measured_forward_scan_PCE: Unit %
- JV_measured_light_spectra: For example, AM1.5G
- JV_measured_light_spectra_intensity: Unit mW/cm2, 1 sun, or 0.5 sun
- JV_measured_scan_speed: Unit V/s
- JV_measured_scan_delay_time: Unit ms
- JV_certified_PCE: Unit %; only if certified
- Stabilized_measured_PCE: Unit %; only if stabilized PCE tested
- Stabilized_certified_PCE: Unit %; only if certified stabilized PCE

- Stability_test_device_matching: True if the best-PCE device is used for stability test
- Stability_test_temperature: Unit C
- Stability_test_atmosphere: For example, Air
- Stability_test_light_spectra: For example, AM1.5G
- Stability_test_light_intensity: Unit mW/cm2, 1 sun, or 0.5 sun
- Stability_test_relative_humidity: Unit %
- Stability_PCE_after_time: For example, 1000 hours
- Stability_PCE_after_time_value: Unit %. Both percentage of initial PCE or PCE value after time are acceptable

## Rules:
1. Return valid JSON only. Do not add explanations.
2. Use the provided JSON keys exactly.
3. Fill in "Null" if information is missing or not reported.
4. Focus strictly on the device with the highest reported PCE.
5. If multiple stability tests exist for the best-PCE device, report only one representative test.
6. Use units from the original text when available.
7. Do not hallucinate values.
8. Use get_document_text to retrieve the combined full text from all PDFs.
"""
)

# The versioned Skill is the runtime source of truth. The legacy constants above
# remain readable for historical comparison, but are replaced before invocation.
ANNOTATION_SKILL, PSC_TEMPLATE, PSC_INSTRUCTIONS = annotation_contract()


def parse_json_response(response_text: str) -> Optional[Dict[str, Any]]:
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
            return json.loads(match.group(0))
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON from matched object: %s", e)

    logger.error("Failed to parse JSON response.")
    return None


def normalize_result_keys(result: Dict[str, Any]) -> Dict[str, Any]:
    normalized = {}

    for key in PSC_TEMPLATE:
        value = result.get(key, "Null")
        if value is None or value == "":
            value = "Null"
        normalized[key] = value

    return normalized


def run_extraction_agent(
    model_name: str,
    folder_path: Path,
    combined_text: str,
) -> Dict[str, Any]:
    logger.info("Initializing model: %s", model_name)

    model = init_chat_model(
        model_name,
        temperature=0,
    )

    checkpointer = InMemorySaver()

    agent = create_agent(
        model=model,
        system_prompt=PSC_INSTRUCTIONS,
        tools=[get_document_text],
        context_schema=ExtractionContext,
        checkpointer=checkpointer,
    )

    context = ExtractionContext(
        folder_path=str(folder_path),
        combined_text=combined_text,
    )

    user_message = (
        "Extract perovskite solar cell data from the document. "
        "Use get_document_text to retrieve the combined text from all PDFs. "
        "Fill all fields for the device with the highest reported power conversion efficiency. "
        "Return only the completed JSON object."
    )

    config = {
        "configurable": {
            "thread_id": f"extraction-{folder_path.name}",
        }
    }

    logger.info("Running extraction agent...")

    response = agent.invoke(
        {"messages": [{"role": "user", "content": user_message}]},
        config=config,
        context=context,
    )

    messages = response.get("messages", [])

    if not messages:
        raise RuntimeError(f"No messages returned by agent. Raw response: {response}")

    last_message = messages[-1]
    response_text = last_message.content if hasattr(last_message, "content") else str(last_message)

    parsed = parse_json_response(response_text)

    if parsed is None:
        raise ValueError(f"Could not parse agent response as JSON:\n{response_text}")

    return normalize_result_keys(parsed)


def safe_filename_part(text: str) -> str:
    text = text.strip()
    if not text:
        return "NoDOI"
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in text)


def save_result(
    result: Dict[str, Any],
    output_folder: Path,
    model_name: str,
    doi_folder: str,
) -> Path:
    output_folder.mkdir(parents=True, exist_ok=True)

    doi = str(result.get("Ref_DOI", "")).strip()
    doi_safe = safe_filename_part(doi) if doi and doi != "Null" else doi_folder
    model_safe = safe_filename_part(model_name)

    output_file = output_folder / f"Device_BestPCE_langchain_{model_safe}_{doi_safe}.json"

    with output_file.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return output_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract PSC data from PDFs in MavaLM/KB/[DOI_FOLDER]."
    )

    parser.add_argument(
        "--repo-root",
        type=str,
        default=None,
        help="Path to MavaLM repo root. If omitted, the script searches upward for a KB folder.",
    )

    parser.add_argument(
        "--doi-folder",
        type=str,
        default="stead-demo-psc-2026",
        help="DOI folder name under MavaLM/KB.",
    )

    parser.add_argument(
        "--model",
        type=str,
        #default="gpt-4o",
        default="gpt-5-mini",
        help="LangChain model name.",
    )

    parser.add_argument(
        "--output-subdir",
        type=str,
        default="generated_dataset/recent",
        help="Output subdirectory under repo root.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Run:\n"
            'export OPENAI_API_KEY="your_api_key"'
        )

    if args.repo_root:
        repo_root = Path(args.repo_root).expanduser().resolve()
    else:
        repo_root = find_mavalm_repo_root(Path.cwd())

    doi_folder = args.doi_folder

    pdf_folder = repo_root / "KB" / doi_folder
    output_folder = (
    repo_root
    / "dataset"
    / "annotation"
    / "recent"
    / doi_folder
)

    print("\n" + "=" * 70)
    print("MavaLM Single-Paper Extraction Agent")
    print("=" * 70)
    print(f"Repo root:     {repo_root}")
    print(f"PDF folder:    {pdf_folder}")
    print(f"Output folder: {output_folder}")
    print(f"Model:         {args.model}")
    print("=" * 70)

    combined_text = load_all_pdfs_from_folder(pdf_folder)

    result = run_extraction_agent(
        model_name=args.model,
        folder_path=pdf_folder,
        combined_text=combined_text,
    )

    output_file = save_result(
        result=result,
        output_folder=output_folder,
        model_name=args.model,
        doi_folder=doi_folder,
    )

    logger.info("Saved extraction result to: %s", output_file)

    print("\n" + "=" * 70)
    print("EXTRACTION COMPLETE")
    print("=" * 70)
    print(f"Output file: {output_file}")
    print("=" * 70)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
