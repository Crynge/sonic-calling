import { startTransition, useDeferredValue, useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

type ContactProfile = {
  id: string;
  full_name: string;
  local_hour: number;
  phone: string;
  city: string;
  state: string;
  use_case: string;
  organization: string;
  consent_status: "consented" | "unknown" | "revoked";
  do_not_call: boolean;
  persona: string;
  notes: string;
};

type AgentProfile = {
  id: string;
  name: string;
  vertical: string;
  voice: string;
  goal: string;
  tool_stack: string[];
  notes: string;
};

type DashboardMetric = {
  label: string;
  value: string;
  tone: "primary" | "neutral" | "warning";
};

type PlatformSurface = {
  surface: string;
  purpose: string;
};

type DashboardSummary = {
  repo_name: string;
  narrative: string;
  metrics: DashboardMetric[];
  contacts: ContactProfile[];
  agent_profiles: AgentProfile[];
  provider_defaults: Record<string, string>;
  compliance_rules: string[];
  platform_surfaces: PlatformSurface[];
};

type ComplianceResult = {
  allowed: boolean;
  risk_level: "low" | "medium" | "high" | "blocked";
  reasons: string[];
  missing_requirements: string[];
};

type RealtimeTrace = {
  provider: "openai" | "local";
  model: string;
  event: string;
  confidence: number;
  detail: string;
  used_fallback: boolean;
};

type ConversationTurn = {
  speaker: "agent" | "caller" | "system";
  text: string;
};

type SessionPayload = {
  session_id: string;
  contact: ContactProfile;
  agent_profile: AgentProfile;
  state: "ready" | "live" | "follow_up" | "handoff" | "completed" | "blocked";
  turns: ConversationTurn[];
  compliance: ComplianceResult;
  latest_reply: string;
  latest_disposition: string;
  summary_note: string;
  trace: RealtimeTrace[];
  websocket_path: string;
};

type AgentReply = {
  reply: string;
  next_state: SessionPayload["state"];
  disposition: "continue" | "schedule" | "handoff" | "stop";
  confidence: number;
  tool_suggestion: string;
  trace: RealtimeTrace[];
};

type SessionView = {
  session: SessionPayload;
  agent_reply: AgentReply | null;
};

type SessionPlan = {
  contact: ContactProfile;
  agent_profile: AgentProfile;
  opening_line: string;
  realtime_model: string;
  telephony_mode: string;
  websocket_path: string;
  compliance: ComplianceResult;
  notes: string[];
};

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`GET ${path} failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`POST ${path} failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function formatRiskLabel(risk: ComplianceResult["risk_level"]): string {
  return risk.replace("_", " ");
}

function App() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [activeContactId, setActiveContactId] = useState("contact-001");
  const [activeAgentProfileId, setActiveAgentProfileId] = useState("agent-sales");
  const [sessionPlan, setSessionPlan] = useState<SessionPlan | null>(null);
  const [sessionView, setSessionView] = useState<SessionView | null>(null);
  const [composer, setComposer] = useState("Please schedule me for tomorrow afternoon.");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const deferredComposer = useDeferredValue(composer);

  useEffect(() => {
    void (async () => {
      try {
        const dashboard = await apiGet<DashboardSummary>("/api/dashboard/summary");
        startTransition(() => {
          setSummary(dashboard);
          if (dashboard.contacts[0]) {
            setActiveContactId((current) => current || dashboard.contacts[0].id);
          }
          if (dashboard.agent_profiles[0]) {
            setActiveAgentProfileId((current) => current || dashboard.agent_profiles[0].id);
          }
        });
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : "Unable to load dashboard.");
      }
    })();
  }, []);

  useEffect(() => {
    if (!activeContactId || !activeAgentProfileId) {
      return;
    }

    void (async () => {
      try {
        const plan = await apiPost<SessionPlan>("/api/session-plan", {
          contact_id: activeContactId,
          agent_profile_id: activeAgentProfileId,
        });
        startTransition(() => {
          setSessionPlan(plan);
        });
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : "Unable to load session plan.");
      }
    })();
  }, [activeContactId, activeAgentProfileId]);

  async function launchSimulator(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const session = await apiPost<SessionView>("/api/sessions", {
        contact_id: activeContactId,
        agent_profile_id: activeAgentProfileId,
      });
      startTransition(() => {
        setSessionView(session);
      });
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Unable to start simulator.");
    } finally {
      setLoading(false);
    }
  }

  async function runNextTurn(): Promise<void> {
    if (!sessionView) {
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const nextSession = await apiPost<SessionView>(`/api/sessions/${sessionView.session.session_id}/respond`, {
        caller_text: composer,
      });
      startTransition(() => {
        setSessionView(nextSession);
      });
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Unable to run next turn.");
    } finally {
      setLoading(false);
    }
  }

  const activeContact = summary?.contacts.find((contact) => contact.id === activeContactId) ?? null;
  const activeAgentProfile =
    summary?.agent_profiles.find((profile) => profile.id === activeAgentProfileId) ?? null;
  const liveTrace = sessionView?.agent_reply?.trace ?? sessionView?.session.trace ?? [];
  const compliance = sessionView?.session.compliance ?? sessionPlan?.compliance ?? null;
  const complianceReasons = compliance?.reasons.length
    ? compliance.reasons
    : summary?.compliance_rules ?? [];
  const missingRequirements = compliance?.missing_requirements ?? [];
  const runtimePath = sessionView?.session.websocket_path ?? sessionPlan?.websocket_path ?? "/twilio/media-stream/preview";
  const runtimeDisposition = sessionView?.agent_reply?.disposition ?? sessionView?.session.latest_disposition ?? "continue";
  const planNotes = sessionPlan?.notes ?? [];

  return (
    <div className="shell">
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Realtime telephony platform / OpenAI Realtime / Twilio Media Streams</p>
          <h1>Sonic Calling</h1>
          <p className="hero-body">
            Build production-grade voice agents with a VideoSDK-style developer experience: realtime session
            templates, Twilio stream ingress, compliance guardrails, tool-aware personas, and a polished
            operator console for testing every live turn before you deploy.
          </p>
        </div>

        <div className="hero-actions">
          <button type="button" className="primary-action" onClick={() => void launchSimulator()} disabled={loading}>
            Launch Simulator
          </button>
          <div className="api-badge">
            <span>OpenAI Realtime</span>
            <span>Twilio Voice</span>
            <span>Twilio-ready</span>
          </div>
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      <main className="grid">
        <section className="main-column">
          <section className="panel intro-panel">
            <div className="section-header">
              <span>Platform narrative</span>
              <strong>{summary?.repo_name ?? "loading..."}</strong>
            </div>
            <p>{summary?.narrative ?? "Loading realtime platform summary..."}</p>
            <div className="metrics-grid">
              {summary?.metrics.map((metric) => (
                <article key={metric.label} className={`metric-card metric-${metric.tone}`}>
                  <span>{metric.label}</span>
                  <strong>{metric.value}</strong>
                </article>
              ))}
            </div>
          </section>

          <section className="panel">
            <div className="section-header">
              <span>Contact workspace</span>
              <strong>{activeContact?.full_name ?? "Choose a contact"}</strong>
            </div>
            <div className="contact-grid">
              {summary?.contacts.map((contact) => (
                <button
                  type="button"
                  key={contact.id}
                  className={`contact-card ${contact.id === activeContactId ? "contact-card-active" : ""}`}
                  onClick={() => setActiveContactId(contact.id)}
                >
                  <span className="contact-status">
                    {contact.do_not_call ? "Blocked contact" : `${contact.city}, ${contact.state}`}
                  </span>
                  <strong>{contact.full_name}</strong>
                  <p>{contact.use_case}</p>
                  <small>{contact.organization}</small>
                </button>
              ))}
            </div>
          </section>

          <section className="panel">
            <div className="section-header">
              <span>Agent personas</span>
              <strong>{activeAgentProfile?.name ?? "Choose an agent"}</strong>
            </div>
            <div className="agent-grid">
              {summary?.agent_profiles.map((profile) => (
                <button
                  type="button"
                  key={profile.id}
                  className={`agent-card ${profile.id === activeAgentProfileId ? "agent-card-active" : ""}`}
                  onClick={() => setActiveAgentProfileId(profile.id)}
                >
                  <div className="agent-topline">
                    <strong>{profile.name}</strong>
                    <span>{profile.voice}</span>
                  </div>
                  <p>{profile.vertical}</p>
                  <small>{profile.goal}</small>
                </button>
              ))}
            </div>
          </section>

          <section className="panel simulator-panel">
            <div className="section-header">
              <span>Realtime simulator</span>
              <strong>{sessionView ? sessionView.session.state : "ready"}</strong>
            </div>

            <div className="sim-layout">
              <div className="transcript-card">
                <h2>Conversation stream</h2>
                <div className="transcript-feed">
                  {sessionView?.session.turns.length ? (
                    sessionView.session.turns.map((turn, index) => (
                      <article key={`${turn.speaker}-${index}`} className={`bubble bubble-${turn.speaker}`}>
                        <span>{turn.speaker}</span>
                        <p>{turn.text}</p>
                      </article>
                    ))
                  ) : (
                    <div className="empty-state">
                      Launch the simulator to generate the disclosure opener, inspect the Twilio-ready session path,
                      and test live turn handling before you connect a real phone number.
                    </div>
                  )}
                </div>
              </div>

              <div className="sim-actions">
                <h2>Caller utterance</h2>
                <textarea
                  value={composer}
                  onChange={(event) => setComposer(event.target.value)}
                  placeholder="Type the caller response here..."
                />
                <button
                  type="button"
                  className="secondary-action"
                  onClick={() => void runNextTurn()}
                  disabled={!sessionView || loading}
                >
                  Run Next Turn
                </button>

                <div className="hint-box">
                  <span>Deferred preview</span>
                  <p>{deferredComposer}</p>
                </div>

                <div className="runtime-card">
                  <span>Runtime wire</span>
                  <strong>{runtimePath}</strong>
                  <small>{runtimeDisposition}</small>
                </div>
              </div>
            </div>
          </section>
        </section>

        <aside className="rail">
          <section className="panel">
            <div className="section-header">
              <span>Session plan</span>
              <strong>{sessionPlan?.telephony_mode ?? "loading..."}</strong>
            </div>
            <p className="plan-line">{sessionPlan?.opening_line ?? "Loading opening line..."}</p>
            <ul className="plan-list">
              {planNotes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </section>

          <section className="panel">
            <div className="section-header">
              <span>Realtime trace</span>
              <strong>{liveTrace.length ? "Live turn events" : "Awaiting session"}</strong>
            </div>
            <div className="trace-list">
              {liveTrace.length ? (
                liveTrace.map((trace, index) => (
                  <article key={`${trace.provider}-${trace.event}-${index}`} className="trace-card">
                    <div className="trace-topline">
                      <strong>{trace.provider === "openai" ? "OpenAI Realtime" : "Local policy engine"}</strong>
                      <span>{Math.round(trace.confidence * 100)}%</span>
                    </div>
                    <p>{trace.model}</p>
                    <small>{trace.event}</small>
                    <small>{trace.detail}</small>
                  </article>
                ))
              ) : (
                <article className="trace-card">
                  <div className="trace-topline">
                    <strong>Twilio-ready bridge</strong>
                    <span>Idle</span>
                  </div>
                  <p>{sessionPlan?.realtime_model ?? "gpt-realtime"}</p>
                  <small>Waiting for the first caller utterance to create a live model trace.</small>
                </article>
              )}
            </div>
          </section>

          <section className="panel">
            <div className="section-header">
              <span>Compliance watch</span>
              <strong>{compliance ? formatRiskLabel(compliance.risk_level) : "loading..."}</strong>
            </div>
            <div className="compliance-stack">
              <div className={`risk-pill risk-${compliance?.risk_level ?? "low"}`}>
                {compliance?.allowed === false ? "Blocked" : "Allowed"}
              </div>
              <ul>
                {complianceReasons.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              {missingRequirements.length ? (
                <>
                  <h3>Missing requirements</h3>
                  <ul>
                    {missingRequirements.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </>
              ) : null}
            </div>
          </section>

          <section className="panel">
            <div className="section-header">
              <span>Contact brief</span>
              <strong>{activeContact?.organization ?? "n/a"}</strong>
            </div>
            <div className="brief-stack">
              <p>
                <strong>Use case:</strong> {activeContact?.use_case}
              </p>
              <p>
                <strong>Persona:</strong> {activeContact?.persona}
              </p>
              <p>
                <strong>Consent:</strong> {activeContact?.consent_status}
              </p>
              <p>
                <strong>Local hour:</strong> {activeContact?.local_hour ?? "--"}:00
              </p>
              <p>
                <strong>Notes:</strong> {activeContact?.notes}
              </p>
            </div>
          </section>

          <section className="panel">
            <div className="section-header">
              <span>Agent tooling</span>
              <strong>{activeAgentProfile?.voice ?? "voice"}</strong>
            </div>
            <div className="tool-stack">
              {(activeAgentProfile?.tool_stack ?? []).map((toolName) => (
                <span key={toolName}>{toolName}</span>
              ))}
            </div>
            <p className="agent-note">{activeAgentProfile?.notes}</p>
          </section>

          <section className="panel">
            <div className="section-header">
              <span>Platform surfaces</span>
              <strong>Developer map</strong>
            </div>
            <div className="surface-list">
              {summary?.platform_surfaces.map((surface) => (
                <article key={surface.surface} className="surface-card">
                  <strong>{surface.surface}</strong>
                  <p>{surface.purpose}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="panel">
            <div className="section-header">
              <span>Runtime defaults</span>
              <strong>Wire settings</strong>
            </div>
            <div className="defaults-list">
              {Object.entries(summary?.provider_defaults ?? {}).map(([key, value]) => (
                <div key={key} className="default-row">
                  <span>{key}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
          </section>
        </aside>
      </main>
    </div>
  );
}

export default App;
