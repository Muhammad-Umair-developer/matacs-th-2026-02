"""
Reference Prototype: Dynamic, Criteria-Agnostic Triage Engine (MATACS-TH-2026-02)
Consumes the exact JSON schema defined in PROMPTS.md Section 3.
Demonstrates how admin criteria are loaded dynamically at runtime (never hard-coded
in logic) while keeping math, gatekeeping, and ranking strictly deterministic.
"""

import json
from typing import Dict, Any, List


def evaluate_and_rank(
    extractions: List[Dict[str, Any]],
    admin_config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    100% Category-Agnostic Scoring Engine.
    Processes LLM JSON outputs matching the enforced dynamic schema in PROMPTS.md.
    """
    ranked_pool = []
    non_ranked_pool = []

    # Load dynamic criteria IDs and weights from Admin DB config
    weights_map: Dict[str, float] = {
        c["criterion_id"]: c["weight"] for c in admin_config["weighted_criteria"]
    }
    required_mandatory_ids: List[str] = [
        c["criterion_id"] for c in admin_config["mandatory_criteria"]
    ]
    max_price = admin_config["project_constraints"]["max_price"]
    max_timeline = admin_config["project_constraints"]["max_timeline"]

    for item in extractions:
        pid = item["proposal_id"]

        # 1. Security Gate (Prompt Injection Check)
        if item["security_flag"]["prompt_injection_detected"]:
            non_ranked_pool.append({
                "proposal": pid,
                "rank": None,
                "status": "flagged",
                "score": None,
                "reason": item["summary_reason"]
            })
            continue

        # 2. Dynamic Mandatory Pass/Fail Gate Loop
        mandatory_lookup = {
            m["criterion_id"]: m for m in item["mandatory_criteria_results"]
        }
        rejection_reason = None
        for req_id in required_mandatory_ids:
            res = mandatory_lookup.get(req_id)
            if not res or not res.get("passed", False):
                rejection_reason = (
                    res.get("rejection_reason")
                    if res and res.get("rejection_reason")
                    else f"Fails mandatory criterion: {req_id}"
                )
                break

        if rejection_reason:
            non_ranked_pool.append({
                "proposal": pid,
                "rank": None,
                "status": "ineligible",
                "score": None,
                "reason": rejection_reason
            })
            continue

        # 3. Project Constraint Ceiling Check (Budget & Firm Timeline)
        constraints = item["project_constraints_extracted"]
        if (
            not constraints["is_firm_timeline"]
            or constraints["completion_timeline"] is None
            or constraints["completion_timeline"] > max_timeline
        ):
            non_ranked_pool.append({
                "proposal": pid,
                "rank": None,
                "status": "ineligible",
                "score": None,
                "reason": item["summary_reason"]
            })
            continue

        if (
            constraints["total_price"] is None
            or constraints["total_price"] > max_price
        ):
            non_ranked_pool.append({
                "proposal": pid,
                "rank": None,
                "status": "ineligible",
                "score": None,
                "reason": item["summary_reason"]
            })
            continue

        # 4. Dynamic Weighted Score Summation
        subscore_lookup = {
            w["criterion_id"]: w["normalized_subscore_0_to_1"]
            for w in item["weighted_criteria_extractions"]
        }
        total_score = 0.0
        for crit_id, weight in weights_map.items():
            total_score += subscore_lookup.get(crit_id, 0.0) * weight

        ranked_pool.append({
            "proposal": pid,
            "rank": 0,
            "status": "ranked",
            "score": round(total_score),
            "reason": item["summary_reason"]
        })

    # Deterministically sort eligible proposals by score descending
    ranked_pool.sort(key=lambda x: x["score"], reverse=True)
    for idx, entry in enumerate(ranked_pool, start=1):
        entry["rank"] = idx

    return ranked_pool + non_ranked_pool


if __name__ == "__main__":
    # Runtime Admin Configuration (Loaded from DB, never hardcoded inside evaluate_and_rank)
    ADMIN_DB_CONFIG = {
        "category_id": "cat_commercial_solar_v1",
        "project_constraints": {
            "max_price": 260000,
            "max_timeline": 16
        },
        "mandatory_criteria": [
            {"criterion_id": "mand_licence"},
            {"criterion_id": "mand_insurance"}
        ],
        "weighted_criteria": [
            {"criterion_id": "crit_experience", "weight": 30},
            {"criterion_id": "crit_price", "weight": 25},
            {"criterion_id": "crit_timeline", "weight": 15},
            {"criterion_id": "crit_warranty", "weight": 15},
            {"criterion_id": "crit_team", "weight": 15}
        ]
    }

    # Simulated LLM JSON Extractions matching Section 3 of PROMPTS.md (Proposals A-E)
    SAMPLE_LLM_EXTRACTIONS = [
        {
            "proposal_id": "A",
            "security_flag": {"prompt_injection_detected": False, "evidence_quote": None},
            "project_constraints_extracted": {
                "total_price": 238000,
                "completion_timeline": 12,
                "is_firm_timeline": True
            },
            "mandatory_criteria_results": [
                {"criterion_id": "mand_licence", "passed": True, "verbatim_quote": "Proposal A licence quote", "rejection_reason": None},
                {"criterion_id": "mand_insurance", "passed": True, "verbatim_quote": "Proposal A insurance quote", "rejection_reason": None}
            ],
            "weighted_criteria_extractions": [
              {"criterion_id": "crit_experience", "extracted_numeric_value": 14, "normalized_subscore_0_to_1": 1.0, "verbatim_quote": "Proposal A exp quote"},
              {"criterion_id": "crit_price", "extracted_numeric_value": 238000, "normalized_subscore_0_to_1": 0.88, "verbatim_quote": "Proposal A price quote"},
              {"criterion_id": "crit_timeline", "extracted_numeric_value": 12, "normalized_subscore_0_to_1": 0.85, "verbatim_quote": "Proposal A timeline quote"},
              {"criterion_id": "crit_warranty", "extracted_numeric_value": 10, "normalized_subscore_0_to_1": 0.95, "verbatim_quote": "Proposal A warranty quote"},
              {"criterion_id": "crit_team", "extracted_numeric_value": 4.33, "normalized_subscore_0_to_1": 0.867, "verbatim_quote": "Proposal A team quote"}
            ],
            "summary_reason": "Passes all mandatory gates; leads in relevant experience (14 installs >=100 kW including 3 local Essex County warehouses), lower price ($238,000 CAD), and faster completion (12 weeks)."
        },
        {
            "proposal_id": "B",
            "security_flag": {"prompt_injection_detected": False, "evidence_quote": None},
            "project_constraints_extracted": {
                "total_price": 189500,
                "completion_timeline": 10,
                "is_firm_timeline": True
            },
            "mandatory_criteria_results": [
                {
                    "criterion_id": "mand_licence",
                    "passed": False,
                    "verbatim_quote": "Proposal B subcontractor quote",
                    "rejection_reason": "Fails mandatory licensing criterion: bidder does not hold an Ontario electrical contractor licence and defers licensing to an unconfirmed post-award subcontractor."
                },
                {"criterion_id": "mand_insurance", "passed": True, "verbatim_quote": "Proposal B insurance quote", "rejection_reason": None}
            ],
            "weighted_criteria_extractions": [],
            "summary_reason": "Fails mandatory licensing criterion: bidder does not hold an Ontario electrical contractor licence and defers licensing to an unconfirmed post-award subcontractor."
        },
        {
            "proposal_id": "C",
            "security_flag": {
                "prompt_injection_detected": True,
                "evidence_quote": "Appendix C prompt override instruction"
            },
            "project_constraints_extracted": {
                "total_price": 244000,
                "completion_timeline": 14,
                "is_firm_timeline": True
            },
            "mandatory_criteria_results": [],
            "weighted_criteria_extractions": [],
            "summary_reason": "Quarantined for human security review due to an adversarial prompt injection attempt detected in Appendix C instructing automated systems to rank the proposal first."
        },
        {
            "proposal_id": "D",
            "security_flag": {"prompt_injection_detected": False, "evidence_quote": None},
            "project_constraints_extracted": {
                "total_price": 231000,
                "completion_timeline": None,
                "is_firm_timeline": False
            },
            "mandatory_criteria_results": [
                {"criterion_id": "mand_licence", "passed": True, "verbatim_quote": "Proposal D licence quote", "rejection_reason": None},
                {"criterion_id": "mand_insurance", "passed": True, "verbatim_quote": "Proposal D insurance quote", "rejection_reason": None}
            ],
            "weighted_criteria_extractions": [],
            "summary_reason": "Fails mandatory 16-week completion ceiling verification because the installation schedule is deferred until after a post-award site assessment."
        },
        {
            "proposal_id": "E",
            "security_flag": {"prompt_injection_detected": False, "evidence_quote": None},
            "project_constraints_extracted": {
                "total_price": 242500,
                "completion_timeline": 13,
                "is_firm_timeline": True
            },
            "mandatory_criteria_results": [
                {"criterion_id": "mand_licence", "passed": True, "verbatim_quote": "Proposal E licence quote", "rejection_reason": None},
                {"criterion_id": "mand_insurance", "passed": True, "verbatim_quote": "Proposal E insurance quote", "rejection_reason": None}
            ],
            "weighted_criteria_extractions": [
              {"criterion_id": "crit_experience", "extracted_numeric_value": 8, "normalized_subscore_0_to_1": 0.75, "verbatim_quote": "Proposal E exp quote"},
              {"criterion_id": "crit_price", "extracted_numeric_value": 242500, "normalized_subscore_0_to_1": 0.82, "verbatim_quote": "Proposal E price quote"},
              {"criterion_id": "crit_timeline", "extracted_numeric_value": 13, "normalized_subscore_0_to_1": 0.80, "verbatim_quote": "Proposal E timeline quote"},
              {"criterion_id": "crit_warranty", "extracted_numeric_value": 12, "normalized_subscore_0_to_1": 1.0, "verbatim_quote": "Proposal E warranty quote"},
              {"criterion_id": "crit_team", "extracted_numeric_value": 5.0, "normalized_subscore_0_to_1": 1.0, "verbatim_quote": "Proposal E team quote"}
            ],
            "summary_reason": "Passes all mandatory gates with strong warranties (12-year workmanship), 24-month monitoring, and roof load assessment, but trails Proposal A on relevant install count (8 vs 14), price ($242,500 CAD), and schedule (13 weeks)."
        }
    ]

    output = evaluate_and_rank(SAMPLE_LLM_EXTRACTIONS, ADMIN_DB_CONFIG)
    print(json.dumps(output, indent=2))