# Feature Specification: Solution Engine

## Business Goal
Produce step-by-step solution for every question: extract from source if available, otherwise generate.

## User Flow
1. Receive NormalizedQuestion + ClassificationResult + DifficultyResult
2. Check if source provides solution
3. If yes: extract mode -> parse and normalize existing solution
4. If no: generate mode -> LLM creates solution from scratch
5. Structure: steps with descriptions, formula refs, calculations, results
6. Verify final answer matches correct_answer
7. Output: SolutionResult with source (extracted/generated) and confidence

## Service Ownership
metadata-engine -> pipeline/stages/solution.py

## Database Requirements
- questions table: solution (JSONB), solution_source, solution_confidence

## API Requirements
- Internal: SolutionEngine protocol with solve() and extract_existing()
- Models: SolutionStep, SolutionResult
- Config: model selection (4o for generate, 4o-mini for extract)

## Validation Requirements
- Steps sequential, non-empty
- Formula refs match known formulas (or flagged unknown)
- Calculations syntactically valid
- Final answer matches correct_answer (validated in FE-006)
- Confidence >= 0.8 for generated, >=0.9 for extracted

## Security Requirements
- Prompt injection: sanitize question text
- No code execution from LLM calculations

## Dependencies
- Requires: ClassificationResult, DifficultyResult
- Provides: SolutionResult for Formula Extraction, Validation

## Edge Cases
- Source solution incomplete -> supplement with generation
- Source solution incorrect -> detect in validation, flag review
- Multi-step with branching -> linearize steps
- Diagram/figure references -> note in step description

## Error Handling
- Generation failure -> retry (max 3), then flag needs_review
- Answer mismatch -> flag needs_review (do not auto-correct)
- Low confidence -> flag needs_review

## Acceptance Criteria
- Generated solutions correct >95% on gold standard
- Extracted solutions normalized consistently
- Step structure uniform
- Confidence correlates with correctness

## Success Criteria
- Generation latency <15s p95
- Cost <.03/question (generated)
- Review rate <5% for generated
