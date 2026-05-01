import { startTransition, useDeferredValue, useEffect, useState } from "react";

function resolveApiBase(): string {
  const params = new URLSearchParams(window.location.search);
  return params.get("apiBase") ?? import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
}

const API_BASE = resolveApiBase();

type ProviderSurface = "realtime" | "telephony" | "tooling" | "analytics";
type ProviderName = "openai" | "gemini" | "twilio" | "custom" | "local";
type ToolKind = "crm" | "calendar" | "sms" | "webhook" | "handoff" | "lookup";
type ToolExecutionStatus = "simulated" | "completed" | "skipped" | "error";

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

type PlatformSurfaceCard = {
  surface: string;
  purpose: string;
};

type RuntimeHealth = {
  openai_api_configured: boolean;
  twilio_credentials_configured: boolean;
  live_bridge_enabled: boolean;
  client_secret_enabled: boolean;
  public_base_url: string;
  public_websocket_base: string;
  openai_websocket_url: string;
  input_audio_format: string;
  output_audio_format: string;
  transcription_model: string;
  turn_detection_mode: string;
  active_realtime_profile: string | null;
  active_telephony_profile: string | null;
  tool_integrations_enabled: number;
  byo_realtime_ready: boolean;
};

type DashboardSummary = {
  repo_name: string;
  narrative: string;
  metrics: DashboardMetric[];
  contacts: ContactProfile[];
  agent_profiles: AgentProfile[];
  provider_defaults: Record<string, string>;
  compliance_rules: string[];
  platform_surfaces: PlatformSurfaceCard[];
  runtime_health: RuntimeHealth;
};

type ComplianceResult = {
  allowed: boolean;
  risk_level: "low" | "medium" | "high" | "blocked";
  reasons: string[];
  missing_requirements: string[];
};

type RealtimeTrace = {
  provider: ProviderName;
  model: string;
  event: string;
  confidence: number;
  detail: string;
  used_fallback: boolean;
};

type StreamEvent = {
  source: "twilio" | "openai" | "system" | "tool";
  event: string;
  detail: string;
  timestamp: string;
  payload_preview: Record<string, unknown>;
};

type ToolExecutionRecord = {
  execution_id: string;
  tool_id: string;
  tool_name: string;
  status: ToolExecutionStatus;
  reason: string;
  session_id: string | null;
  timestamp: string;
  input_payload: Record<string, unknown>;
  output_payload: Record<string, unknown>;
};

type ProviderProfile = {
  profile_id: string;
  name: string;
  provider: ProviderName;
  surface: ProviderSurface;
  active: boolean;
  ready: boolean;
  auth_source: "environment" | "vault" | "unset";
  masked_secret: string | null;
  account_label: string | null;
  model: string | null;
  endpoint: string | null;
  notes: string;
  readiness_notes: string[];
  metadata: Record<string, string>;
};

type ToolIntegration = {
  tool_id: string;
  name: string;
  kind: ToolKind;
  description: string;
  enabled: boolean;
  requires_network: boolean;
  mapped_functions: string[];
  endpoint_url: string | null;
  http_method: "GET" | "POST";
  auth_profile_id: string | null;
  static_headers: Record<string, string>;
  expected_fields: string[];
  simulator_response: string;
  last_result_summary: string;
};

type RuntimeConfigurationView = {
  provider_profiles: ProviderProfile[];
  tool_integrations: ToolIntegration[];
  active_realtime_profile_id: string | null;
  active_telephony_profile_id: string | null;
};

type SessionRuntime = {
  bridge_mode: "simulated" | "openai_realtime";
  bridge_status: "idle" | "connecting" | "streaming" | "closed" | "error";
  input_audio_format: string;
  output_audio_format: string;
  stream_sid: string | null;
  call_sid: string | null;
  openai_response_id: string | null;
  twilio_event_count: number;
  openai_event_count: number;
  latest_mark: string | null;
  last_input_transcript: string;
  last_output_transcript: string;
  last_tool_name: string | null;
  last_tool_arguments: string | null;
  last_tool_status: ToolExecutionStatus | null;
  last_tool_result: string | null;
  tool_execution_count: number;
  provider_profile_id: string | null;
  telephony_profile_id: string | null;
  last_error: string | null;
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
  created_at: string;
  turns: ConversationTurn[];
  compliance: ComplianceResult;
  latest_reply: string;
  latest_disposition: string;
  summary_note: string;
  trace: RealtimeTrace[];
  websocket_path: string;
  runtime: SessionRuntime;
  events: StreamEvent[];
  tool_executions: ToolExecutionRecord[];
  provider_profile_id: string | null;
  telephony_profile_id: string | null;
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

type SessionCollectionView = {
  sessions: SessionPayload[];
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

type ClientSecretResponse = {
  enabled: boolean;
  session_id: string;
  session: Record<string, unknown>;
  client_secret: {
    value: string;
    expires_at: number;
  } | null;
  preview_reason: string | null;
};

type ProviderFormState = {
  name: string;
  provider: ProviderName;
  surface: ProviderSurface;
  api_key: string;
  account_sid: string;
  auth_token: string;
  from_number: string;
  model: string;
  endpoint: string;
  notes: string;
};

type ToolFormState = {
  name: string;
  kind: ToolKind;
  description: string;
  mapped_functions: string;
  endpoint_url: string;
  auth_profile_id: string;
  simulator_response: string;
};

const defaultProviderForm: ProviderFormState = {
  name: "",
  provider: "openai",
  surface: "realtime",
  api_key: "",
  account_sid: "",
  auth_token: "",
  from_number: "",
  model: "gpt-realtime",
  endpoint: "https://api.openai.com/v1/realtime",
  notes: "",
};

const defaultToolForm: ToolFormState = {
  name: "",
  kind: "webhook",
  description: "",
  mapped_functions: "post_custom_webhook",
  endpoint_url: "",
  auth_profile_id: "",
  simulator_response: "Diagnostic run completed in simulator mode.",
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

function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "n/a";
  }
  return new Date(value).toLocaleString();
}

function App() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [runtimeConfig, setRuntimeConfig] = useState<RuntimeConfigurationView | null>(null);
  const [toolHistory, setToolHistory] = useState<ToolExecutionRecord[]>([]);
  const [sessionLedger, setSessionLedger] = useState<SessionPayload[]>([]);
  const [activeContactId, setActiveContactId] = useState("contact-001");
  const [activeAgentProfileId, setActiveAgentProfileId] = useState("agent-sales");
  const [sessionPlan, setSessionPlan] = useState<SessionPlan | null>(null);
  const [sessionView, setSessionView] = useState<SessionView | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [clientSecretResult, setClientSecretResult] = useState<ClientSecretResponse | null>(null);
  const [composer, setComposer] = useState("Please schedule me for tomorrow afternoon.");
  const [providerForm, setProviderForm] = useState<ProviderFormState>(defaultProviderForm);
  const [toolForm, setToolForm] = useState<ToolFormState>(defaultToolForm);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const deferredComposer = useDeferredValue(composer);

  const activeRealtimeProfileId = runtimeConfig?.active_realtime_profile_id ?? null;
  const activeTelephonyProfileId = runtimeConfig?.active_telephony_profile_id ?? null;

  const refreshDashboard = async (): Promise<void> => {
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
  };

  const refreshRuntimeConfig = async (): Promise<void> => {
    const payload = await apiGet<RuntimeConfigurationView>("/api/runtime/config");
    startTransition(() => {
      setRuntimeConfig(payload);
    });
  };

  const refreshToolHistory = async (): Promise<void> => {
    const payload = await apiGet<ToolExecutionRecord[]>("/api/tools/executions");
    startTransition(() => {
      setToolHistory(payload);
    });
  };

  const refreshSessions = async (): Promise<void> => {
    const payload = await apiGet<SessionCollectionView>("/api/sessions");
    startTransition(() => {
      setSessionLedger(payload.sessions);
    });
  };

  useEffect(() => {
    void Promise.all([refreshDashboard(), refreshRuntimeConfig(), refreshToolHistory(), refreshSessions()]).catch(
      (fetchError) => {
        setError(fetchError instanceof Error ? fetchError.message : "Unable to load dashboard.");
      },
    );
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
          provider_profile_id: activeRealtimeProfileId,
          telephony_profile_id: activeTelephonyProfileId,
        });
        startTransition(() => {
          setSessionPlan(plan);
        });
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : "Unable to load session plan.");
      }
    })();
  }, [activeAgentProfileId, activeContactId, activeRealtimeProfileId, activeTelephonyProfileId]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void Promise.all([refreshSessions(), refreshToolHistory()]).catch(() => undefined);
    }, 3500);
    return () => window.clearInterval(interval);
  }, []);

  async function launchSimulator(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const session = await apiPost<SessionView>("/api/sessions", {
        contact_id: activeContactId,
        agent_profile_id: activeAgentProfileId,
        provider_profile_id: activeRealtimeProfileId,
        telephony_profile_id: activeTelephonyProfileId,
      });
      startTransition(() => {
        setSessionView(session);
        setSelectedSessionId(session.session.session_id);
      });
      await Promise.all([refreshSessions(), refreshToolHistory()]);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Unable to start simulator.");
    } finally {
      setLoading(false);
    }
  }

  async function mintClientSecret(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      const payload = await apiPost<ClientSecretResponse>("/api/realtime/client-secret", {
        contact_id: activeContactId,
        agent_profile_id: activeAgentProfileId,
        provider_profile_id: activeRealtimeProfileId,
        telephony_profile_id: activeTelephonyProfileId,
      });
      startTransition(() => {
        setClientSecretResult(payload);
        setSelectedSessionId(payload.session_id);
      });
      await refreshSessions();
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Unable to mint client secret.");
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
        setSelectedSessionId(nextSession.session.session_id);
      });
      await Promise.all([refreshSessions(), refreshToolHistory()]);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Unable to run next turn.");
    } finally {
      setLoading(false);
    }
  }

  async function activateProvider(surface: ProviderSurface, profileId: string): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      await apiPost<ProviderProfile>(`/api/runtime/providers/${surface}/select`, { profile_id: profileId });
      await Promise.all([refreshRuntimeConfig(), refreshDashboard()]);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Unable to activate provider profile.");
    } finally {
      setLoading(false);
    }
  }

  async function saveProvider(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      await apiPost<ProviderProfile>("/api/runtime/providers", {
        name: providerForm.name,
        provider: providerForm.provider,
        surface: providerForm.surface,
        api_key: providerForm.api_key || null,
        account_sid: providerForm.account_sid || null,
        auth_token: providerForm.auth_token || null,
        from_number: providerForm.from_number || null,
        model: providerForm.model || null,
        endpoint: providerForm.endpoint || null,
        notes: providerForm.notes,
        metadata: {},
      });
      startTransition(() => {
        setProviderForm(defaultProviderForm);
      });
      await refreshRuntimeConfig();
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Unable to save provider profile.");
    } finally {
      setLoading(false);
    }
  }

  async function saveTool(): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      await apiPost<ToolIntegration>("/api/tools", {
        name: toolForm.name,
        kind: toolForm.kind,
        description: toolForm.description,
        enabled: true,
        endpoint_url: toolForm.endpoint_url || null,
        http_method: "POST",
        auth_profile_id: toolForm.auth_profile_id || null,
        mapped_functions: toolForm.mapped_functions
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
        static_headers: {},
        expected_fields: ["reason"],
        simulator_response: toolForm.simulator_response,
      });
      startTransition(() => {
        setToolForm(defaultToolForm);
      });
      await Promise.all([refreshRuntimeConfig(), refreshToolHistory(), refreshDashboard()]);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Unable to save tool integration.");
    } finally {
      setLoading(false);
    }
  }

  async function runToolProbe(toolId: string, functionName: string | undefined): Promise<void> {
    setLoading(true);
    setError(null);
    try {
      await apiPost<ToolExecutionRecord>(`/api/tools/${toolId}/execute`, {
        session_id: selectedSessionId,
        reason: "Operator diagnostic run from the Sonic Calling tool mesh.",
        arguments: {
          function_name: functionName,
          reason: "Operator diagnostic run from the Sonic Calling tool mesh.",
        },
      });
      await Promise.all([refreshToolHistory(), refreshSessions()]);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Unable to run tool probe.");
    } finally {
      setLoading(false);
    }
  }

  const activeContact = summary?.contacts.find((contact) => contact.id === activeContactId) ?? null;
  const activeAgentProfile = summary?.agent_profiles.find((profile) => profile.id === activeAgentProfileId) ?? null;
  const activeSessionFromLedger =
    sessionLedger.find((session) => session.session_id === selectedSessionId) ?? null;
  const activeSession =
    sessionView?.session.session_id === selectedSessionId
      ? sessionView.session
      : activeSessionFromLedger ?? sessionView?.session ?? null;
  const liveTrace = sessionView?.agent_reply?.trace ?? activeSession?.trace ?? [];
  const compliance = activeSession?.compliance ?? sessionPlan?.compliance ?? null;
  const complianceReasons = compliance?.reasons.length ? compliance.reasons : summary?.compliance_rules ?? [];
  const missingRequirements = compliance?.missing_requirements ?? [];
  const runtimePath = activeSession?.websocket_path ?? sessionPlan?.websocket_path ?? "/twilio/media-stream/preview";
  const runtimeDisposition = sessionView?.agent_reply?.disposition ?? activeSession?.latest_disposition ?? "continue";
  const planNotes = sessionPlan?.notes ?? [];
  const runtimeHealth = summary?.runtime_health ?? null;
  const providerProfiles = runtimeConfig?.provider_profiles ?? [];
  const toolIntegrations = runtimeConfig?.tool_integrations ?? [];

  const groupedProviders = {
    realtime: providerProfiles.filter((profile) => profile.surface === "realtime"),
    telephony: providerProfiles.filter((profile) => profile.surface === "telephony"),
    tooling: providerProfiles.filter((profile) => profile.surface === "tooling"),
    analytics: providerProfiles.filter((profile) => profile.surface === "analytics"),
  };

  return (
    <div className="shell">
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Realtime telephony platform / OpenAI Realtime / Twilio Media Streams / BYO API</p>
          <h1>Sonic Calling</h1>
          <p className="hero-body">
            Build production-grade voice agents with a VideoSDK-style developer experience: realtime session
            templates, Twilio stream ingress, masked provider vaults, live tool execution, client-secret minting,
            runtime observability, and a hyper-detailed operator cockpit for testing every call path before you deploy.
          </p>
        </div>

        <div className="hero-actions">
          <button type="button" className="primary-action" onClick={() => void launchSimulator()} disabled={loading}>
            Launch Simulator
          </button>
          <button type="button" className="secondary-action" onClick={() => void mintClientSecret()} disabled={loading}>
            Mint Client Secret
          </button>
          <div className="api-badge">
            <span>OpenAI Realtime</span>
            <span>Twilio Voice</span>
            <span>BYO Provider Vault</span>
            <span>Tool Mesh</span>
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
              <span>Runtime readiness</span>
              <strong>{runtimeHealth?.live_bridge_enabled ? "Live bridge available" : "Simulator fallback"}</strong>
            </div>
            <div className="status-grid">
              <article className="status-card">
                <span>OpenAI live</span>
                <strong>{runtimeHealth?.openai_api_configured ? "Configured" : "Missing key"}</strong>
              </article>
              <article className="status-card">
                <span>Twilio live</span>
                <strong>{runtimeHealth?.twilio_credentials_configured ? "Configured" : "Missing creds"}</strong>
              </article>
              <article className="status-card">
                <span>BYO realtime</span>
                <strong>{runtimeHealth?.byo_realtime_ready ? "Ready" : "Not ready"}</strong>
              </article>
              <article className="status-card">
                <span>Tool integrations</span>
                <strong>{runtimeHealth?.tool_integrations_enabled ?? 0}</strong>
              </article>
            </div>
          </section>

          <section className="panel">
            <div className="section-header">
              <span>Provider vault</span>
              <strong>{providerProfiles.length} profiles</strong>
            </div>
            <div className="vault-grid">
              {(["realtime", "telephony", "tooling"] as ProviderSurface[]).map((surface) => (
                <div key={surface} className="vault-column">
                  <h2>{surface}</h2>
                  <div className="trace-list">
                    {(groupedProviders[surface] ?? []).map((profile) => (
                      <article key={profile.profile_id} className={`trace-card provider-card ${profile.active ? "provider-card-active" : ""}`}>
                        <div className="trace-topline">
                          <strong>{profile.name}</strong>
                          <span>{profile.provider}</span>
                        </div>
                        <p>{profile.model ?? profile.account_label ?? profile.endpoint ?? "Configured profile"}</p>
                        <small>{profile.masked_secret ?? "No secret stored"}</small>
                        <div className="tool-stack compact-stack">
                          <span>{profile.auth_source}</span>
                          <span>{profile.ready ? "ready" : "needs setup"}</span>
                        </div>
                        <ul className="mini-list">
                          {profile.readiness_notes.map((note) => (
                            <li key={note}>{note}</li>
                          ))}
                        </ul>
                        <button
                          type="button"
                          className="secondary-action inline-action"
                          onClick={() => void activateProvider(profile.surface, profile.profile_id)}
                          disabled={loading || profile.active}
                        >
                          {profile.active ? "Active" : "Activate"}
                        </button>
                      </article>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            <div className="config-form">
              <div className="form-heading">
                <strong>Add BYO provider</strong>
                <span>Store masked credentials for realtime, telephony, or sidecar tooling.</span>
              </div>
              <div className="form-grid">
                <label>
                  Name
                  <input value={providerForm.name} onChange={(event) => setProviderForm((current) => ({ ...current, name: event.target.value }))} />
                </label>
                <label>
                  Provider
                  <select value={providerForm.provider} onChange={(event) => setProviderForm((current) => ({ ...current, provider: event.target.value as ProviderName }))}>
                    <option value="openai">OpenAI</option>
                    <option value="gemini">Gemini</option>
                    <option value="twilio">Twilio</option>
                    <option value="custom">Custom</option>
                  </select>
                </label>
                <label>
                  Surface
                  <select value={providerForm.surface} onChange={(event) => setProviderForm((current) => ({ ...current, surface: event.target.value as ProviderSurface }))}>
                    <option value="realtime">Realtime</option>
                    <option value="telephony">Telephony</option>
                    <option value="tooling">Tooling</option>
                    <option value="analytics">Analytics</option>
                  </select>
                </label>
                <label>
                  Model
                  <input value={providerForm.model} onChange={(event) => setProviderForm((current) => ({ ...current, model: event.target.value }))} />
                </label>
                <label>
                  Endpoint
                  <input value={providerForm.endpoint} onChange={(event) => setProviderForm((current) => ({ ...current, endpoint: event.target.value }))} />
                </label>
                <label>
                  API key
                  <input value={providerForm.api_key} onChange={(event) => setProviderForm((current) => ({ ...current, api_key: event.target.value }))} />
                </label>
                <label>
                  Account SID
                  <input value={providerForm.account_sid} onChange={(event) => setProviderForm((current) => ({ ...current, account_sid: event.target.value }))} />
                </label>
                <label>
                  Auth token
                  <input value={providerForm.auth_token} onChange={(event) => setProviderForm((current) => ({ ...current, auth_token: event.target.value }))} />
                </label>
                <label>
                  From number
                  <input value={providerForm.from_number} onChange={(event) => setProviderForm((current) => ({ ...current, from_number: event.target.value }))} />
                </label>
              </div>
              <label className="full-width">
                Notes
                <textarea value={providerForm.notes} onChange={(event) => setProviderForm((current) => ({ ...current, notes: event.target.value }))} />
              </label>
              <button type="button" className="secondary-action" onClick={() => void saveProvider()} disabled={loading || !providerForm.name}>
                Save Provider Profile
              </button>
            </div>
          </section>

          <section className="panel">
            <div className="section-header">
              <span>Tool mesh</span>
              <strong>{toolIntegrations.length} integrations</strong>
            </div>
            <div className="trace-list">
              {toolIntegrations.map((tool) => (
                <article key={tool.tool_id} className="trace-card">
                  <div className="trace-topline">
                    <strong>{tool.name}</strong>
                    <span>{tool.kind}</span>
                  </div>
                  <p>{tool.description}</p>
                  <small>{tool.last_result_summary || tool.simulator_response || "No executions yet."}</small>
                  <div className="tool-stack compact-stack">
                    {tool.mapped_functions.map((fn) => (
                      <span key={fn}>{fn}</span>
                    ))}
                  </div>
                  <div className="default-row inline-row">
                    <span>{tool.requires_network ? tool.endpoint_url ?? "Endpoint required" : "Simulator-safe integration"}</span>
                    <button
                      type="button"
                      className="secondary-action inline-action"
                      onClick={() => void runToolProbe(tool.tool_id, tool.mapped_functions[0])}
                      disabled={loading}
                    >
                      Run Probe
                    </button>
                  </div>
                </article>
              ))}
            </div>

            <div className="config-form">
              <div className="form-heading">
                <strong>Add tool integration</strong>
                <span>Map agent functions to a webhook, CRM, booking engine, or handoff rail.</span>
              </div>
              <div className="form-grid">
                <label>
                  Name
                  <input value={toolForm.name} onChange={(event) => setToolForm((current) => ({ ...current, name: event.target.value }))} />
                </label>
                <label>
                  Kind
                  <select value={toolForm.kind} onChange={(event) => setToolForm((current) => ({ ...current, kind: event.target.value as ToolKind }))}>
                    <option value="webhook">Webhook</option>
                    <option value="crm">CRM</option>
                    <option value="calendar">Calendar</option>
                    <option value="sms">SMS</option>
                    <option value="handoff">Handoff</option>
                    <option value="lookup">Lookup</option>
                  </select>
                </label>
                <label>
                  Auth profile
                  <select value={toolForm.auth_profile_id} onChange={(event) => setToolForm((current) => ({ ...current, auth_profile_id: event.target.value }))}>
                    <option value="">None</option>
                    {providerProfiles.map((profile) => (
                      <option key={profile.profile_id} value={profile.profile_id}>
                        {profile.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Endpoint URL
                  <input value={toolForm.endpoint_url} onChange={(event) => setToolForm((current) => ({ ...current, endpoint_url: event.target.value }))} />
                </label>
              </div>
              <label className="full-width">
                Description
                <textarea value={toolForm.description} onChange={(event) => setToolForm((current) => ({ ...current, description: event.target.value }))} />
              </label>
              <div className="form-grid">
                <label>
                  Mapped functions
                  <input value={toolForm.mapped_functions} onChange={(event) => setToolForm((current) => ({ ...current, mapped_functions: event.target.value }))} />
                </label>
                <label>
                  Simulator response
                  <input value={toolForm.simulator_response} onChange={(event) => setToolForm((current) => ({ ...current, simulator_response: event.target.value }))} />
                </label>
              </div>
              <button type="button" className="secondary-action" onClick={() => void saveTool()} disabled={loading || !toolForm.name}>
                Save Tool Integration
              </button>
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
              <strong>{activeSession ? activeSession.state : "ready"}</strong>
            </div>

            <div className="sim-layout">
              <div className="transcript-card">
                <h2>Conversation stream</h2>
                <div className="transcript-feed">
                  {activeSession?.turns.length ? (
                    activeSession.turns.map((turn, index) => (
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
              <span>Client secret</span>
              <strong>{clientSecretResult?.enabled ? "Live ready" : clientSecretResult ? "Preview only" : "Not minted"}</strong>
            </div>
            <div className="secret-card">
              <p>
                {clientSecretResult?.enabled
                  ? "Short-lived browser credential minted successfully."
                  : clientSecretResult?.preview_reason ?? "Generate a realtime client secret for a browser or WebRTC client."}
              </p>
              <div className="secret-meta">
                <span>Session</span>
                <strong>{clientSecretResult?.session_id ?? "n/a"}</strong>
              </div>
              <div className="secret-meta">
                <span>Expires</span>
                <strong>
                  {clientSecretResult?.client_secret?.expires_at
                    ? new Date(clientSecretResult.client_secret.expires_at * 1000).toLocaleTimeString()
                    : "n/a"}
                </strong>
              </div>
            </div>
          </section>

          <section className="panel">
            <div className="section-header">
              <span>Bridge telemetry</span>
              <strong>{activeSession?.runtime.bridge_status ?? "idle"}</strong>
            </div>
            <div className="telemetry-grid">
              <div className="default-row">
                <span>Mode</span>
                <strong>{activeSession?.runtime.bridge_mode ?? "simulated"}</strong>
              </div>
              <div className="default-row">
                <span>Realtime profile</span>
                <strong>{activeSession?.runtime.provider_profile_id ?? "n/a"}</strong>
              </div>
              <div className="default-row">
                <span>Telephony profile</span>
                <strong>{activeSession?.runtime.telephony_profile_id ?? "n/a"}</strong>
              </div>
              <div className="default-row">
                <span>OpenAI response</span>
                <strong>{activeSession?.runtime.openai_response_id ?? "n/a"}</strong>
              </div>
              <div className="default-row">
                <span>Twilio events</span>
                <strong>{activeSession?.runtime.twilio_event_count ?? 0}</strong>
              </div>
              <div className="default-row">
                <span>OpenAI events</span>
                <strong>{activeSession?.runtime.openai_event_count ?? 0}</strong>
              </div>
              <div className="default-row">
                <span>Tool executions</span>
                <strong>{activeSession?.runtime.tool_execution_count ?? 0}</strong>
              </div>
              <div className="default-row">
                <span>Last tool status</span>
                <strong>{activeSession?.runtime.last_tool_status ?? "n/a"}</strong>
              </div>
            </div>
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
                      <strong>{trace.provider === "openai" ? "OpenAI Realtime" : trace.provider}</strong>
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
              <span>Session tool output</span>
              <strong>{activeSession?.tool_executions.length ?? 0} executions</strong>
            </div>
            <div className="event-list">
              {(activeSession?.tool_executions ?? []).length ? (
                activeSession?.tool_executions.map((execution) => (
                  <article key={execution.execution_id} className="event-card">
                    <div className="trace-topline">
                      <strong>{execution.tool_name}</strong>
                      <span>{execution.status}</span>
                    </div>
                    <p>{String(execution.output_payload.summary ?? execution.reason)}</p>
                    <small>{formatTimestamp(execution.timestamp)}</small>
                  </article>
                ))
              ) : (
                <div className="trace-card">
                  <p>No tool executions recorded on this session yet.</p>
                </div>
              )}
            </div>
          </section>

          <section className="panel">
            <div className="section-header">
              <span>Global tool history</span>
              <strong>{toolHistory.length} recent</strong>
            </div>
            <div className="event-list">
              {toolHistory.map((execution) => (
                <article key={execution.execution_id} className="event-card">
                  <div className="trace-topline">
                    <strong>{execution.tool_name}</strong>
                    <span>{execution.status}</span>
                  </div>
                  <p>{String(execution.output_payload.summary ?? execution.reason)}</p>
                  <small>{execution.session_id ?? "no session"} / {formatTimestamp(execution.timestamp)}</small>
                </article>
              ))}
            </div>
          </section>

          <section className="panel">
            <div className="section-header">
              <span>Event timeline</span>
              <strong>{activeSession?.events.length ?? 0} events</strong>
            </div>
            <div className="event-list">
              {(activeSession?.events ?? []).length ? (
                activeSession?.events.map((event, index) => (
                  <article key={`${event.event}-${index}`} className="event-card">
                    <div className="trace-topline">
                      <strong>{event.source}</strong>
                      <span>{event.event}</span>
                    </div>
                    <p>{event.detail}</p>
                    <small>{formatTimestamp(event.timestamp)}</small>
                  </article>
                ))
              ) : (
                <div className="trace-card">
                  <p>No bridge events yet.</p>
                </div>
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
              <span>Session ledger</span>
              <strong>{sessionLedger.length} tracked</strong>
            </div>
            <div className="ledger-list">
              {sessionLedger.map((session) => (
                <button
                  type="button"
                  key={session.session_id}
                  className={`ledger-card ${session.session_id === selectedSessionId ? "ledger-card-active" : ""}`}
                  onClick={() => setSelectedSessionId(session.session_id)}
                >
                  <div className="trace-topline">
                    <strong>{session.contact.full_name}</strong>
                    <span>{session.state}</span>
                  </div>
                  <p>{session.agent_profile.name}</p>
                  <small>{formatTimestamp(session.created_at)}</small>
                </button>
              ))}
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
