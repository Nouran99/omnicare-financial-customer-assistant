import type { ChatResponse } from "../lib/api";

type ToolCall = ChatResponse["tool_calls"][number];

interface CitationListProps {
  sources: string[];
}

interface ToolCallCardsProps {
  toolCalls: ChatResponse["tool_calls"];
}

export function CitationList({ sources }: CitationListProps) {
  if (sources.length === 0) {
    return null;
  }

  return (
    <section className="message-metadata-section" aria-label="Policy sources">
      <h3 className="metadata-heading">Sources</h3>
      <ul className="citation-list">
        {sources.map((source) => (
          <li key={source} className="citation-item">
            <span aria-hidden="true">↳</span>
            <span>{source}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function toolStatus(toolCall: ToolCall): { label: string; tone: string } {
  if (toolCall.status === "success") {
    return { label: "Completed", tone: "success" };
  }
  if (toolCall.status === "failure") {
    return { label: "Not completed", tone: "failure" };
  }
  return { label: "No result", tone: "neutral" };
}

export function ToolCallCards({ toolCalls }: ToolCallCardsProps) {
  if (toolCalls.length === 0) {
    return null;
  }

  return (
    <section className="message-metadata-section" aria-label="Tool activity">
      <h3 className="metadata-heading">Tool activity</h3>
      <div className="tool-card-list">
        {toolCalls.map((toolCall, index) => {
          const status = toolStatus(toolCall);
          return (
            <article
              key={`${toolCall.name}-${toolCall.status}-${index}`}
              className={`tool-card tool-card-${status.tone}`}
              data-status={status.tone}
            >
              <div className="tool-card-header">
                <code>{toolCall.name}</code>
                <span className="tool-status">
                  <span className="status-marker" aria-hidden="true" />
                  {status.label}
                </span>
              </div>
              {toolCall.result_summary ? (
                <p className="tool-result-summary">{toolCall.result_summary}</p>
              ) : (
                <p className="tool-result-summary">No public result summary was returned.</p>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function AssistantMessageMetadata({
  sources,
  toolCalls,
}: CitationListProps & ToolCallCardsProps) {
  if (sources.length === 0 && toolCalls.length === 0) {
    return null;
  }

  return (
    <div className="assistant-message-metadata">
      <CitationList sources={sources} />
      <ToolCallCards toolCalls={toolCalls} />
    </div>
  );
}
