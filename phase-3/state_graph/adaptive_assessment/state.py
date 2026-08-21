"""
Adaptive Assessment & Mastery Evaluation — LangGraph state schema.

Nodes (defined later in graph.py) that read/write this state:
    start_assessment -> select_next_question (Task Decomposition)
        -> evaluate_answer (Constrained ReAct)
        -> check_mastery_or_continue
            -> [more questions needed] select_next_question   (real cycle)
            -> [done] finalize -> flag_for_review (HITL, conditional)
               -> record_grade -> log_and_close

Design notes (mirrors state_graph/academic_integrity/state.py on purpose,
same reasoning applies here):
- Pydantic BaseModel, not TypedDict: this state is written to by an LLM
  (select_next_question, evaluate_answer) and by an admin through the
  platform's HITL UI (flag_for_review) -- both untrusted entry points.
- `answers` uses an Annotated[..., add] reducer because select_next_question
  and evaluate_answer run more than once per session (that's the whole
  point of the cycle) and each pass appends one more answered question.
- `session_id` doubles as the LangGraph thread_id source (checkpointing.py):
  thread_id = f"adaptive-assessment-{session_id}".
"""

from __future__ import annotations

from operator import add
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field


class AnsweredQuestion(BaseModel):
    answer_id: Optional[int] = None  # set once written to AssessmentAnswers
    question_text: str
    difficulty: Literal["easy", "medium", "hard"]
    student_answer: str
    expected_answer: Optional[str] = None  # set by select_next_question; lets
        # evaluate_answer's GRADE_EXACT action do a real comparison instead
        # of a Python dispatcher with nothing to check against
    is_correct: Optional[bool] = None
    score_awarded: Optional[float] = None  # 0.0-1.0 for this one question
    options: Optional[list[str]] = None


class AdaptiveAssessmentState(BaseModel):
    # --- session identity (mirrors AssessmentSessions columns) ---
    session_id: Optional[int] = None  # None until the session row is first inserted
    student_id: int
    course_id: int
    topic: str

    # --- adaptive loop state ---
    answers: list[AnsweredQuestion] = Field(default_factory=list)
    current_difficulty: Literal["easy", "medium", "hard"] = "medium"
    pending_question: Optional[AnsweredQuestion] = None  # asked, not yet answered
    subskills_to_probe: list[str] = Field(default_factory=list)  # Task Decomposition output
    subskills_covered: list[str] = Field(default_factory=list)

    # --- config (set once at start_assessment, read by check_mastery_or_continue) ---
    max_questions: int = 8
    mastery_threshold: float = 0.75

    # --- workflow status ---
    status: Literal["in_progress", "flagged_for_review", "completed"] = "in_progress"

    # --- outcome ---
    running_score: float = 0.0  # running average of answers[*].score_awarded
    mastery_level: Optional[Literal["novice", "developing", "proficient", "mastered"]] = None
    final_score: Optional[float] = None

    # --- HITL (flag_for_review) ---
    flagged: bool = False
    flag_reason: Optional[str] = None  # e.g. "score within 5% of mastery threshold"
    reviewed_by: Optional[str] = None
    review_decision: Optional[Literal["approve", "adjust_score", "retake"]] = None
    review_notes: Optional[str] = None
    adjusted_score: Optional[float] = None

    # --- failure / ticket path (kept separate from HITL, same as academic_integrity) ---
    last_error: Optional[str] = None

    # --- bookkeeping ---
    thread_id: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True