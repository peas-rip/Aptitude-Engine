# Product Requirements Document: Question Metadata Engine

## 1. Product Overview

### 1.1 Product Name
Question Metadata Engine (QME)

### 1.2 Vision Statement
Transform raw aptitude questions from diverse sources into standardized, metadata-rich structured objects ready for downstream consumption by a Question Deduplication/Ingestion Engine.

### 1.3 Problem Statement
Raw aptitude questions exist in unstructured formats (PDF, DOCX, TXT, CSV, manual entry) with inconsistent metadata. Downstream systems need structured, validated, enriched question objects with:
- Hierarchical topic classification
- Quantitative difficulty scoring with explainable factors
- Step-by-step solutions (extracted or generated)
- Formula references for knowledge base linking
- Full provenance tracking
- Validation status for quality assurance

### 1.4 Success Criteria
- Process 1,000-10,000 questions per batch with <5% failure rate
- Topic/subtopic classification accuracy >90% against gold standard
- Difficulty score correlation >0.8 with expert ratings
- Solution generation correctness >95% for generated solutions
- End-to-end processing cost <.05 per question at scale
- Zero silent data corruption (all failures explicit)

## 2. Users and Roles

### 2.1 Primary User: Data Engineering Team
- Workflow: Upload batch files -> Monitor processing -> Review flagged items -> Export JSONL
- Needs: Reliability, observability, retry/resume, cost visibility

### 2.2 Secondary User: ML/Content Team
- Workflow: Curate taxonomy -> Review classification quality -> Adjust prompts -> Reprocess
- Needs: Versioned taxonomy, prompt versioning, reprocessing capability, evaluation metrics

### 2.3 Downstream Consumer: Deduplication Engine (System)
- Interface: Consumes JSONL output via file transfer or API
- Needs: Stable schema, complete metadata, embedding-ready fields

## 3. Core Features

### 3.1 Question Extraction & Normalization (FE-001)
Extract question text, options, answer from raw input formats.

### 3.2 Topic/Subtopic Classification (FE-002)
Hierarchical classification using versioned taxonomy with LLM + human curation.

### 3.3 Difficulty Scoring (FE-003)
Multi-factor difficulty model outputting 0-10 score, rating, factors, estimated time.

### 3.4 Solution Engine (FE-004)
Extract existing solutions or generate step-by-step solutions with validation.

### 3.5 Formula Identification (FE-005)
Identify formulas used, output references for future Formula KB linking.

### 3.6 Multi-Layer Validation (FE-006)
Schema, answer, calculation, consistency, and confidence validation.

### 3.7 Batch Processing Pipeline (FE-007)
Checkpointed, resumable batch processing with partial failure handling.

### 3.8 Source Tracking & Versioning (FE-008)
Full provenance: source, page, extraction timestamp, model/prompt versions.

### 3.9 Human Review Workflow (FE-009)
Flag questions for review: needs_review status with reason codes.

### 3.10 Observability & Cost Tracking (FE-010)
Metrics, logging, token usage, estimated cost per question/batch.

## 4. Non-Functional Requirements

### 4.1 Performance
- Single question: <30 seconds p95
- Batch 10K: <8 hours wall time (sequential)
- Memory: <2GB per worker

### 4.2 Reliability
- Checkpoint every 10 questions
- Automatic retry (3x with exponential backoff)
- No silent failures - all errors logged with context

### 4.3 Security
- API keys in environment variables / secret manager
- Input sanitization for prompt injection
- File type validation, size limits
- No PII in questions (assumed)

### 4.4 Extensibility
- Pluggable classifier/solver/validator interfaces
- Taxonomy versioning without code changes
- Prompt/model versioning for reproducibility

## 5. Out of Scope (V1)
- Question deduplication
- Student-facing interfaces
- Test generation
- Payment/billing
- User management/authentication
- Real-time/streaming processing
- Formula knowledge base (references only)
- Admin dashboard (CLI + API only)
- Multi-tenancy

## 6. Assumptions
- Input questions are legally sourced/licensed
- Questions are primarily Quantitative Aptitude (math/logic)
- English language only (V1)
- OpenAI API available and within rate limits
- Team comfortable with Python/FastAPI operations
