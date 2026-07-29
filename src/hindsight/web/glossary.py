"""Plain-language explanations surfaced behind every info control in the console.

A visitor should never meet a term they cannot expand. Each entry is written for
someone who has not seen this project before, and avoids assuming any machine
learning background beyond "a model makes predictions".
"""

from __future__ import annotations

GLOSSARY: dict[str, dict[str, str]] = {
    "target-leakage": {
        "term": "Target leakage",
        "short": "A feature secretly contains the answer.",
        "body": (
            "Target leakage happens when a model is trained on information that would not "
            "have existed at the moment it is asked to predict. The model looks excellent "
            "in testing because it is effectively reading the answer, then fails in "
            "production where that information is not available yet. It is one of the most "
            "expensive silent failures in production machine learning."
        ),
    },
    "datahub": {
        "term": "DataHub",
        "short": "The open-source metadata graph Hindsight reads.",
        "body": (
            "DataHub catalogs the tables, columns, dashboards, pipelines and ML models "
            "across a company's data stack, and records how they connect. Hindsight uses "
            "that graph as its evidence source: without it there is no way to ask where a "
            "feature's data actually came from."
        ),
    },
    "mcp": {
        "term": "MCP Server",
        "short": "How the agent calls DataHub.",
        "body": (
            "The Model Context Protocol server exposes DataHub as tools an AI agent can "
            "call - search the catalog, read an entity, trace lineage, apply a tag. "
            "Hindsight uses the official DataHub MCP server for discovery and governed "
            "mutations, and the Python SDK where typed ML metadata is needed."
        ),
    },
    "column-lineage": {
        "term": "Column-level lineage",
        "short": "Which exact columns fed this column.",
        "body": (
            "Table-level lineage tells you table A fed table B. Column-level lineage tells "
            "you which specific column fed which specific column. Leakage is a column-level "
            "problem, so table-level lineage cannot detect it - this resolution is the "
            "reason the whole approach works."
        ),
    },
    "ml-lineage": {
        "term": "ML lineage",
        "short": "Training data to features to model to deployment.",
        "body": (
            "DataHub models ML assets as first-class entities, so the path from raw table "
            "to feature to trained model to deployment is queryable. Hindsight walks that "
            "path backwards from a candidate model version to find where each feature's "
            "information originated."
        ),
    },
    "urn": {
        "term": "URN",
        "short": "DataHub's name for one specific thing.",
        "body": (
            "Every table, column and model in the catalog gets one unique identifier, "
            "so two teams talking about 'the payments table' can be sure they mean the "
            "same one. It reads left to right: the kind of thing, then where it lives, "
            "then its name. You never have to type one - it is shown so that a finding "
            "can be traced to exactly one asset and no other."
        ),
    },
    "pipeline": {
        "term": "Pipeline",
        "short": "The code that builds one table from others.",
        "body": (
            "Data rarely arrives ready to use. A pipeline is the step that reads some "
            "tables, does something to them, and writes a new one. The defect this tool "
            "looks for is usually created inside a pipeline, long before anyone starts "
            "training a model - which is why looking only at the model misses it."
        ),
    },
    "confirmation-policy": {
        "term": "Confirmation policy",
        "short": "How much collapse counts as proof.",
        "body": (
            "Rebuilding a model without the future always lowers its score a little. "
            "The policy is the line, written down in advance, above which that drop "
            "counts as proof rather than noise. Choosing it after seeing the result "
            "would let anyone prove anything, so it is fixed first and the measured "
            "margin against it is published either way."
        ),
    },
    "prediction-cutoff": {
        "term": "Prediction cutoff",
        "short": "The moment the model must decide.",
        "body": (
            "For a credit decision, the cutoff is loan origination - everything the model "
            "is allowed to know must already exist at that instant. A source classified as "
            "post-outcome became available only after the cutoff, so using it means the "
            "model is reading the future."
        ),
    },
    "transformation-check": {
        "term": "Transformation check",
        "short": "Reading the SQL that built the feature.",
        "body": (
            "Hindsight parses the feature's SQL into a syntax tree with sqlglot and looks "
            "for a guard such as available_at <= prediction_time. If a post-outcome table "
            "is joined with no such guard, that is a deterministic proof of the violation - "
            "no model training required."
        ),
    },
    "point-in-time": {
        "term": "Point-in-time reconstruction",
        "short": "Rebuild the feature as it truly looked, then retrain.",
        "body": (
            "The feature is recomputed using only records that existed at the cutoff, and "
            "the model is retrained. A genuinely predictive feature keeps its advantage. A "
            "leaked feature collapses, because the advantage was borrowed from the future. "
            "This is the counterfactual that separates skill from hindsight."
        ),
    },
    "ablation-delta": {
        "term": "Ablation delta",
        "short": "How much accuracy drops if you remove the feature.",
        "body": (
            "Ablation measures whether a feature is useful. It says nothing about whether "
            "the information was allowed to exist yet. That is why the honest control here "
            "has a larger ablation delta than the leaked feature - a detector built on "
            "importance alone gets this case exactly backwards."
        ),
    },
    "advantage-retained": {
        "term": "Advantage retained",
        "short": "How much of the edge survives honest time.",
        "body": (
            "The share of a feature's performance advantage that remains after the feature "
            "is rebuilt point-in-time. Near 100% means the value was real. A collapse means "
            "the value depended on information from after the decision."
        ),
    },
    "safe-control": {
        "term": "Safe control",
        "short": "A strong feature that must NOT be flagged.",
        "body": (
            "A detector that flags everything is useless. The console deliberately includes "
            "a legitimate, highly predictive feature that shares ancestry with the outcome "
            "but only uses pre-cutoff data. It must come back clear every single run, and it "
            "is a permanent regression test rather than a demo prop."
        ),
    },
    "verdict-lattice": {
        "term": "Verdict lattice",
        "short": "Calibrated conclusions, never a guess.",
        "body": (
            "Verdicts run from insufficient_metadata through needs_review and "
            "high_confidence to confirmed or clear_for_release. Reaching confirmed requires "
            "either a deterministic SQL and time proof or a point-in-time collapse. An LLM "
            "may explain the evidence; it can never promote a verdict."
        ),
    },
    "approval-gate": {
        "term": "Human approval boundary",
        "short": "Nothing is written to the catalog without a person.",
        "body": (
            "Publication is a dry run by default. A human must explicitly approve before "
            "Hindsight writes anything into DataHub, and the proposed repair is never merged "
            "or applied automatically. The agent proposes; a person decides."
        ),
    },
    "writeback-types": {
        "term": "What gets written back",
        "short": "Tag, property, document and incident.",
        "body": (
            "On approval Hindsight writes a field tag on the offending column, a structured "
            "verdict property, a linked audit Document containing the evidence path, and an "
            "active leakage incident. The next engineer or agent inherits the finding rather "
            "than rediscovering it."
        ),
    },
    "reread": {
        "term": "Re-read verification",
        "short": "Trust nothing that was not read back.",
        "body": (
            "After every write, Hindsight fetches the entity again from DataHub and confirms "
            "the change actually persisted. A write that reports success but cannot be read "
            "back is treated as a failure."
        ),
    },
    "recorded-replay": {
        "term": "Recorded replay",
        "short": "Real DataHub responses, captured and committed.",
        "body": (
            "So anyone can evaluate this without installing Docker, the metadata responses "
            "from a real DataHub Core instance were captured, hashed and committed. Replay "
            "is honest by construction - the recordings came from a live run, and "
            "verify-fixture-live re-proves them against your own instance."
        ),
    },
}


def glossary_for(keys: list[str] | None = None) -> dict[str, dict[str, str]]:
    if keys is None:
        return GLOSSARY
    return {key: GLOSSARY[key] for key in keys if key in GLOSSARY}
