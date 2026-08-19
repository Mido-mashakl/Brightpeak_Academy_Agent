# Brightpeak Academy — Faculty Hiring Policies

These are static, job-independent hiring rules. They are retrieved via RAG
(`search_policies(category="hiring")`) and injected into the CV parsing and
scoring prompts. They are NOT specific to any single job posting — job-specific
qualifications live in `JobPostings.qualifications` and are injected separately.

## 1. Never invent missing information

If a CV does not explicitly state a qualification, years of experience, a
degree, or any other fact, that field must be recorded as missing (`null` /
`MISSING`) — never guessed, inferred, or estimated from context.

Example: a CV that lists skills but never mentions years of experience must
have `years_experience = null`. It must never be filled in as "probably 2-3
years" or any other invented value, even if the candidate's other
qualifications make that plausible.

This rule applies identically during initial scoring and during re-scoring.

## 2. How missing qualifications should be handled during scoring

A qualification with no evidence in the CV must be marked `MISSING`, not
`FAIL`. `FAIL` is reserved for qualifications the CV actively contradicts or
clearly does not meet (e.g. the job requires 2+ years and the CV states less
than one year).

`MISSING` should reduce the overall score less than an explicit `FAIL`,
because absence of evidence is not evidence of absence — the candidate may
simply not have listed it.

## 3. Rules for scoring

- Score every qualification the job posting lists; do not add or drop
  qualifications that aren't in `JobPostings.qualifications`.
- Teaching experience is weighted more heavily for instructor-track postings
  than for non-teaching academic roles, since classroom performance is a core
  part of the job.
- The overall score must stay within 0–100.
- Every score must be accompanied by a per-qualification breakdown
  (PASS / FAIL / MISSING plus the evidence or lack of evidence found in the
  CV) so a human reviewer can see exactly why a candidate scored the way they
  did — scores should never be a bare number with no justification.

## 4. Rules for re-scoring

- Only re-score candidates the Department Head explicitly selected. Do not
  re-score the full candidate pool just because one candidate was
  re-evaluated.
- A re-score must use the same missing-data rule as the initial score: new
  weighting instructions from the Department Head (e.g. "weight teaching
  experience more heavily") may change the score, but must never be used as
  license to invent facts that aren't in the CV.
- Keep the prior score on record (`CandidateScores.trigger = 'initial'`) and
  insert the re-score as a new row (`trigger = 'rescore'`) rather than
  overwriting history, so the Department Head can see how and why a ranking
  changed.

## 5. General hiring policy

- A hiring decision (hire / reject) is always made by an authenticated
  Department Head — the system may rank, summarize, and recommend, but it
  never finalizes a hiring outcome on its own.
- An interview request does not imply a decision; the candidate returns to
  Department Head review after the interview result is recorded.
- All candidate data is scoped to the job it was submitted for. A candidate's
  CV must never be retrieved or considered while evaluating a different job
  posting.
