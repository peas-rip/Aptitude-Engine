"""Test & Practice Agent: deterministic assembly from the external agent's bank."""

from qme.testgen.assembler import generate_test
from qme.testgen.bank import Bank, load_bank
from qme.testgen.errors import ContractError, SelectionError, SubmissionError, TestGenError
from qme.testgen.practice import generate_practice
from qme.testgen.schemas import (
    ChapterKnowledge,
    GeneratedTest,
    PracticeRequest,
    PracticeSet,
    SubmitRequest,
    TestRequest,
    TestResult,
    TestSpec,
)
from qme.testgen.scoring import score_test
from qme.testgen.spec import compile_spec, parse_test_request

__all__ = [
    "Bank",
    "ChapterKnowledge",
    "ContractError",
    "GeneratedTest",
    "PracticeRequest",
    "PracticeSet",
    "SelectionError",
    "SubmissionError",
    "SubmitRequest",
    "TestGenError",
    "TestRequest",
    "TestResult",
    "TestSpec",
    "compile_spec",
    "generate_practice",
    "generate_test",
    "load_bank",
    "parse_test_request",
    "score_test",
]
