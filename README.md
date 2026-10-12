# MavaLM

Harness and Skills for *MavaLM: In Search of a Verifiable Automated Database
Harness for AI Scientists*.

```
mavalm/        Skill registry, annotation agent, verification agent, LangGraph pipeline, field-level metrics
skills/        psc-annotate-v1 (97-field PSC schema + field guide), psc-verify-v1 (equivalence rules);
               registry.json pins versions, archive/ keeps the paper's psc-verify-v1@1.1.0
scripts/       validate_repository.py
tests/         unit tests
```

## Setup

```bash
python -m pip install -e .            # Python >= 3.11; add '.[agents]' for live model calls
make check
```

## Run

A workspace holds `KB/<doi>/*.pdf` (article + supplement) and
`dataset/GT/recent/<doi>/ground_truth_<doi>.json` (97-field reference record).

```bash
export OPENAI_API_KEY=...
python -m mavalm.pipeline.psc_pipeline --repo-root /path/to/workspace --doi-folder <doi> \
       --extraction-model gpt-5-mini --judge-model o3
# --dry-run runs the graph without model calls
```

Outputs: `dataset/annotation/recent/<doi>/Device_BestPCE_*.json` (candidate record)
and `dataset/evaluation/recent/<doi>/Evaluation_*.json` (field-level TP/TN/FP/FN/FP_mismatch
decisions with the Skill versions used). `mavalm.metrics` scores such audits
(accuracy, precision, recall, F1, per-subfield).

## License

MIT.
