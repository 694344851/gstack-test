import { useMemo, useReducer } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type StageStatus = "not_started" | "running" | "succeeded" | "failed";
type TaskStatus = "queued" | "running" | "failed" | "completed";
type StageName =
  | "source_analysis"
  | "lyric_plan"
  | "composition_brief"
  | "cover_direction"
  | "audio_render";

type StageSnapshot = {
  status: StageStatus;
  artifact: Record<string, unknown> | null;
};

type TaskSnapshot = {
  id: string;
  status: TaskStatus;
  currentStage: StageName | "completed";
  input: {
    title: string;
    synopsis: string | null;
  };
  stages: Record<StageName, StageSnapshot>;
  currentResult: {
    title: string | null;
    coverUrl: string | null;
    audioUrl: string | null;
    activeStyle: string;
  };
  error: { stage: string; message: string; retryable: boolean } | null;
  createdAt?: string;
  updatedAt?: string;
};

type WorkspaceMode = "seeded" | "user";

type UiState = {
  mode: WorkspaceMode;
  selectedStage: StageName;
  title: string;
  synopsis: string;
};

type UiAction =
  | { type: "select-stage"; stage: StageName }
  | { type: "set-title"; value: string }
  | { type: "set-synopsis"; value: string }
  | { type: "enter-user-workspace" };

const STAGE_ORDER: StageName[] = [
  "source_analysis",
  "lyric_plan",
  "composition_brief",
  "cover_direction",
  "audio_render",
];

const STAGE_LABELS: Record<StageName, string> = {
  source_analysis: "剧情提炼",
  lyric_plan: "歌词结构",
  composition_brief: "编曲设定",
  cover_direction: "封面方向",
  audio_render: "音频渲染",
};

const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  queued: "排队中",
  running: "生成中",
  failed: "失败",
  completed: "已完成",
};

const STAGE_STATUS_LABELS: Record<StageStatus, string> = {
  not_started: "未开始",
  running: "生成中",
  succeeded: "已完成",
  failed: "失败",
};

const ARTIFACT_FIELD_LABELS: Record<string, string> = {
  summary: "主题摘要",
  themes: "核心主题",
  emotionArc: "情绪弧线",
  motifs: "视觉母题",
  suggestedAudience: "目标受众",
  concept: "歌词概念",
  sections: "段落结构",
  name: "名称",
  purpose: "作用",
  hook: "副歌锚点",
  sourceSummary: "来源摘要",
  titleProposal: "标题提案",
  bpm: "速度",
  key: "调式",
  timeSignature: "拍号",
  arrangement: "配器方向",
  vocalDirection: "演唱方向",
  structure: "结构",
  artDirection: "视觉方向",
  titleLock: "封面标题",
  title: "标题",
  durationSeconds: "时长",
};

const SEEDED_EXAMPLE: TaskSnapshot = {
  id: "seeded_example",
  status: "completed",
  currentStage: "completed",
  input: {
    title: "哪吒",
    synopsis: "一个围绕反抗命运与情绪抬升展开的热门题材示例。",
  },
  stages: {
    source_analysis: {
      status: "succeeded",
      artifact: {
        summary: "识别出反抗命运、牺牲与关系张力三条主线。",
      },
    },
    lyric_plan: {
      status: "succeeded",
      artifact: {
        concept: "副歌聚焦不认命，主歌保留压抑和脆弱感。",
      },
    },
    composition_brief: {
      status: "succeeded",
      artifact: {
        bpm: 92,
        key: "D Minor",
      },
    },
    cover_direction: {
      status: "succeeded",
      artifact: {
        artDirection: "冷底热点的深夜配乐控制台封面",
      },
    },
    audio_render: {
      status: "succeeded",
      artifact: {
        durationSeconds: 24,
      },
    },
  },
  currentResult: {
    title: "哪吒·逆光版",
    coverUrl:
      "data:image/svg+xml;utf8,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20width%3D%27600%27%20height%3D%27600%27%20viewBox%3D%270%200%20600%20600%27%3E%3Crect%20width%3D%27600%27%20height%3D%27600%27%20fill%3D%27%23111923%27/%3E%3Ccircle%20cx%3D%27460%27%20cy%3D%27130%27%20r%3D%2780%27%20fill%3D%27%233CD6C8%27%20fill-opacity%3D%270.25%27/%3E%3Ctext%20x%3D%2760%27%20y%3D%27450%27%20fill%3D%27%23EAF0F8%27%20font-size%3D%2746%27%20font-family%3D%27sans-serif%27%3E%E5%93%AA%E5%90%92%C2%B7%E9%80%86%E5%85%89%E7%89%88%3C/text%3E%3Ctext%20x%3D%2760%27%20y%3D%27510%27%20fill%3D%27%2391A1B4%27%20font-size%3D%2722%27%20font-family%3D%27sans-serif%27%3E%E5%BD%93%E5%89%8D%E7%89%88%E6%9C%AC%20%C2%B7%20%E7%94%B5%E5%BD%B1%E6%B5%81%E8%A1%8C%3C/text%3E%3C/svg%3E",
    audioUrl: null,
    activeStyle: "电影流行",
  },
  error: null,
};

function reducer(state: UiState, action: UiAction): UiState {
  switch (action.type) {
    case "select-stage":
      return { ...state, selectedStage: action.stage };
    case "set-title":
      return { ...state, title: action.value };
    case "set-synopsis":
      return { ...state, synopsis: action.value };
    case "enter-user-workspace":
      return { ...state, mode: "user" };
    default:
      return state;
  }
}

async function createTask(payload: { title: string; synopsis: string }) {
  const response = await fetch(`${API_BASE}/generation-tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error("任务创建失败");
  }
  return (await response.json()) as { taskId: string; snapshot: TaskSnapshot };
}

async function getTask(taskId: string) {
  const response = await fetch(`${API_BASE}/generation-tasks/${taskId}`);
  if (!response.ok) {
    throw new Error("任务查询失败");
  }
  return (await response.json()) as TaskSnapshot;
}

function stageSummary(stage: StageName, snapshot: TaskSnapshot): string {
  const artifact = snapshot.stages[stage].artifact;
  if (stage === "source_analysis" && artifact?.summary) return String(artifact.summary);
  if (stage === "lyric_plan" && artifact?.concept) return String(artifact.concept);
  if (stage === "composition_brief" && artifact?.bpm) {
    return `${String(artifact.bpm)} BPM · ${localizeValue(artifact.key ?? "")}`;
  }
  if (stage === "cover_direction" && artifact?.artDirection) return String(artifact.artDirection);
  if (stage === "audio_render" && artifact?.durationSeconds) {
    return `已生成 ${String(artifact.durationSeconds)} 秒试听片段`;
  }
  switch (snapshot.stages[stage].status) {
    case "running":
      return "正在生成中";
    case "failed":
      return "当前步骤失败，可稍后重试";
    default:
      return "等待执行";
  }
}

function localizeValue(value: unknown): string {
  if (typeof value !== "string") return String(value ?? "未生成");
  if (value === "default") return "默认版本";
  if (value === "D Minor") return "D 小调";
  if (value === "D Major") return "D 大调";
  if (value === "A Minor") return "A 小调";
  if (value === "A Major") return "A 大调";
  if (value === "C Major") return "C 大调";
  if (value === "G Major") return "G 大调";
  if (value === "E Minor") return "E 小调";
  return value;
}

function fieldLabel(key: string): string {
  return ARTIFACT_FIELD_LABELS[key] ?? key;
}

function renderArtifactValue(value: unknown) {
  if (Array.isArray(value)) {
    return (
      <ul className="inspector-list">
        {value.map((item, index) => (
          <li key={`${index}-${String(item)}`}>{typeof item === "object" && item !== null ? renderArtifactValue(item) : localizeValue(item)}</li>
        ))}
      </ul>
    );
  }

  if (value && typeof value === "object") {
    return (
      <dl className="inspector-kv nested">
        {Object.entries(value as Record<string, unknown>).map(([key, nestedValue]) => (
          <div key={key}>
            <dt>{fieldLabel(key)}</dt>
            <dd>{renderArtifactValue(nestedValue)}</dd>
          </div>
        ))}
      </dl>
    );
  }

  return <span>{localizeValue(value)}</span>;
}

function renderInspector(stage: StageName, artifact: Record<string, unknown> | null) {
  if (!artifact) {
    return <p className="inspector-empty">当前步骤还没有产出内容。</p>;
  }

  if (stage === "cover_direction") {
    return (
      <div className="inspector-stack">
        {artifact.coverUrl ? (
          <div className="inspector-cover-preview">
            <img src={String(artifact.coverUrl)} alt={String(artifact.titleLock ?? "封面预览")} />
          </div>
        ) : null}
        <dl className="inspector-kv">
            <div>
              <dt>封面标题</dt>
              <dd>{localizeValue(artifact.titleLock ?? "未生成")}</dd>
            </div>
            <div>
              <dt>视觉方向</dt>
              <dd>{localizeValue(artifact.artDirection ?? "未生成")}</dd>
            </div>
          </dl>
      </div>
    );
  }

  if (stage === "audio_render") {
    return (
      <div className="inspector-stack">
        {artifact.audioUrl ? <audio controls src={String(artifact.audioUrl)} className="inspector-audio" /> : null}
        <dl className="inspector-kv">
            <div>
              <dt>版本标题</dt>
              <dd>{localizeValue(artifact.title ?? "未生成")}</dd>
            </div>
          <div>
            <dt>试听状态</dt>
            <dd>{artifact.audioUrl ? "已生成可播放片段" : "尚未生成音频"}</dd>
          </div>
          {"durationSeconds" in artifact ? (
            <div>
              <dt>时长</dt>
              <dd>{localizeValue(artifact.durationSeconds)} 秒</dd>
            </div>
          ) : null}
        </dl>
      </div>
    );
  }

  return <dl className="inspector-kv">{Object.entries(artifact).map(([key, value]) => (
    <div key={key}>
      <dt>{fieldLabel(key)}</dt>
      <dd>{renderArtifactValue(value)}</dd>
    </div>
  ))}</dl>;
}

function displayStageName(stage: TaskSnapshot["currentStage"]): string {
  if (stage === "completed") return "已完成";
  return STAGE_LABELS[stage];
}

function App() {
  const [uiState, dispatch] = useReducer(reducer, {
    mode: "seeded",
    selectedStage: "source_analysis",
    title: "",
    synopsis: "",
  });

  const createMutation = useMutation({
    mutationFn: createTask,
    onSuccess: () => dispatch({ type: "enter-user-workspace" }),
  });

  const taskId = createMutation.data?.taskId;

  const taskQuery = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => getTask(taskId!),
    enabled: Boolean(taskId),
    refetchInterval: (query) => {
      const snapshot = query.state.data;
      if (!snapshot) return 1500;
      return snapshot.status === "running" || snapshot.status === "queued" ? 1500 : false;
    },
  });

  const activeSnapshot = uiState.mode === "seeded" || !taskQuery.data ? SEEDED_EXAMPLE : taskQuery.data;

  const selectedStageArtifact = useMemo(
    () => activeSnapshot.stages[uiState.selectedStage].artifact,
    [activeSnapshot, uiState.selectedStage],
  );

  const isMobileFallback = typeof window !== "undefined" && window.innerWidth < 1024;

  if (isMobileFallback) {
    return (
      <main className="mobile-fallback">
        <p className="eyebrow">桌面优先</p>
        <h1>这个工作台推荐在桌面端打开</h1>
        <p>你仍然可以先了解产品：输入影视题材，系统会把题材拆成歌曲，并把每一步创作判断显示出来。</p>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <section className="top-strip">
        <div className="brand-block">
          <p className="eyebrow">影视灵感歌曲工作台</p>
          <h1>当前版本</h1>
          <p className="subtle">结果先出现，创作链立刻跟上。</p>
        </div>
        <form
          className="input-panel"
          onSubmit={(event) => {
            event.preventDefault();
            createMutation.mutate({ title: uiState.title, synopsis: uiState.synopsis });
          }}
        >
          <label>
            影视题材
            <input
              value={uiState.title}
              onChange={(event) => dispatch({ type: "set-title", value: event.target.value })}
              placeholder="输入电影或剧名"
            />
          </label>
          <label>
            剧情简介（可选）
            <textarea
              rows={3}
              value={uiState.synopsis}
              onChange={(event) => dispatch({ type: "set-synopsis", value: event.target.value })}
              placeholder="补一段剧情简介，能提高题材分析稳定性"
            />
          </label>
          <div className="button-row">
            <button className="primary" type="submit" disabled={createMutation.isPending || !uiState.title.trim()}>
              生成当前版本
            </button>
            <button type="button" className="ghost" onClick={() => dispatch({ type: "enter-user-workspace" })}>
              试试我的题材
            </button>
          </div>
          {createMutation.error ? <p className="error-text">任务创建失败，请稍后重试。</p> : null}
        </form>
      </section>

      <section className="hero-result">
        <div className="cover-card">
          {activeSnapshot.currentResult.coverUrl ? (
            <img src={activeSnapshot.currentResult.coverUrl} alt={activeSnapshot.currentResult.title ?? "封面"} />
          ) : (
            <div className="cover-placeholder">封面待生成</div>
          )}
        </div>
        <div className="result-body">
          <p className="eyebrow accent">{localizeValue(activeSnapshot.currentResult.activeStyle)}</p>
          <h2>{activeSnapshot.currentResult.title ?? "当前版本正在形成"}</h2>
          <p className="subtle">{activeSnapshot.input.title} · {TASK_STATUS_LABELS[activeSnapshot.status]}</p>
          {activeSnapshot.currentResult.audioUrl ? (
            <audio controls src={activeSnapshot.currentResult.audioUrl} />
          ) : (
            <div className="audio-placeholder">音频生成完成后会出现在这里</div>
          )}
        </div>
        <div className="status-panel">
          <div className="status-chip"><span>任务状态</span><strong>{TASK_STATUS_LABELS[activeSnapshot.status]}</strong></div>
          <div className="status-chip"><span>当前步骤</span><strong>{displayStageName(activeSnapshot.currentStage)}</strong></div>
          <div className="status-chip"><span>风格分支</span><strong>{localizeValue(activeSnapshot.currentResult.activeStyle)}</strong></div>
        </div>
      </section>

      <section className="workspace-grid">
        <section className="panel">
          <header className="panel-header">
            <h3>创作流程</h3>
            <p>左侧流程行，右侧步骤详情</p>
          </header>
          <div className="workflow-layout">
            <div className="workflow-list">
              {STAGE_ORDER.map((stage) => (
                <button
                  key={stage}
                  type="button"
                  className={`workflow-row ${uiState.selectedStage === stage ? "selected" : ""}`}
                  onClick={() => dispatch({ type: "select-stage", stage })}
                >
                  <div>
                    <strong>{STAGE_LABELS[stage]}</strong>
                    <p>{stageSummary(stage, activeSnapshot)}</p>
                  </div>
                  <span className={`state ${activeSnapshot.stages[stage].status}`}>{STAGE_STATUS_LABELS[activeSnapshot.stages[stage].status]}</span>
                </button>
              ))}
            </div>

            <aside className="inspector">
              <p className="eyebrow">步骤详情</p>
              <h4>{STAGE_LABELS[uiState.selectedStage]}</h4>
              {renderInspector(uiState.selectedStage, selectedStageArtifact)}
            </aside>
          </div>
        </section>
      </section>
    </main>
  );
}

export default App;
