# Feature Specification: Formula Identification

## Business Goal
Identify formulas used in solution, output standardized references for future Formula KB linking.

## User Flow
1. Receive NormalizedQuestion + SolutionResult + ClassificationResult
2. Build formula extraction prompt
3. Call LLM (GPT-4o-mini) with structured output
4. For each formula: name, expression, category, reference_id (if known)
5. Unknown formulas: flag for KB addition
6. Output: FormulaResult

## Service Ownership
metadata-engine -> pipeline/stages/formula.py

## Database Requirements
- questions table: formulas_used (JSONB array of FormulaRef)
- Future: formulas table for KB

## API Requirements
- Internal: FormulaExtractor protocol
- FormulaRef model: name, expression, category, reference_id, confidence
- Config: known_formula_catalog (optional, for reference_id matching)

## Validation Requirements
- Every formula in solution steps referenced
- Expression mathematically valid (basic check)
- Category from controlled vocabulary
- Unknown formulas listed separately

## Security Requirements
- Prompt injection prevention

## Dependencies
- Requires: SolutionResult (steps, formulas_used)
- Provides: FormulaResult for Output, future KB linking

## Edge Cases
- Implicit formulas (not named in solution) -> infer from steps
- Compound formulas -> break into components
- Unit conversions -> standard category
- Approximations (pi approx 3.14) -> note in expression

## Error Handling
- Extraction failure -> retry, then empty list with warning
- Unknown formula -> include with reference_id=null, flag for review

## Acceptance Criteria
- Known formula recall >95%
- Expression format consistent
- Unknown formulas explicitly listed
- Reference IDs match future KB schema

## Success Criteria
- Latency <3s p95
- Cost <.005/question
- Zero missing formula references
