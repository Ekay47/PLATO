import { useEffect, useRef, useState, useCallback } from 'react';
import ReactFlow, { 
  Background, 
  Controls, 
  MiniMap, 
  Panel,
  ReactFlowProvider,
  useReactFlow
} from 'reactflow';
import 'reactflow/dist/style.css';

import { useDiagram } from './hooks/useDiagram';
import { nodeTypes } from './components/CustomNodes';
import { Logo } from './components/Logo';
import { extractErrorFromResponse, formatBackendDetail, parseRunEvent, type RunCreateResponse } from './types/api-contract';

type StepStatus = 'pending' | 'active' | 'completed' | 'failed';

const formatTokenUsage = (value: any): string[] | undefined => {
  if (!value) return undefined;
  if (typeof value === 'string') return [value];
  if (typeof value !== 'object') return [String(value)];

  const message = value.message;
  if (typeof message === 'string' && message.length > 0) {
    return [`Token usage: ${message}`];
  }

  const total = value.total_tokens;
  const prompt = value.prompt_tokens;
  const completion = value.completion_tokens;

  if ([total, prompt, completion].every((x) => typeof x !== 'number')) return undefined;

  return [
    `Total tokens: ${total ?? 0}`,
    `Prompt tokens: ${prompt ?? 0}`,
    `Completion tokens: ${completion ?? 0}`
  ];
};

const WorkflowStep = ({ label, status, result, activeMessages }: { label: string, status: StepStatus, result?: any, activeMessages?: string[] }) => {
  const [expanded, setExpanded] = useState(false);
  const [contentOverflow, setContentOverflow] = useState(false);
  const contentRef = useRef<HTMLDivElement | null>(null);
  const isArrayResult = Array.isArray(result);

  useEffect(() => {
    setExpanded(false);
  }, [result]);

  useEffect(() => {
    const el = contentRef.current;
    if (!el) return;
    const check = () => setContentOverflow(el.scrollHeight > el.clientHeight + 1);
    check();
    const id = window.requestAnimationFrame(check);
    return () => window.cancelAnimationFrame(id);
  }, [result, expanded]);

  return (
    <div className="relative flex flex-col gap-2">
      <div className="flex items-start gap-3 relative">
        <div className={`w-6 h-6 rounded-full flex items-center justify-center shrink-0 transition-all ${
          status === 'completed' ? 'bg-brand-500 text-white' : 
          status === 'active' ? 'bg-brand-100 border-2 border-brand-500' : 
          status === 'failed' ? 'bg-red-500 text-white' :
          'bg-slate-200'
        }`}>
          {status === 'completed' && (
            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
              <path d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" />
            </svg>
          )}
          {status === 'failed' && (
            <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-9-3a1 1 0 012 0v4a1 1 0 01-2 0V7zm1 8a1.25 1.25 0 100-2.5A1.25 1.25 0 0010 15z" clipRule="evenodd" />
            </svg>
          )}
          {status === 'active' && <div className="w-1.5 h-1.5 bg-brand-500 rounded-full animate-pulse-dot"></div>}
        </div>
        <div className="flex-1 min-w-0">
          <div className="h-6 flex items-center">
            <p className={`text-xs font-bold uppercase ${
            status === 'completed' ? 'text-slate-800' : 
            status === 'active' ? 'text-brand-600' : 
            status === 'failed' ? 'text-red-600' :
            'text-slate-400'
            }`}>{label}</p>
          </div>
          {status === 'active' && activeMessages && activeMessages.length > 0 && (
            <div className="mt-2 space-y-1">
              {activeMessages.slice(-6).map((m, i) => (
                <div key={i} className="flex items-start gap-2 text-[10px] text-slate-500 font-mono animate-pulse">
                  <div className="w-1.5 h-1.5 bg-brand-500 rounded-full animate-pulse-dot mt-1"></div>
                  <div className="whitespace-pre-wrap break-words">{m}</div>
                </div>
              ))}
            </div>
          )}
          {status === 'completed' && result && (
            <div className="mt-2 p-2 bg-slate-100 rounded text-[10px] font-mono text-slate-600 overflow-hidden max-w-full">
              <div ref={contentRef} className={`max-h-40 ${expanded ? 'overflow-auto' : 'overflow-hidden'}`}>
                {isArrayResult ? (
                  <ul className="list-disc list-inside">
                    {result.map((item, i) => (
                      <li key={i} className="break-words">{item}</li>
                    ))}
                  </ul>
                ) : (
                  <pre className="whitespace-pre-wrap break-words">{String(result)}</pre>
                )}
              </div>
              {contentOverflow && (
                <button
                  type="button"
                  onClick={() =>
                    setExpanded((v) => {
                      const next = !v;
                      if (!next && contentRef.current) contentRef.current.scrollTop = 0;
                      return next;
                    })
                  }
                  className="mt-2 text-[10px] font-semibold text-brand-600 hover:text-brand-700"
                >
                  {expanded ? 'Collapse' : 'Expand'}
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const Flow = ({ diagramType, setDiagramType, requirementText, setRequirementText, isGenerating, setIsGenerating }: any) => {
  const [intermediateResults, setIntermediateResults] = useState<any>({});
  const [progressMessages, setProgressMessages] = useState<Record<string, string[]>>({});
  const [stepStatus, setStepStatus] = useState<Record<string, StepStatus>>({
    workflow_initialization: 'pending',
    activity_identification: 'pending',
    structure_decomposition: 'pending',
    information_integration: 'pending',
    plantuml_generation: 'pending',
    canvas_rendering: 'pending',
  });
  const [viewMode, setViewMode] = useState<'canvas' | 'code'>('canvas');
  const [outputDiagramType, setOutputDiagramType] = useState('activity');
  const [isExporting, setIsExporting] = useState(false);
  const [backendStatus, setBackendStatus] = useState<{status: string, version: string}>({ status: 'checking...', version: 'unknown' });
  const [toastMessage, setToastMessage] = useState<{text: string, type: 'error' | 'warning' | 'info'} | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const [renderWaitVersion, setRenderWaitVersion] = useState<number | null>(null);
  const { 
    nodes, 
    edges, 
    onNodesChange, 
    onEdgesChange, 
    onConnect, 
    code,
    setCode, 
    error: parseError,
    layoutVersion,
    resetToDefaultLayout
  } = useDiagram();

  const reactFlowInstance = useReactFlow();
  const apiBase = import.meta.env.VITE_API_BASE || 'http://localhost:8147';

  const normalizeProgressMessage = useCallback((payload: any) => {
    const raw =
      (typeof payload?.message === 'string' ? payload.message : '') ||
      (typeof payload?.ui?.text === 'string' ? payload.ui.text : '');
    const msg = String(raw || '').replace(/\s+/g, ' ').trim();
    if (!msg) return null;
    if (/^waiting for llm response/i.test(msg)) return null;
    const allowed =
      /^(identify:|decompose:|verify:|reconstruct:|generate:|nlp:|llm:|waiting for llm response)/i;
    if (!allowed.test(msg)) return null;
    return msg.length > 240 ? msg.slice(0, 237) + '...' : msg;
  }, []);

  const handleFitView = useCallback(() => {
    reactFlowInstance.fitView({ padding: 0.2, duration: 800 });
  }, [reactFlowInstance]);

  const handleResetCanvas = useCallback(() => {
    const ok = resetToDefaultLayout();
    if (ok) {
      setTimeout(() => reactFlowInstance.fitView({ padding: 0.2, duration: 300 }), 50);
    }
  }, [reactFlowInstance, resetToDefaultLayout]);

  const handleExportPng = useCallback(async () => {
    const uml = String(code || '').trim();
    if (!uml) return;
    setIsExporting(true);
    try {
      const controller = new AbortController();
      const timeoutMs = Number(import.meta.env.VITE_EXPORT_TIMEOUT_MS || 12000);
      const t = window.setTimeout(() => controller.abort(), timeoutMs);
      let res: Response;
      try {
        res = await fetch(`${apiBase}/plantuml/png`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code: uml }),
          signal: controller.signal
        });
      } finally {
        window.clearTimeout(t);
      }
      if (!res.ok) {
        throw new Error(await extractErrorFromResponse(res, 'Export failed'));
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      try {
        const a = document.createElement('a');
        const ts = new Date().toISOString().replace(/[:.]/g, '-');
        a.href = url;
        a.download = `plato-${outputDiagramType}-${ts}.png`;
        document.body.appendChild(a);
        a.click();
        a.remove();
      } finally {
        URL.revokeObjectURL(url);
      }
    } catch (e: any) {
      if (e?.name === 'AbortError') {
        throw new Error('Export timeout');
      }
      throw e;
    } finally {
      setIsExporting(false);
    }
  }, [apiBase, code, outputDiagramType]);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(`${apiBase}/health`, { signal: AbortSignal.timeout(3000) });
        if (res.ok) {
          const data = await res.json();
          setBackendStatus({ status: data.status, version: data.version });
        } else {
          setBackendStatus({ status: 'offline', version: 'unknown' });
        }
      } catch (e) {
        setBackendStatus({ status: 'offline', version: 'unknown' });
      }
    };
    checkHealth();
    // Poll every 30 seconds
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, [apiBase]);

  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (renderWaitVersion === null) return;
    if (layoutVersion > renderWaitVersion && !parseError) {
      setStepStatus((prev) => ({ ...prev, canvas_rendering: 'completed' }));
      setRenderWaitVersion(null);
    }
  }, [layoutVersion, parseError, renderWaitVersion]);

  const isCanvasSupported = outputDiagramType === 'activity';

  const handleGenerateModel = async () => {
    if (backendStatus.status === 'offline') {
      setToastMessage({ text: "Backend service is unavailable. Please check your connection or contact an administrator.", type: 'error' });
      setTimeout(() => setToastMessage(null), 3000);
      return;
    }
    if (!requirementText) return;
    const runDiagramType = diagramType;
    setOutputDiagramType(runDiagramType);
    setViewMode(runDiagramType === 'activity' ? 'canvas' : 'code');
    setIsGenerating(true);
    setIntermediateResults({});
    setProgressMessages({});
    setCode('');
    setToastMessage(null);
    setStepStatus({
      workflow_initialization: 'active',
      activity_identification: 'pending',
      structure_decomposition: 'pending',
      information_integration: 'pending',
      plantuml_generation: 'pending',
      canvas_rendering: 'pending',
    });

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    try {
      const res = await fetch(`${apiBase}/runs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          requirement_text: requirementText,
          diagram_type: diagramType
        })
      });
      if (!res.ok) {
        throw new Error(await extractErrorFromResponse(res, 'Failed to create run'));
      }
      const created = (await res.json()) as Partial<RunCreateResponse> & { detail?: unknown };
      if (!created.run_id) {
        throw new Error(formatBackendDetail(created?.detail) || 'Failed to create run');
      }

      const rid = created.run_id as string;
      const es = new EventSource(`${apiBase}/runs/${rid}/events`);
      eventSourceRef.current = es;

      es.onmessage = (msg) => {
        try {
          const ev = parseRunEvent(msg.data || '{}');
          const type = ev.type as string | undefined;
          const step = ev.step as string | undefined;
          const payload = ev.payload as Record<string, any> | undefined;

          if (type === 'run.snapshot' && payload?.artifacts) {
            setIntermediateResults(payload.artifacts);
          }

          if (type === 'step.started' && step) {
            setProgressMessages((prev) => ({ ...prev, [step]: [] }));
            setStepStatus((prev) => ({
              ...prev,
              workflow_initialization: prev.workflow_initialization === 'active' ? 'completed' : prev.workflow_initialization,
              [step]: 'active',
            }));
          }

          if (type === 'step.progress' && step) {
            const message = normalizeProgressMessage(payload);
            if (typeof message === 'string' && message.length > 0) {
              setProgressMessages((prev) => {
                const current = prev[step] || [];
                if (current.length > 0 && current[current.length - 1] === message) {
                  return prev;
                }
                const next = [...current, message].slice(-12);
                return { ...prev, [step]: next };
              });
            }
          }

          if ((type === 'step.completed' || type === 'step.failed') && step) {
            setStepStatus((prev) => ({ ...prev, [step]: type === 'step.failed' ? 'failed' : 'completed' }));
          }

          if (type === 'artifact.created' && payload?.key) {
            setIntermediateResults((prev: any) => ({ ...prev, [payload.key]: payload.value }));
            if (payload.key === 'plantuml') {
              setStepStatus((prev) => ({ ...prev, plantuml_generation: 'completed', canvas_rendering: 'active' }));
              setRenderWaitVersion(layoutVersion);
              setCode(payload.value || '');
              if (runDiagramType !== 'activity') {
                setViewMode('code');
              }
            }
          }

          if (type === 'run.completed') {
            setIsGenerating(false);
            setStepStatus((prev) => ({ ...prev, workflow_initialization: 'completed' }));
            if (eventSourceRef.current) {
              eventSourceRef.current.close();
              eventSourceRef.current = null;
            }
          }

          if (type === 'run.failed') {
            setIsGenerating(false);
            const dependencyIssue = payload?.error_code === 'DEPENDENCY_UNAVAILABLE' || payload?.error_code === 'CONFIG_INVALID';
            const message = dependencyIssue
              ? (formatBackendDetail(payload?.detail || payload) || payload?.error || 'Runtime dependency is unavailable')
              : (payload?.error || formatBackendDetail(payload?.detail) || 'Run failed');
            setToastMessage({ text: message, type: 'error' });
            setStepStatus((prev) => {
              const next = { ...prev };
              let foundActive = false;
              for (const k in next) {
                if (next[k] === 'active') {
                  next[k] = 'failed';
                  foundActive = true;
                }
              }
              if (!foundActive) {
                next.workflow_initialization = 'failed';
              }
              return next;
            });
            if (eventSourceRef.current) {
              eventSourceRef.current.close();
              eventSourceRef.current = null;
            }
          }
        } catch (e) {
          setToastMessage({ text: 'Failed to parse SSE event', type: 'error' });
        }
      };

      es.onerror = () => {
        setIsGenerating(false);
        setToastMessage({ text: 'SSE connection error', type: 'error' });
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = null;
        }
      };
    } catch (err: any) {
      console.error('Generation failed:', err);
      setToastMessage({ text: err.message || 'Generation failed', type: 'error' });
    } finally {
      if (!eventSourceRef.current) {
        setIsGenerating(false);
      }
    }
  };

  return (
    <main className="flex-1 flex overflow-hidden">
      {/* Left Sidebar: Input Section */}
      <section className="w-1/4 min-w-[320px] max-w-md border-r border-slate-200 bg-white flex flex-col">
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="font-semibold text-slate-800">NL Requirement Input</h2>
          <span className="text-[10px] px-2 py-0.5 bg-brand-50 text-brand-700 rounded-full font-bold uppercase tracking-wider">
            {isGenerating ? 'Processing' : 'Ready'}
          </span>
        </div>
        <div className="flex-1 p-4 flex flex-col gap-4">
          {/* Diagram Type Toggle */}
          <div className="bg-slate-100 p-1 rounded-xl flex">
            {['activity', 'sequence', 'state'].map((type) => (
              <button
                key={type}
                className={`flex-1 py-2 text-[11px] font-bold rounded-lg transition-all ${
                  diagramType === type 
                    ? 'bg-white text-brand-600 shadow-sm border border-slate-200' 
                    : 'text-slate-500 hover:text-slate-700'
                }`}
                onClick={() => setDiagramType(type)}
              >
                {type.toUpperCase()}
              </button>
            ))}
          </div>
          <div className="flex-1 relative group">
            <textarea
              className="w-full h-full p-4 pb-10 text-sm text-slate-700 border border-slate-200 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-transparent resize-none leading-relaxed"
              placeholder="Describe your process here..."
              value={requirementText}
              onChange={(e) => setRequirementText(e.target.value)}
            />
            <div className="absolute bottom-4 right-4 text-[10px] text-slate-400 bg-white/80 px-1 rounded pointer-events-none">100% Secure Processing</div>
          </div>
          <button 
            onClick={handleGenerateModel}
            disabled={isGenerating || !requirementText}
            className="w-full bg-brand-600 hover:bg-brand-700 text-white font-semibold py-3 px-6 rounded-xl transition-all shadow-lg shadow-brand-200 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path d="M13 10V3L4 14h7v7l9-11h-7z" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
            </svg>
            {isGenerating ? 'Generating...' : 'Generate Diagram'}
          </button>
        </div>
      </section>

      {/* Middle Panel: Workflow Execution */}
      <section className="w-[272px] border-r border-slate-200 bg-surface-50 flex flex-col">
        <div className="p-4 border-b border-slate-200 bg-white">
          <h2 className="font-semibold text-slate-800 text-sm">Execution Flow</h2>
        </div>
        <div className="flex-1 p-4 space-y-6 overflow-y-auto">
          <WorkflowStep 
            label="Workflow Initialization" 
            status={stepStatus.workflow_initialization} 
            activeMessages={isGenerating ? ["Creating run and waiting for events..."] : undefined}
          />
          <WorkflowStep 
            label="Activity Identification" 
            status={stepStatus.activity_identification} 
            result={intermediateResults.identification}
            activeMessages={progressMessages.activity_identification}
          />
          <WorkflowStep 
            label="Structure Decomposition" 
            status={stepStatus.structure_decomposition} 
            result={intermediateResults.decomposition}
            activeMessages={progressMessages.structure_decomposition}
          />
          <WorkflowStep 
            label="Information Integration" 
            status={stepStatus.information_integration} 
            result={intermediateResults.integration}
            activeMessages={progressMessages.information_integration}
          />
          <WorkflowStep 
            label="PlantUML Generation" 
            status={stepStatus.plantuml_generation} 
            result={formatTokenUsage(intermediateResults.token_usage)}
            activeMessages={progressMessages.plantuml_generation}
          />
          <WorkflowStep 
            label="Canvas Rendering" 
            status={stepStatus.canvas_rendering} 
          />
        </div>
        <div className="p-4 bg-slate-900 text-white text-[10px] font-mono flex justify-between items-center">
          <div>
            <span className={backendStatus.status === 'online' ? 'text-green-400' : 'text-red-400'}>λ</span> 
            <span className="ml-2">Engine: {backendStatus.status}</span>
          </div>
          <div className="text-slate-500">
            {backendStatus.version !== 'unknown' ? backendStatus.version : 'v2.4.0'}
          </div>
        </div>
      </section>

      {/* Right Panel: Output Canvas */}
      <section className="flex-1 bg-surface-100 relative flex flex-col">
        {/* Global Toast */}
        {toastMessage && (
          <div className={`absolute top-20 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-lg shadow-lg text-sm font-medium transition-all animate-in fade-in slide-in-from-top-4 ${
            toastMessage.type === 'error' ? 'bg-red-100 text-red-700 border border-red-200' :
            toastMessage.type === 'warning' ? 'bg-amber-100 text-amber-700 border border-amber-200' :
            'bg-slate-800 text-white'
          }`}>
            {toastMessage.text}
          </div>
        )}
        {isExporting && (
          <div className="absolute inset-0 z-50 bg-black/30 flex items-center justify-center">
            <div className="bg-white rounded-lg shadow-xl border border-slate-200 px-5 py-4 flex items-center gap-3">
              <div className="w-2 h-2 bg-brand-500 rounded-full animate-pulse-dot"></div>
              <div className="text-sm font-medium text-slate-700">Exporting PNG...</div>
            </div>
          </div>
        )}
        {/* Canvas Toolbar */}
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 flex items-center gap-1 p-1 bg-white shadow-xl rounded-full border border-slate-200">
          <button 
            onClick={() => {
              if (!isCanvasSupported) {
                setToastMessage({ text: 'Canvas rendering for this diagram type is not currently supported.', type: 'warning' });
                setTimeout(() => setToastMessage(null), 3000);
                return;
              }
              setViewMode('canvas');
            }}
            className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all ${viewMode === 'canvas' ? 'bg-slate-800 text-white shadow-sm' : 'text-slate-500 hover:bg-slate-100'} ${!isCanvasSupported ? 'opacity-50 cursor-not-allowed' : ''}`}
            title={!isCanvasSupported ? "Not currently supported" : ""}
          >
            Canvas
          </button>
          <button 
            onClick={() => setViewMode('code')}
            className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all ${viewMode === 'code' ? 'bg-slate-800 text-white shadow-sm' : 'text-slate-500 hover:bg-slate-100'}`}
          >
            Code
          </button>
        </div>

        <div className="flex-1 canvas-bg relative overflow-hidden flex flex-col">
          {!isCanvasSupported && viewMode === 'canvas' ? (
            <div className="flex-1 flex items-center justify-center bg-surface-100">
              <div className="text-slate-400 font-medium flex flex-col items-center gap-2">
                <svg className="w-8 h-8 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                </svg>
                <span>Canvas rendering for {outputDiagramType} is not currently supported.</span>
                <span className="text-xs">Please use the Code view or Export PNG.</span>
              </div>
            </div>
          ) : viewMode === 'canvas' ? (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              nodeTypes={nodeTypes}
              fitView
              minZoom={0.1}
            >
              <Background color="#aaa" gap={16} />
              <Controls />
              <MiniMap />
              <Panel position="top-right">
                <div className="flex items-center gap-1 p-1 bg-white shadow-xl rounded-full border border-slate-200 mt-12">
                  <button onClick={handleFitView} className="p-2 hover:bg-slate-50 rounded-full text-slate-600">
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
                    </svg>
                  </button>
                </div>
              </Panel>
            </ReactFlow>
          ) : (
            <div className="flex-1 w-full h-full bg-slate-900 p-6 pt-16">
              <textarea
                className="w-full h-full bg-transparent text-green-400 font-mono text-sm resize-none outline-none leading-relaxed"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                spellCheck={false}
                placeholder="// PlantUML code will appear here..."
              />
            </div>
          )}
        </div>

        {/* Canvas Footer */}
        <div className="p-4 bg-white border-t border-slate-200 flex justify-between items-center">
          <div className="text-xs text-slate-400 font-mono">
            {parseError || (isGenerating ? "Generating model..." : "Model visualization ready")}
          </div>
          <div className="flex gap-3">
            <button onClick={handleResetCanvas} className="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-800 border border-slate-200 rounded-lg hover:bg-slate-50">Reset Canvas</button>
            <button onClick={() => { handleExportPng().catch((e) => setToastMessage({ text: String(e?.message || e || 'Export failed'), type: 'error' })); }} className="px-4 py-2 text-sm font-bold text-white bg-slate-800 rounded-lg hover:bg-slate-900 shadow-md">Export PNG</button>
          </div>
        </div>
      </section>
    </main>
  );
};

function App() {
  const [requirementText, setRequirementText] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [diagramType, setDiagramType] = useState('activity');

  return (
    <div className="bg-surface-50 text-slate-900 font-sans h-screen flex flex-col overflow-hidden">
      {/* Top Navigation */}
      <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between z-10">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-3">
            <Logo className="w-10 h-10 text-brand-600" fill="currentColor" />
            <span className="font-bold text-xl tracking-tight text-slate-800 underline decoration-brand-500 decoration-2 underline-offset-4">PLATO</span>
          </div>
        </div>
        <div className="flex items-center gap-4">
        </div>
      </header>

      <ReactFlowProvider>
        <Flow 
          diagramType={diagramType}
          setDiagramType={setDiagramType}
          requirementText={requirementText}
          setRequirementText={setRequirementText}
          isGenerating={isGenerating}
          setIsGenerating={setIsGenerating}
        />
      </ReactFlowProvider>
    </div>
  );
}

export default App;
