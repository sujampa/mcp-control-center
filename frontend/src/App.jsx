import { useEffect, useState } from "react";
import {
  Activity,
  ArrowRight,
  Boxes,
  Braces,
  Check,
  CheckCircle2,
  CircleAlert,
  Clock3,
  Code2,
  LoaderCircle,
  Play,
  RefreshCw,
  Server,
  Terminal,
  Wrench,
  XCircle,
} from "lucide-react";

import "./App.css";

const API_URL = "http://127.0.0.1:8000";

const TOOLS = [
  {
    name: "calculate_total",
    description: "Calculate the total cost of a product order.",
    input: {
      quantity: "integer",
      unit_price: "number",
    },
    example:
      "Calculate the cost of 15 keyboards at 250 rupees each.",
  },
  {
    name: "check_stock",
    description: "Check whether available stock meets a requested quantity.",
    input: {
      product_name: "string",
      available_stock: "integer",
      requested_quantity: "integer",
    },
    example:
      "We have 20 keyboards and need 5. Is the stock sufficient?",
  },
];

function StatusDot({ online }) {
  return (
    <span
      className={`status-dot ${online ? "online" : "offline"}`}
      aria-label={online ? "Online" : "Offline"}
    />
  );
}

function JsonViewer({ value }) {
  return (
    <pre className="json-viewer">
      <code>
        {typeof value === "string"
          ? value
          : JSON.stringify(value, null, 2)}
      </code>
    </pre>
  );
}

function formatStage(stage) {
  return stage
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatDuration(duration) {
  if (duration === null || duration === undefined) {
    return null;
  }

  const milliseconds = Number(duration);

  return Number.isFinite(milliseconds)
    ? `${milliseconds.toFixed(2)} ms`
    : null;
}

function App() {
  const [serverOnline, setServerOnline] = useState(false);
  const [checkingServer, setCheckingServer] = useState(true);

  const [question, setQuestion] = useState(
    "Calculate the cost of 15 keyboards at 250 rupees each."
  );

  const [selectedTool, setSelectedTool] = useState("calculate_total");

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [history, setHistory] = useState([]);

  async function checkHealth() {
    setCheckingServer(true);

    try {
      const response = await fetch(`${API_URL}/health`);

      if (!response.ok) {
        throw new Error("Backend health check failed");
      }

      const data = await response.json();

      setServerOnline(data.status === "healthy");
    } catch {
      setServerOnline(false);
    } finally {
      setCheckingServer(false);
    }
  }

  useEffect(() => {
    checkHealth();

    const interval = setInterval(checkHealth, 15000);

    return () => clearInterval(interval);
  }, []);

  async function executeRequest(event) {
    event?.preventDefault();

    if (!question.trim() || loading) {
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    const startedAt = performance.now();
    const requestQuestion = question.trim();

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: requestQuestion,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : `Request failed with HTTP ${response.status}`
        );
      }

      const frontendDuration = performance.now() - startedAt;

      const execution = {
        id: `${Date.now()}`,
        question: requestQuestion,
        answer: data.answer || "No answer was returned.",
        toolUsed: data.tool_used || null,
        toolArguments: data.tool_arguments ?? null,
        toolResult: data.tool_result ?? null,
        toolDuration: data.tool_duration_ms ?? null,
        trace: Array.isArray(data.trace) ? data.trace : [],
        status: data.status || "success",
        duration:
          data.total_duration_ms ?? frontendDuration,
        frontendDuration,
        timestamp: new Date().toLocaleTimeString(),
        success: data.status !== "error",
      };

      setResult(execution);

      setHistory((previous) => [execution, ...previous].slice(0, 8));

      if (data.tool_used) {
        setSelectedTool(data.tool_used);
      }
    } catch (err) {
      const message =
        err.message ||
        "Could not connect to the backend. Check that FastAPI is running.";

      setError(message);

      const failedExecution = {
        id: `${Date.now()}`,
        question: requestQuestion,
        answer: message,
        toolUsed: null,
        duration: performance.now() - startedAt,
        timestamp: new Date().toLocaleTimeString(),
        success: false,
      };

      setHistory((previous) =>
        [failedExecution, ...previous].slice(0, 8)
      );
    } finally {
      setLoading(false);
    }
  }

  function chooseTool(tool) {
    setSelectedTool(tool.name);
    setQuestion(tool.example);
    setResult(null);
    setError("");
  }

  const activeTool = TOOLS.find(
    (tool) => tool.name === selectedTool
  );

  return (
    <div className="mcp-app">
      {/* Header */}
      <header className="top-header">
        <div className="brand">
          <div className="brand-mark">
            <Boxes size={22} />
          </div>

          <div>
            <div className="brand-name">
              MCP<span>Control</span>
            </div>

            <div className="brand-caption">
              MODEL CONTEXT PROTOCOL PLAYGROUND
            </div>
          </div>
        </div>

        <div className="header-right">
          <div className="connection-status">
            <StatusDot online={serverOnline} />

            <span>
              {checkingServer
                ? "Checking server"
                : serverOnline
                  ? "Backend connected"
                  : "Backend offline"}
            </span>
          </div>

          <button
            className="icon-button"
            onClick={checkHealth}
            title="Refresh backend status"
            aria-label="Refresh backend status"
          >
            <RefreshCw size={16} />
          </button>

          <div className="version-label">MCP DEMO</div>
        </div>
      </header>

      {/* Workspace */}
      <main className="workspace">
        <aside className="left-panel">
          <div className="panel-heading">
            <span>SERVER OVERVIEW</span>
            <Server size={15} />
          </div>

          <section className="server-card">
            <div className="server-card-top">
              <div className="server-icon">
                <Terminal size={21} />
              </div>

              <StatusDot online={serverOnline} />
            </div>

            <h2>MCP Business Server</h2>

            <p>
              Exposes business functions as callable MCP tools.
            </p>

            <div className="server-meta">
              <span>Transport</span>
              <strong>STDIO</strong>
            </div>

            <div className="server-meta">
              <span>Runtime</span>
              <strong>Python</strong>
            </div>

            <div className="server-meta">
              <span>AI model</span>
              <strong>Llama 3.2</strong>
            </div>
          </section>

          <div className="panel-heading tools-heading">
            <span>AVAILABLE TOOLS</span>
            <span className="count-badge">{TOOLS.length}</span>
          </div>

          <div className="tool-list">
            {TOOLS.map((tool) => (
              <button
                key={tool.name}
                className={`tool-item ${
                  selectedTool === tool.name ? "selected" : ""
                }`}
                onClick={() => chooseTool(tool)}
              >
                <div className="tool-item-icon">
                  <Wrench size={17} />
                </div>

                <div className="tool-item-content">
                  <strong>{tool.name}</strong>
                  <span>{tool.description}</span>
                </div>

                {selectedTool === tool.name && (
                  <span className="selected-indicator" />
                )}
              </button>
            ))}
          </div>

          <div className="sidebar-footer">
            <div className="footer-icon">
              <Activity size={16} />
            </div>

            <div>
              <strong>Local execution</strong>
              <p>Requests processed by your local stack.</p>
            </div>
          </div>
        </aside>

        <section className="main-panel">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span className="eyebrow-square" />
                DEVELOPER WORKSPACE
              </div>

              <h1>MCP Execution Playground</h1>

              <p>
                Submit a request and inspect its actual MCP execution.
              </p>
            </div>

            <div className="environment-badge">
              <span className="environment-dot" />
              LOCAL ENVIRONMENT
            </div>
          </div>

          {/* Request editor */}
          <section className="section-card request-card">
            <div className="section-title">
              <div className="section-title-left">
                <div className="section-icon">
                  <Code2 size={17} />
                </div>

                <div>
                  <h2>Request editor</h2>
                  <p>Enter a natural-language business request.</p>
                </div>
              </div>

              <span className="method-badge">POST /chat</span>
            </div>

            <form onSubmit={executeRequest}>
              <label className="input-label" htmlFor="request">
                REQUEST
              </label>

              <textarea
                id="request"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Describe the business operation..."
                maxLength={2000}
                rows={3}
                disabled={loading}
              />

              <div className="request-footer">
                <span>{question.length} / 2000 characters</span>

                <button
                  className="execute-button"
                  type="submit"
                  disabled={loading || !question.trim()}
                >
                  {loading ? (
                    <LoaderCircle className="spin" size={17} />
                  ) : (
                    <Play size={16} />
                  )}

                  {loading ? "Executing..." : "Execute request"}

                  {!loading && <ArrowRight size={16} />}
                </button>
              </div>
            </form>

            <div className="example-row">
              <span>EXAMPLES</span>

              {TOOLS.map((tool) => (
                <button
                  key={tool.name}
                  className="example-chip"
                  onClick={() => chooseTool(tool)}
                  disabled={loading}
                >
                  {tool.name}
                </button>
              ))}
            </div>
          </section>

          {/* Tool definition */}
          <section className="section-card definition-card">
            <div className="section-title">
              <div className="section-title-left">
                <div className="section-icon">
                  <Braces size={17} />
                </div>

                <div>
                  <h2>Tool definition</h2>
                  <p>Selected MCP tool and expected parameters.</p>
                </div>
              </div>

              <span className="type-badge">TOOL SCHEMA</span>
            </div>

            <div className="definition-content">
              <div className="definition-name">
                <div>
                  <span className="muted-label">TOOL NAME</span>
                  <h3>{activeTool?.name}</h3>
                </div>

                <span className="function-badge">function</span>
              </div>

              <p className="definition-description">
                {activeTool?.description}
              </p>

              <div className="parameter-heading">
                <span>INPUT PARAMETERS</span>

                <span>
                  {Object.keys(activeTool?.input || {}).length} parameters
                </span>
              </div>

              <div className="parameter-list">
                {Object.entries(activeTool?.input || {}).map(
                  ([name, type]) => (
                    <div className="parameter-row" key={name}>
                      <span className="parameter-name">{name}</span>
                      <span className="parameter-type">{type}</span>

                      <span className="parameter-required">
                        required
                      </span>
                    </div>
                  )
                )}
              </div>
            </div>
          </section>

          {/* Results */}
          <div className="results-grid">
            {/* Execution result */}
            <section className="section-card result-panel">
              <div className="section-title">
                <div className="section-title-left">
                  <div className="section-icon">
                    <Activity size={17} />
                  </div>

                  <div>
                    <h2>Execution result</h2>
                    <p>Actual response returned by FastAPI.</p>
                  </div>
                </div>

                {result && (
                  <span
                    className={
                      result.success
                        ? "success-badge"
                        : "error-badge"
                    }
                  >
                    {result.success ? (
                      <Check size={12} />
                    ) : (
                      <XCircle size={12} />
                    )}

                    {result.success ? "SUCCESS" : "FAILED"}
                  </span>
                )}
              </div>

              {loading ? (
                <div className="empty-state">
                  <LoaderCircle className="spin" size={25} />
                  <strong>Waiting for response</strong>
                  <span>
                    The backend is processing your request.
                  </span>
                </div>
              ) : error ? (
                <div className="error-state">
                  <CircleAlert size={22} />
                  <strong>Request failed</strong>
                  <p>{error}</p>
                </div>
              ) : result ? (
                <div className="response-content">
                  <div className="response-meta">
                    <span>
                      <CheckCircle2 size={14} />
                      Backend response received
                    </span>

                    <span>
                      <Clock3 size={14} />
                      {formatDuration(result.duration)}
                    </span>
                  </div>

                  <div className="response-answer">
                    <span className="muted-label">ANSWER</span>
                    <p>{result.answer}</p>
                  </div>

                  <div className="response-meta tool-result-meta">
                    <span>Selected MCP tool</span>
                    <strong>
                      {result.toolUsed || "No tool executed"}
                    </strong>
                  </div>

                  {result.toolArguments !== null && (
                    <div className="response-answer">
                      <span className="muted-label">
                        VALIDATED TOOL ARGUMENTS
                      </span>

                      <JsonViewer value={result.toolArguments} />
                    </div>
                  )}

                  {result.toolResult !== null && (
                    <div className="response-answer">
                      <span className="muted-label">
                        ACTUAL MCP TOOL RESULT
                      </span>

                      <JsonViewer value={result.toolResult} />
                    </div>
                  )}

                  {result.toolDuration !== null && (
                    <div className="response-meta">
                      <span>Tool execution time</span>
                      <strong>
                        {formatDuration(result.toolDuration)}
                      </strong>
                    </div>
                  )}
                </div>
              ) : (
                <div className="empty-state">
                  <Terminal size={25} />
                  <strong>No execution yet</strong>
                  <span>
                    Submit a request to see its response here.
                  </span>
                </div>
              )}
            </section>

            {/* Actual execution trace */}
            <section className="section-card trace-panel">
              <div className="section-title">
                <div className="section-title-left">
                  <div className="section-icon">
                    <Activity size={17} />
                  </div>

                  <div>
                    <h2>Execution trace</h2>
                    <p>Actual events recorded by the backend.</p>
                  </div>
                </div>

                {result && (
                  <span className="count-badge">
                    {result.trace?.length || 0} events
                  </span>
                )}
              </div>

              {loading && (
                <div className="empty-state">
                  <LoaderCircle className="spin" size={25} />
                  <strong>Executing request</strong>
                  <span>
                    Waiting for the recorded execution events.
                  </span>
                </div>
              )}

              {!loading && !result && !error && (
                <div className="empty-state trace-empty">
                  <Activity size={25} />
                  <strong>Ready for execution</strong>
                  <span>
                    The actual execution events will appear here.
                  </span>
                </div>
              )}

              {result && result.trace?.length > 0 && (
                <div className="trace-list">
                  {result.trace.map((event, index) => (
                    <div
                      className="trace-row"
                      key={`${event.stage}-${index}`}
                    >
                      <span className="trace-number">
                        {String(index + 1).padStart(2, "0")}
                      </span>

                      <div className="trace-event-content">
                        <strong>{formatStage(event.stage)}</strong>
                        <p>{event.message}</p>

                        {event.details && (
                          <details className="trace-details">
                            <summary>View event details</summary>
                            <JsonViewer value={event.details} />
                          </details>
                        )}

                        {event.duration_ms != null && (
                          <span className="trace-duration">
                            {formatDuration(event.duration_ms)}
                          </span>
                        )}
                      </div>

                      {event.status === "success" ? (
                        <CheckCircle2
                          className="trace-success"
                          size={16}
                          aria-label="Success"
                        />
                      ) : event.status === "error" ? (
                        <XCircle
                          className="trace-failure"
                          size={16}
                          aria-label="Error"
                        />
                      ) : (
                        <Clock3
                          className="trace-pending"
                          size={16}
                          aria-label={event.status}
                        />
                      )}
                    </div>
                  ))}
                </div>
              )}

              {result && (!result.trace || result.trace.length === 0) && (
                <div className="empty-state">
                  <CircleAlert size={22} />
                  <strong>No trace events returned</strong>
                  <span>
                    Check the FastAPI response and backend logs.
                  </span>
                </div>
              )}

              {error && (
                <div className="error-state trace-error">
                  <XCircle size={22} />
                  <strong>Execution failed</strong>
                  <p>{error}</p>
                </div>
              )}

              <div className="trace-disclaimer">
                <CircleAlert size={14} />
                Events reflect data returned by the backend. They appear
                after the request completes; this is not live streaming.
              </div>
            </section>
          </div>

          {/* Recent executions */}
          <section className="section-card history-panel">
            <div className="section-title">
              <div className="section-title-left">
                <div className="section-icon">
                  <Clock3 size={17} />
                </div>

                <div>
                  <h2>Recent executions</h2>
                  <p>Requests made during this browser session.</p>
                </div>
              </div>

              <span className="count-badge">{history.length}</span>
            </div>

            {history.length === 0 ? (
              <div className="history-empty">
                No executions recorded yet.
              </div>
            ) : (
              <div className="history-table-wrapper">
                <table className="history-table">
                  <thead>
                    <tr>
                      <th>STATUS</th>
                      <th>REQUEST</th>
                      <th>TOOL</th>
                      <th>DURATION</th>
                      <th>TIME</th>
                    </tr>
                  </thead>

                  <tbody>
                    {history.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <span
                            className={`history-status ${
                              item.success ? "passed" : "failed"
                            }`}
                          >
                            {item.success ? (
                              <CheckCircle2 size={13} />
                            ) : (
                              <XCircle size={13} />
                            )}

                            {item.success ? "Success" : "Failed"}
                          </span>
                        </td>

                        <td className="history-question">
                          {item.question}
                        </td>

                        <td>
                          <code>{item.toolUsed || "—"}</code>
                        </td>

                        <td>{formatDuration(item.duration) || "—"}</td>

                        <td>{item.timestamp}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <footer className="workspace-footer">
            <span>MCP CONTROL CENTER</span>
            <span>
              React · FastAPI · Ollama · MCP Python SDK
            </span>
          </footer>
        </section>
      </main>
    </div>
  );
}

export default App;