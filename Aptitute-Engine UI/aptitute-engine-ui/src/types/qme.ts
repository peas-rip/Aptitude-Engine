// ── Enums & primitives ────────────────────────────────────────────────────
export type Difficulty = "easy" | "medium" | "hard";
export type TestMode = "progressive" | "mixed";

/** Chapter separator: " › " (space + U+203A + space). */
export const CHAPTER_SEP = " › ";

// ── Questions (bank records, returned byte-for-byte, never altered) ───────
export interface BankClassification {
  chapter: string;                     // raw chapter label, NOT qualified
  topic: string;
  difficulty: Difficulty;
  difficulty_basis: string | null;
  source_label_basis: string | null;
}

export interface BankAgentMetadata {
  question_type: string;               // e.g. "mcq"
  skills: string[];
  generation_tags: string[];
  recommended_use: string[];
  estimated_time_seconds: number;      // >= 0, drives `timing`
}

export interface BankFinalAnswer {
  option_key: string;                  // e.g. "B"
  option_text: string | null;
}

export interface BankSolution {
  method: string;
  steps: string[];
  final_answer: BankFinalAnswer;
  solution_basis: string | null;
}

export interface BankSource {
  name: string;                        // == source key (verbatim)
  type: string;                        // e.g. "pdf"
  identifier: string | null;
  page: number | null;
  question_id: string | null;
}

export interface BankQuestion {
  question_id: string;                 // globally unique, your answers-map key
  question_text: string;
  options: Record<string, string>;     // { "A": "...", "B": "..." }
  correct_answer: string;              // option key, e.g. "B"
  answer_text: string | null;
  classification: BankClassification;
  agent_metadata: BankAgentMetadata;
  solution: BankSolution;
  formula_refs: string[];
  source: BankSource;
}

// ── Test assembly ─────────────────────────────────────────────────────────
export interface Selection {
  count: number;                       // required, >= 1
  source?: string | null;
  chapter?: string | null;             // legacy: RAW chapter name
  chapters?: string[];                 // friendly scope: QUALIFIED keys
  topic?: string | null;
  difficulty?: Difficulty | null;
  question_type?: string | null;
  skills?: string[];
  page_min?: number | null;
  page_max?: number | null;
}

export interface Shortage {
  selection_index: number;
  requested: number;
  provided: number;
  shortfall: number;
  filters: Record<string, unknown>;
}

export interface Coverage {
  total: number;
  by_chapter: Record<string, number>;  // QUALIFIED chapter keys
  by_topic: Record<string, number>;
  by_difficulty: Record<string, number>;
  by_source: Record<string, number>;
}

export interface Timing {
  estimated_total_sec: number;         // good seed for your countdown
  avg_per_question_sec: number;
  min_sec: number;
  max_sec: number;
}

export interface AnswerKeyEntry {
  question_id: string;
  correct_answer: string;
  answer_text: string | null;
  solution_steps: string[];
}

export interface GeneratedTest {
  test_id: string;
  title: string | null;
  seed: number | null;
  generated_at: string;                // ISO-8601
  contract_source: {
    blueprint: string;
    schema_version: string | number;
    question_bank: string;
    knowledge_bank: string;
  };
  selections_applied: Selection[];     // compiled form for friendly requests
  selection_rules_applied: string[];   // human-readable
  questions: BankQuestion[];
  answer_key: AnswerKeyEntry[];        // parallel to `questions`
  coverage: Coverage;
  timing: Timing;
  shortages: Shortage[];               // empty for friendly-shape requests
  notes: Record<string, unknown>;      // e.g. { overlaps_dropped: 3 }
}

// ── Practice ──────────────────────────────────────────────────────────────
export interface Pagination {
  page: number;                        // >= 1
  count: number;                       // page size
  total: number;                       // full pool size
  total_pages: number;
  has_more: boolean;
}

export interface KnowledgeTerms {
  formulas: string[];
  short_tricks: string[];
}

export interface PracticeSet {
  practice_id: string;
  title: string | null;
  seed: number | null;                 // ECHO — reuse for page+1
  generated_at: string;
  mode: TestMode;
  filters_applied: Record<string, unknown>;
  questions: BankQuestion[];
  coverage: Coverage;
  timing: Timing;
  pagination: Pagination | null;
  shortages: Shortage[];               // always [] for practice
  topic_knowledge: Record<string, KnowledgeTerms>;
  chapter_formula_summary: string[];   // [] unless the page spans one chapter
}

// ── Scoring ───────────────────────────────────────────────────────────────
export interface ScoreBreakup {
  correct: number;
  total: number;
  percent: number;                     // 0..100, 1 decimal
}

export interface ResultLine {
  question_id: string;
  your_answer: string | null;          // null => not answered (counts wrong)
  correct_answer: string;
  answer_text: string | null;
  is_correct: boolean;
  solution_steps: string[];
  difficulty: Difficulty;
  chapter: string;                     // QUALIFIED chapter key
  source: string;
}

export interface TestResult {
  test_id: string;
  score: ScoreBreakup;
  by_difficulty: Partial<Record<Difficulty, ScoreBreakup>>;
  by_chapter: Record<string, ScoreBreakup>;
  by_source: Record<string, ScoreBreakup>;
  elapsed_seconds: number | null;
  results: ResultLine[];               // one per question, in test order
}

// ── Knowledge ─────────────────────────────────────────────────────────────
export interface ChapterKnowledge {
  chapter: string;                     // UNQUALIFIED label
  topic: string | null;
  formula_summary: string[];
  topics: Record<string, KnowledgeTerms>;
}

// ── Discovery (GET /bank/meta) ────────────────────────────────────────────
export interface ChapterInfo {
  key: string;                         // QUALIFIED "Source › Chapter"
  label: string;                       // raw chapter name
  question_count: number;
  difficulty_counts: Partial<Record<Difficulty, number>>; // absent key => 0
}

export interface SourceInfo {
  name: string;                        // source key, verbatim
  question_count: number;
  chapters: ChapterInfo[];
}

export interface KnowledgeCoverage {
  covered_chapters: string[];          // UNQUALIFIED names
  missing_chapters: string[];
}

export interface TestGenerationContract {
  required_filters: string[];
  optional_filters: string[];
  selection_rules: string[];
  output_fields: string[];
}

export interface BankMeta {
  sources: SourceInfo[];
  chapters: string[];                  // qualified, sorted
  topics: string[];                    // sorted
  difficulties: string[];              // only those present
  question_count: number;
  buckets: Record<string, Record<string, Partial<Record<Difficulty, number>>>>;
  knowledge_coverage: KnowledgeCoverage;
  contract: TestGenerationContract;
}

// ── Request types ─────────────────────────────────────────────────────────
/** POST /tests — friendly shape (recommended). */
export interface FriendlyTestRequest {
  count: number;                       // required
  difficulty: DifficultySpec;          // required
  sources?: string[];                  // omit = all; [] is an error
  chapters?: string[];                 // omit = all; [] is an error
  seed?: number;                       // omit = server-generated (echoed)
  title?: string;
  test_id?: string;
}

export interface DifficultySpec {
  mode: "single" | "mixed";
  value?: Difficulty;                  // mode: "single"
  counts?: Partial<Record<Difficulty, number>>; // mode: "mixed", sums to count
}

/** POST /tests — legacy shape. Exactly one of the two shapes per body. */
export interface LegacyTestRequest {
  selections: Selection[];             // min length 1
  seed?: number;
  title?: string;
  test_id?: string;
  include_solutions?: boolean;         // default true
}

export type TestRequest = FriendlyTestRequest | LegacyTestRequest;

/** POST /tests/submit */
export interface SubmitRequest {
  request: TestRequest;                // EXACT original body, seed included
  answers?: Record<string, string>;    // question_id => option key
  test_id?: string;
  elapsed_seconds?: number;
}

/** POST /practice */
export interface PracticeRequest {
  count?: number;                      // default 10, >= 1
  page?: number;                       // default 1, >= 1
  seed?: number;                       // echo it for stable pagination
  source?: string;
  chapter?: string;                    // qualified or raw
  topic?: string;
  difficulty?: Difficulty;
  mode?: TestMode;                     // default "progressive"
  include_knowledge?: boolean;         // default true
  title?: string;
  practice_id?: string;
}