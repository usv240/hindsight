"""The scenario library: the same defect, told in domains people already know.

Leakage is domain-agnostic, but "credit default at origination" is not a story
most visitors can hold. Each scenario here is a real, runnable audit - its own
data, its own seed, its own SQL - wrapped in a concrete situation with a person
in it. Someone who has never trained a model can pick the one closest to their
world and follow the whole argument.

Every scenario is synthetic. No real person is represented in any of them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Scenario:
    slug: str
    name: str
    domain: str
    icon: str
    # The situation, in one sentence a stranger understands.
    situation: str
    # The question the model is asked to answer.
    question: str
    # The moment after which nothing may be known.
    cutoff_moment: str
    # What the model cheated with, in everyday words.
    leak_plain: str
    # Why the cheat is invisible until production.
    leak_why_hidden: str
    # What a person should do about it.
    fix_plain: str
    # What it costs if nobody catches it.
    stakes: str
    audit_config: str
    available: bool = True
    story: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "domain": self.domain,
            "icon": self.icon,
            "situation": self.situation,
            "question": self.question,
            "cutoff_moment": self.cutoff_moment,
            "leak_plain": self.leak_plain,
            "leak_why_hidden": self.leak_why_hidden,
            "fix_plain": self.fix_plain,
            "stakes": self.stakes,
            "audit_config": self.audit_config,
            "available": self.available,
            "story": self.story,
        }


SCENARIOS: dict[str, Scenario] = {
    "credit_default": Scenario(
        slug="credit_default",
        name="Loan approval",
        domain="Lending",
        icon="bank",
        situation=(
            "A bank wants to predict whether someone will repay a loan, so it can decide "
            "who to approve."
        ),
        question="Will this applicant repay the loan?",
        cutoff_moment="the moment the loan is approved or declined",
        leak_plain=(
            "The model was given how long it had been since the customer's last payment - "
            "but it counted payments made AFTER the loan was already approved."
        ),
        leak_why_hidden=(
            "In testing, every application already has months of payment history attached, "
            "because the test data was collected later. On the day of a real decision, none "
            "of it exists yet."
        ),
        fix_plain=("Rebuild the feature so it only counts payments recorded before the decision."),
        stakes=(
            "The bank approves people it should have declined and declines people it should "
            "have approved - and only finds out months later, one default at a time."
        ),
        audit_config="audits/credit_default.json",
        story=[
            {
                "when": "Day 0",
                "what": "Maya applies for a loan. The bank must decide today.",
                "note": "Everything the model is allowed to know stops here.",
            },
            {
                "when": "Day 31",
                "what": "Maya makes her first payment.",
                "note": "This fact did not exist when the decision was made.",
            },
            {
                "when": "Later",
                "what": "Someone builds a training set and joins in all payment history.",
                "note": "The model can now see Day 31 while pretending to sit on Day 0.",
            },
            {
                "when": "Testing",
                "what": "The model looks flawless.",
                "note": "Of course it does. It is reading the answer.",
            },
        ],
    ),
    "credit_default_fixed": Scenario(
        slug="credit_default_fixed",
        name="The same loan model, fixed",
        domain="Lending",
        icon="check",
        situation=(
            "The same bank, after applying the one-line repair Hindsight proposed. This is "
            "what a clean audit looks like."
        ),
        question="Will this applicant repay the loan?",
        cutoff_moment="the moment the loan is approved or declined",
        leak_plain=(
            "Nothing. The feature under audit only uses information that existed before the "
            "decision, and the query that builds it says so explicitly."
        ),
        leak_why_hidden=(
            "There is nothing hidden here. This scenario exists so you can see the tool clear "
            "a model as well as block one - a gate that only ever says no is not a gate."
        ),
        fix_plain="No action needed. This version is safe to release.",
        stakes=(
            "A reviewer can trust a block only if a clear is also possible. This is the "
            "control on the whole product."
        ),
        audit_config="audits/credit_default_fixed.json",
        story=[
            {
                "when": "Day 0",
                "what": "Maya applies for a loan. The bank must decide today.",
                "note": "Everything the model is allowed to know stops here.",
            },
            {
                "when": "Day 31",
                "what": "Maya makes her first payment.",
                "note": "The repaired query explicitly refuses to look at this.",
            },
            {
                "when": "Later",
                "what": "The training set is rebuilt with the availability guard in place.",
                "note": "Only pre-decision facts survive the join.",
            },
            {
                "when": "Testing",
                "what": "The model scores well - and keeps that score honestly.",
                "note": "Its advantage survives the rebuild, so it is real.",
            },
        ],
    ),
    "hospital_readmission": Scenario(
        slug="hospital_readmission",
        name="Hospital readmission",
        domain="Healthcare",
        icon="pulse",
        situation=(
            "A hospital wants to predict which patients will be readmitted within 30 days, "
            "so it can offer extra follow-up care at discharge."
        ),
        question="Will this patient be readmitted within 30 days?",
        cutoff_moment="the moment the patient is discharged",
        leak_plain=(
            "The model was given the patient's follow-up appointment count - but it counted "
            "appointments booked AFTER discharge, which only happen when someone is already "
            "getting sicker."
        ),
        leak_why_hidden=(
            "Follow-up bookings look like ordinary patient history in the warehouse. Nothing "
            "about the column name says these were created after the patient went home."
        ),
        fix_plain=("Count only appointments that existed on the discharge date."),
        stakes=(
            "Extra care goes to the wrong patients. The people who actually needed follow-up "
            "are sent home unsupported."
        ),
        audit_config="audits/hospital_readmission.json",
        story=[
            {
                "when": "Day 0",
                "what": "A patient is discharged. Care teams decide follow-up today.",
                "note": "Everything the model is allowed to know stops here.",
            },
            {
                "when": "Day 22",
                "what": "The patient books an urgent follow-up appointment.",
                "note": "A strong signal - and completely unavailable at discharge.",
            },
            {
                "when": "Later",
                "what": "The training set joins in all appointments, whenever they happened.",
                "note": "The model reads Day 22 while pretending to sit on Day 0.",
            },
            {
                "when": "Testing",
                "what": "The model spots nearly every readmission.",
                "note": "Because it is being told the answer.",
            },
        ],
    ),
    "fraud_screening": Scenario(
        slug="fraud_screening",
        name="Fraud screening",
        domain="Payments",
        icon="shield",
        situation=(
            "A payments company wants to block fraudulent transactions in real time, before "
            "the money moves."
        ),
        question="Is this transaction fraudulent?",
        cutoff_moment="the instant the transaction is authorised or declined",
        leak_plain=(
            "The model was given a 'disputes on this account' count - but disputes are filed "
            "days after the fraud happens, so the number was effectively the answer."
        ),
        leak_why_hidden=(
            "The dispute table is joined on account ID with no time filter at all. It looks "
            "like any other account attribute."
        ),
        fix_plain=("Only count disputes filed before the transaction timestamp."),
        stakes=(
            "The model appears near-perfect in evaluation and then blocks almost nothing in "
            "production, because at authorisation time the dispute count is always zero."
        ),
        audit_config="audits/fraud_screening.json",
        story=[
            {
                "when": "Second 0",
                "what": "A card is swiped. Authorise or decline, right now.",
                "note": "Everything the model is allowed to know stops here.",
            },
            {
                "when": "Day 9",
                "what": "The cardholder notices and files a dispute.",
                "note": "This is how the fraud became known at all.",
            },
            {
                "when": "Later",
                "what": "Training data joins disputes to transactions with no time filter.",
                "note": "The dispute count is now a near-perfect label in disguise.",
            },
            {
                "when": "Testing",
                "what": "Fraud detection looks solved.",
                "note": "In production the same feature is always zero.",
            },
        ],
    ),
}

DEFAULT_SCENARIO = "credit_default"


def get_scenario(slug: str | None) -> Scenario:
    return SCENARIOS.get(slug or DEFAULT_SCENARIO, SCENARIOS[DEFAULT_SCENARIO])


def list_scenarios() -> list[Scenario]:
    return list(SCENARIOS.values())
