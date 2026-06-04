from __future__ import annotations

from .models import Paper


SAMPLE_PAPERS = [
    Paper(
        pmid="00000001",
        title="Population-based longitudinal study of health care use among autistic adolescents",
        abstract=(
            "This population-based longitudinal cohort study included 12450 autistic adolescents "
            "and matched comparison participants. The study examined emergency care, outpatient "
            "service use, and transition-age outcomes among youth ages 13 to 24."
        ),
        journal="Journal of Child Psychology and Psychiatry",
        publication_date="2026-05-01",
        doi="10.0000/demo.1",
        authors=("Demo A", "Demo B"),
        publication_types=("Journal Article",),
    ),
    Paper(
        pmid="00000002",
        title="Randomized clinical trial of a parent-mediated intervention for toddlers with autism",
        abstract=(
            "A randomized clinical trial tested a parent-mediated intervention in toddlers with "
            "autism spectrum disorder. The sample of 180 children was followed for language and "
            "adaptive behavior outcomes."
        ),
        journal="JAMA Pediatrics",
        publication_date="2026-05-03",
        doi="10.0000/demo.2",
        authors=("Demo C", "Demo D"),
        publication_types=("Randomized Controlled Trial", "Clinical Trial"),
    ),
    Paper(
        pmid="00000003",
        title="Narrative commentary on autism awareness campaigns",
        abstract=(
            "This commentary discusses public awareness and advocacy messaging. It does not report "
            "new human participant data, sample size, or systematic review methods."
        ),
        journal="Community Perspectives",
        publication_date="2026-05-05",
        authors=("Demo E",),
        publication_types=("Comment",),
    ),
]

