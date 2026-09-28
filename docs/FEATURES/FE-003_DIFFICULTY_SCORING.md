# Feature Specification: Difficulty Scoring

## Business Goal
Assign quantitative difficulty score (0-10) with explainable factors and estimated solving time.

## User Flow
1. Receive NormalizedQuestion + ClassificationResult
2. Build difficulty prompt with factor definitions
3. Call LLM (GPT-4o-mini) with structured output
4. Parse factors: concept_count, reasoning_complexity, calculation_complexity, steps, ambiguity, formula_complexity
5. Apply weighted scoring algorithm
6. Map score to rating: easy (0-3.5), medium (3.5-6.5), hard (6.5-10)
7. Estimate time: base + factor adjustments
8. Output: DifficultyResult

## Service Ownership
metadata-engine -> pipeline/stages/difficulty.py

## Database Requirements
- questions table: difficulty_score, difficulty_rating, difficulty_factors (JSONB), estimated_time_sec

## API Requirements
- Internal: DifficultyEngine protocol
- Config: factor_weights (JSON), rating_thresholds, base_time_sec

## Validation Requirements
- Score in range 0.0-10.0
- All 6 factors present with scores 0-10
- Rating matches score thresholds
- Estimated time >0
- Confidence >= threshold (default 0.7)

## Security Requirements
- Prompt injection prevention
- Factor weights from config (not LLM)

## Dependencies
- Requires: ClassificationResult (concepts, question_type)
- Provides: DifficultyResult for Solution, Formula, Output

## Edge Cases
- Trivial questions (score ~1) -> verify not under-scored
- Extremely complex (score ~9) -> verify not over-scored
- Missing concepts -> use classification concepts
- Subjective factors -> explicit reasoning in output

## Error Handling
- LLM failure -> retry, then default to median (5.0) with low confidence
- Factor parsing failure -> flag needs_review

## Acceptance Criteria
- Score distribution: ~20% easy, ~60% medium, ~20% hard
- Correlation with expert ratings >0.8
- Factor contributions explainable (reasoning field)
- Versioned methodology in output

## Success Criteria
- Consistent scoring across similar questions
- Explainable factors for audit
- Low review rate (<5%)
