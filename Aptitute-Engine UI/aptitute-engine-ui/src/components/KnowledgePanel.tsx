import type { KnowledgeTerms } from "../types/qme";

interface KnowledgePanelProps {
  topicKnowledge: Record<string, KnowledgeTerms>;
  chapterFormulaSummary: string[];
}

export function KnowledgePanel({
  topicKnowledge,
  chapterFormulaSummary,
}: KnowledgePanelProps) {
  if (
    Object.keys(topicKnowledge).length === 0 &&
    chapterFormulaSummary.length === 0
  ) {
    return null;
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-medium text-gray-900 mb-4">
        Formulas &amp; Shortcuts
      </h3>
      {chapterFormulaSummary.length > 0 && (
        <>
          <h4 className="text-md font-semibold text-gray-700 mb-2">
            Chapter Summary
          </h4>
          <ul className="list-disc pl-5 space-y-1 text-sm text-gray-700">
            {chapterFormulaSummary.map((line, idx) => (
              <li key={idx}>{line}</li>
            ))}
          </ul>
        </>
      )}

      {Object.keys(topicKnowledge).length > 0 && (
        <>
          <h4 className="text-md font-semibold text-gray-700 mb-4 mt-6">
            By Topic
          </h4>
          <div className="space-y-4">
            {Object.entries(topicKnowledge).map(([topic, terms]) => (
              <div key={topic} className="border-t pt-4">
                <h5 className="text-sm font-medium text-gray-700 mb-2">
                  {topic}
                </h5>
                {terms.formulas.length > 0 && (
                  <>
                    <p className="mb-1">
                      <span className="font-medium">Formulas:</span>
                    </p>
                    <ul className="list-disc pl-5 space-y-1 text-sm text-gray-700">
                      {terms.formulas.map((f, idx) => (
                        <li key={idx}>{f}</li>
                      ))}
                    </ul>
                  </>
                )}
                {terms.short_tricks.length > 0 && (
                  <>
                    <p className="mb-1">
                      <span className="font-medium">Shortcuts:</span>
                    </p>
                    <ul className="list-disc pl-5 space-y-1 text-sm text-gray-700">
                      {terms.short_tricks.map((s, idx) => (
                        <li key={idx}>{s}</li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}