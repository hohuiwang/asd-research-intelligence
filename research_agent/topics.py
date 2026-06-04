from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Paper


@dataclass(frozen=True)
class StudyType:
    slug: str
    label: str
    group: str
    reason: str


@dataclass(frozen=True)
class StudyTypeNavItem:
    slug: str
    label: str
    description: str


STUDY_TYPE_NAV = (
    StudyTypeNavItem("all", "All studies", "Every screened paper"),
    StudyTypeNavItem("therapy", "Therapy", "Behavioral, psychosocial, parent, school, or skills interventions"),
    StudyTypeNavItem("non-therapy", "Non-therapy", "Medication, mechanisms, epidemiology, biomarkers, and services"),
    StudyTypeNavItem("medication", "Medication", "Drug, pharmacology, dose, and placebo-controlled medication studies"),
    StudyTypeNavItem("review-synthesis", "Reviews", "Systematic reviews, meta-analyses, and evidence syntheses"),
    StudyTypeNavItem("epidemiology-risk", "Epidemiology/Risk", "Population, registry, exposure, prevalence, burden, and outcome studies"),
    StudyTypeNavItem("measurement-diagnosis", "Measurement/Diagnosis", "Screening, scales, diagnosis, validation, and phenotyping"),
    StudyTypeNavItem("biology-neuroscience", "Biology/Neuroscience", "Brain, EEG, imaging, sensory, biomarker, and mechanism studies"),
    StudyTypeNavItem("genetics-family", "Genetics/Family", "Genetics, familial liability, and intergenerational studies"),
    StudyTypeNavItem("services-lifespan", "Services/Lifespan", "Healthcare, education, employment, quality of life, and adult-life studies"),
    StudyTypeNavItem("other-non-therapy", "Other Non-therapy", "Relevant ASD studies outside the main non-therapy buckets"),
)


MEDICATION_TERMS = (
    "medication",
    "medicine",
    "drug",
    "pharmacologic",
    "pharmacological",
    "pharmacotherapy",
    "dose",
    "mg/day",
    "placebo",
    "adverse event",
    "treatment-emergent",
    "pimavanserin",
    "risperidone",
    "aripiprazole",
    "sertraline",
    "fluoxetine",
    "atomoxetine",
    "methylphenidate",
    "guanfacine",
    "clonidine",
    "oxytocin",
    "bumetanide",
    "metformin",
    "cannabidiol",
    "naltrexone",
    "antipsychotic",
)

THERAPY_TERMS = (
    "therapy",
    "psychotherapy",
    "behavioral intervention",
    "behavioural intervention",
    "parent-mediated",
    "parent mediated",
    "caregiver-mediated",
    "caregiver mediated",
    "early intervention",
    "speech therapy",
    "language intervention",
    "occupational therapy",
    "social skills",
    "cognitive behavioral",
    "cognitive behavioural",
    "cbt",
    "applied behavior analysis",
    "applied behaviour analysis",
    "aba",
    "school-based intervention",
    "skills training",
    "coaching",
    "training program",
)

REVIEW_TERMS = (
    "systematic review",
    "meta-analysis",
    "evidence synthesis",
    "scoping review",
    "review",
)

EPIDEMIOLOGY_TERMS = (
    "population-based",
    "registry",
    "prevalence",
    "incidence",
    "burden",
    "risk",
    "exposure",
    "prenatal",
    "birth",
    "mortality",
    "comorbidity",
    "disparities",
    "nationally representative",
)

MEASUREMENT_TERMS = (
    "measure",
    "measurement",
    "diagnosis",
    "diagnostic",
    "screening",
    "scale",
    "checklist",
    "validity",
    "validation",
    "invariance",
    "factor structure",
    "phenotype",
    "assessment",
)

NEUROSCIENCE_TERMS = (
    "neural",
    "brain",
    "eeg",
    "erp",
    "mismatch negativity",
    "neuroimaging",
    "fmri",
    "imaging",
    "biomarker",
    "sensory",
    "auditory",
    "visual search",
    "eye-tracking",
    "electrophysiological",
    "mechanism",
)

GENETICS_TERMS = (
    "genetic",
    "genetics",
    "genome",
    "genome-wide",
    "whole-genome",
    "exome",
    "polygenic",
    "heritability",
    "familial",
    "family",
    "families",
    "parent",
    "parents",
    "intergenerational",
    "liability",
    "co-aggregation",
    "transmission",
)

SERVICES_TERMS = (
    "healthcare",
    "health care",
    "service",
    "services",
    "quality of life",
    "social support",
    "employment",
    "independent living",
    "transition",
    "education",
    "school",
    "physical activity",
    "sport",
    "policy",
    "adult life",
)


def classify_study_type(paper: Paper) -> StudyType:
    text = _paper_text(paper)
    title_text = paper.title.lower()
    publication_types = " ".join(paper.publication_types).lower()

    if _contains_any(text, MEDICATION_TERMS):
        return StudyType("medication", "Medication", "non_therapy", "medication/pharmacology signal")
    if _contains_any(text, THERAPY_TERMS):
        return StudyType("therapy", "Therapy", "therapy", "therapy or behavioral intervention signal")
    if _contains_any(text + " " + publication_types, REVIEW_TERMS):
        return StudyType("review-synthesis", "Reviews", "non_therapy", "review or synthesis signal")
    if _contains_any(title_text, EPIDEMIOLOGY_TERMS):
        return StudyType("epidemiology-risk", "Epidemiology/Risk", "non_therapy", "population, registry, exposure, or risk signal")
    if _contains_any(text, GENETICS_TERMS):
        return StudyType("genetics-family", "Genetics/Family", "non_therapy", "genetic, familial, or intergenerational signal")
    if _contains_any(text, SERVICES_TERMS):
        return StudyType("services-lifespan", "Services/Lifespan", "non_therapy", "services, quality-of-life, education, or adult-life signal")
    if _contains_any(text, MEASUREMENT_TERMS):
        return StudyType("measurement-diagnosis", "Measurement/Diagnosis", "non_therapy", "measurement, screening, or diagnosis signal")
    if _contains_any(text, EPIDEMIOLOGY_TERMS):
        return StudyType("epidemiology-risk", "Epidemiology/Risk", "non_therapy", "population, registry, exposure, or risk signal")
    if _contains_any(text, NEUROSCIENCE_TERMS):
        return StudyType("biology-neuroscience", "Biology/Neuroscience", "non_therapy", "brain, sensory, biomarker, or mechanism signal")
    return StudyType("other-non-therapy", "Other Non-therapy", "non_therapy", "no more specific study-type signal")


def study_type_matches(paper: dict, slug: str) -> bool:
    if slug == "all":
        return True
    if slug == "therapy":
        return paper["study_type_group"] == "therapy"
    if slug == "non-therapy":
        return paper["study_type_group"] == "non_therapy"
    return paper["study_type_slug"] == slug


def _paper_text(paper: Paper) -> str:
    return f"{paper.title}\n{paper.abstract}\n{' '.join(paper.publication_types)}".lower()


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(_contains_phrase(text, term) for term in terms)


def _contains_phrase(text: str, phrase: str) -> bool:
    pattern = r"\b" + re.escape(phrase).replace(r"\ ", r"\s+") + r"\b"
    return re.search(pattern, text) is not None
