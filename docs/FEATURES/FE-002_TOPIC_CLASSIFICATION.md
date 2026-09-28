# Feature Specification: Topic/Subtopic Classification

## Business Goal
Classify each question into a hierarchical taxonomy: Category -> Topic -> Subtopic, with concepts and tags.

## User Flow
1. Receive NormalizedQuestion from extraction
2. Load current taxonomy version
3. Build classification prompt with taxonomy context
4. Call LLM (GPT-4o-mini) with structured output
5. Validate response against taxonomy (IDs exist)
6. Attach confidence score
7. Output: ClassificationResult

## Service Ownership
metadata-engine -> pipeline/stages/classifier.py

## Database Requirements
- taxonomy_nodes table (hierarchical)
- taxonomy_versions table (version control)
- questions table: category_id, topic_id, subtopic_id FKs

## API Requirements
- Internal: QuestionClassifier protocol
- Config: confidence_threshold (default 0.7)
- Taxonomy version recorded in output

## Validation Requirements
- Returned IDs must exist in current taxonomy
- Confidence >= threshold -> auto-accept
- Confidence < threshold -> flag needs_review
- Concepts array non-empty
- question_type: mcq, numeric, multi_select

## Security Requirements
- Prompt injection: sanitize question text before embedding in prompt
- Taxonomy loaded from trusted source (local YAML/DB)

## Dependencies
- Requires: NormalizedQuestion (FE-001)
- Provides: ClassificationResult for Difficulty, Solution, Formula

## Edge Cases
- Question spans multiple topics -> primary + secondary
- New topic not in taxonomy -> flag for taxonomy update
- Ambiguous classification -> low confidence -> review
- Taxonomy version mismatch -> use version from processing run

## Error Handling
- LLM parse failure -> retry (max 3)
- Taxonomy validation failure -> flag needs_review
- API timeout -> retry with backoff

## Acceptance Criteria
- Gold standard: >90% accuracy on 200 questions
- Structured output parsing: 100% success
- Taxonomy version recorded
- Low confidence flagged for review

## Success Criteria
- Classification latency <5s p95
- Cost <.01/question
- Review rate <10% on clean data
