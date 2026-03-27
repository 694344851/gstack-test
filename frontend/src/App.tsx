import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type StageStatus = "not_started" | "running" | "succeeded" | "failed";
type TaskStatus = "queued" | "running" | "failed" | "completed";
type StageName =
  | "source_analysis"
  | "lyric_plan"
  | "composition_brief"
  | "cover_direction"
  | "audio_render";
type AppSection = "workspace" | "library";
type WorkspaceMode = "seeded" | "user";
type LibraryScope = "works" | "trash";

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

type LibraryWork = {
  id: string;
  title: string;
  coverUrl: string;
  sourceTitle: string;
  createdAt: string;
  activeStyle: string;
  hasAudio: boolean;
  deletedAt: string | null;
};

type LibraryWorkDetail = {
  id: string;
  title: string;
  coverUrl: string | null;
  sourceTitle: string;
  createdAt: string;
  updatedAt: string;
  activeStyle: string;
  hasAudio: boolean;
  isTrashed: boolean;
  deletedAt: string | null;
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
};

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

async function parseError(response: Response, fallback: string) {
  try {
    const data = (await response.json()) as { detail?: string };
    return data.detail ?? fallback;
  } catch {
    return fallback;
  }
}

async function createTask(payload: { title: string; synopsis: string }) {
  const response = await fetch(`${API_BASE}/generation-tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await parseError(response, "任务创建失败"));
  }
  return (await response.json()) as { taskId: string; snapshot: TaskSnapshot };
}

async function getTask(taskId: string) {
  const response = await fetch(`${API_BASE}/generation-tasks/${taskId}`);
  if (!response.ok) {
    throw new Error(await parseError(response, "任务查询失败"));
  }
  return (await response.json()) as TaskSnapshot;
}

function taskSnapshotToLibraryDetail(snapshot: TaskSnapshot): LibraryWorkDetail {
  return {
    id: snapshot.id,
    title: snapshot.currentResult.title ?? "未命名作品",
    coverUrl: snapshot.currentResult.coverUrl,
    sourceTitle: snapshot.input.title,
    createdAt: snapshot.createdAt ?? "",
    updatedAt: snapshot.updatedAt ?? snapshot.createdAt ?? "",
    activeStyle: snapshot.currentResult.activeStyle,
    hasAudio: Boolean(snapshot.currentResult.audioUrl),
    isTrashed: false,
    deletedAt: null,
    input: snapshot.input,
    stages: snapshot.stages,
    currentResult: snapshot.currentResult,
  };
}

async function getLibraryWorks() {
  const response = await fetch(`${API_BASE}/library/works`);
  if (!response.ok) {
    throw new Error(await parseError(response, "作品库加载失败"));
  }
  return (await response.json()) as LibraryWork[];
}

async function getTrashWorks() {
  const response = await fetch(`${API_BASE}/library/trash`);
  if (!response.ok) {
    throw new Error(await parseError(response, "垃圾箱加载失败"));
  }
  return (await response.json()) as LibraryWork[];
}

async function getLibraryWorkDetail(taskId: string) {
  const response = await fetch(`${API_BASE}/library/works/${taskId}`);
  if (response.status === 404) {
    // 兼容尚未重启到新详情接口的本地后端进程，回退到已有任务快照接口。
    return taskSnapshotToLibraryDetail(await getTask(taskId));
  }
  if (!response.ok) {
    throw new Error(await parseError(response, "作品详情加载失败"));
  }
  return (await response.json()) as LibraryWorkDetail;
}

async function renameLibraryWork(payload: { id: string; title: string }) {
  const response = await fetch(`${API_BASE}/library/works/${payload.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: payload.title }),
  });
  if (!response.ok) {
    throw new Error(await parseError(response, "作品重命名失败"));
  }
  return (await response.json()) as LibraryWorkDetail;
}

async function trashLibraryWork(id: string) {
  const response = await fetch(`${API_BASE}/library/works/${id}/trash`, { method: "POST" });
  if (!response.ok) {
    throw new Error(await parseError(response, "移入垃圾箱失败"));
  }
  return (await response.json()) as LibraryWorkDetail;
}

async function restoreLibraryWork(id: string) {
  const response = await fetch(`${API_BASE}/library/works/${id}/restore`, { method: "POST" });
  if (!response.ok) {
    throw new Error(await parseError(response, "恢复作品失败"));
  }
  return (await response.json()) as LibraryWorkDetail;
}

async function permanentlyDeleteLibraryWork(id: string) {
  const response = await fetch(`${API_BASE}/library/works/${id}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error(await parseError(response, "彻底删除失败"));
  }
  return (await response.json()) as { ok: true };
}

function stageSummary(stage: StageName, snapshot: { stages: Record<StageName, StageSnapshot> }): string {
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
      return "当前步骤还没有产出内容";
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

function formatTimestamp(value: string): string {
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(timestamp);
}

function renderArtifactValue(value: unknown) {
  if (Array.isArray(value)) {
    return (
      <ul className="inspector-list">
        {value.map((item, index) => (
          <li key={`${index}-${String(item)}`}>
            {typeof item === "object" && item !== null ? renderArtifactValue(item) : localizeValue(item)}
          </li>
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

  return (
    <dl className="inspector-kv">
      {Object.entries(artifact).map(([key, value]) => (
        <div key={key}>
          <dt>{fieldLabel(key)}</dt>
          <dd>{renderArtifactValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function displayStageName(stage: TaskSnapshot["currentStage"]): string {
  if (stage === "completed") return "已完成";
  return STAGE_LABELS[stage];
}

function firstAvailableStage(stages: Record<StageName, StageSnapshot>): StageName {
  return STAGE_ORDER.find((stage) => stages[stage].artifact) ?? STAGE_ORDER[0];
}

function ScopeToggle({
  scope,
  activeCount,
  trashCount,
  onChange,
}: {
  scope: LibraryScope;
  activeCount: number;
  trashCount: number;
  onChange: (scope: LibraryScope) => void;
}) {
  return (
    <div className="scope-toggle" role="tablist" aria-label="作品范围切换">
      <button
        type="button"
        role="tab"
        aria-selected={scope === "works"}
        className={scope === "works" ? "selected" : ""}
        onClick={() => onChange("works")}
      >
        全部作品 <span>{activeCount}</span>
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={scope === "trash"}
        className={scope === "trash" ? "selected" : ""}
        onClick={() => onChange("trash")}
      >
        垃圾箱 <span>{trashCount}</span>
      </button>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="library-modal-shell" aria-label="作品详情加载中">
      <section className="library-master-strip skeleton-block">
        <div className="modal-cover skeleton" />
        <div className="master-copy">
          <div className="ghost-line long" />
          <div className="ghost-line medium" />
          <div className="ghost-line short" />
        </div>
        <div className="master-actions">
          <div className="ghost-line short" />
          <div className="ghost-line short" />
        </div>
      </section>
      <section className="library-modal-body">
        <div className="workflow-list">
          {STAGE_ORDER.map((stage) => (
            <div key={stage} className="workflow-row skeleton-block">
              <div>
                <strong>{STAGE_LABELS[stage]}</strong>
                <p>加载中</p>
              </div>
            </div>
          ))}
        </div>
        <aside className="inspector">
          <div className="ghost-line long" />
          <div className="ghost-line medium" />
          <div className="ghost-line long" />
        </aside>
      </section>
    </div>
  );
}

function App() {
  const queryClient = useQueryClient();
  const [section, setSection] = useState<AppSection>("workspace");
  const [mode, setMode] = useState<WorkspaceMode>("seeded");
  const [selectedStage, setSelectedStage] = useState<StageName>("source_analysis");
  const [title, setTitle] = useState("");
  const [synopsis, setSynopsis] = useState("");
  const [libraryScope, setLibraryScope] = useState<LibraryScope>("works");
  const [detailWorkId, setDetailWorkId] = useState<string | null>(null);
  const [detailStage, setDetailStage] = useState<StageName>("source_analysis");
  const [renameDraft, setRenameDraft] = useState("");
  const [isRenameMode, setIsRenameMode] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const createMutation = useMutation({
    mutationFn: createTask,
    onSuccess: () => {
      setMode("user");
      setSection("workspace");
    },
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

  const worksQuery = useQuery({
    queryKey: ["library-works"],
    queryFn: getLibraryWorks,
    enabled: section === "library",
  });

  const trashQuery = useQuery({
    queryKey: ["library-trash"],
    queryFn: getTrashWorks,
    enabled: section === "library",
  });

  const detailQuery = useQuery({
    queryKey: ["library-work", detailWorkId],
    queryFn: () => getLibraryWorkDetail(detailWorkId!),
    enabled: section === "library" && Boolean(detailWorkId),
  });

  useEffect(() => {
    if (!detailQuery.data) return;
    setDetailStage(firstAvailableStage(detailQuery.data.stages));
    setRenameDraft(detailQuery.data.title);
    setIsRenameMode(false);
    setIsDeleteConfirmOpen(false);
  }, [detailQuery.data?.id]);

  useEffect(() => {
    if (!detailWorkId) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (isDeleteConfirmOpen) {
        setIsDeleteConfirmOpen(false);
        return;
      }
      setDetailWorkId(null);
      setIsRenameMode(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [detailWorkId, isDeleteConfirmOpen]);

  const activeSnapshot = mode === "seeded" || !taskQuery.data ? SEEDED_EXAMPLE : taskQuery.data;
  const selectedStageArtifact = useMemo(
    () => activeSnapshot.stages[selectedStage].artifact,
    [activeSnapshot, selectedStage],
  );

  const activeCount = worksQuery.data?.length ?? 0;
  const trashCount = trashQuery.data?.length ?? 0;
  const currentLibraryList = libraryScope === "works" ? worksQuery.data : trashQuery.data;
  const currentLibraryError = libraryScope === "works" ? worksQuery.error : trashQuery.error;
  const currentLibraryLoading = libraryScope === "works" ? worksQuery.isLoading : trashQuery.isLoading;

  const invalidateLibraryQueries = async (id?: string) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["library-works"] }),
      queryClient.invalidateQueries({ queryKey: ["library-trash"] }),
      id ? queryClient.invalidateQueries({ queryKey: ["library-work", id] }) : Promise.resolve(),
    ]);
  };

  const renameMutation = useMutation({
    mutationFn: renameLibraryWork,
    onSuccess: async (detail) => {
      queryClient.setQueryData(["library-work", detail.id], detail);
      await invalidateLibraryQueries(detail.id);
      setRenameDraft(detail.title);
      setIsRenameMode(false);
    },
  });

  const trashMutation = useMutation({
    mutationFn: trashLibraryWork,
    onSuccess: async (detail) => {
      await invalidateLibraryQueries(detail.id);
      setDetailWorkId(null);
      setIsDeleteConfirmOpen(false);
      setFeedback("已移入垃圾箱，可恢复");
    },
  });

  const restoreMutation = useMutation({
    mutationFn: restoreLibraryWork,
    onSuccess: async (detail) => {
      await invalidateLibraryQueries(detail.id);
      setDetailWorkId(null);
      setIsDeleteConfirmOpen(false);
      setFeedback("已恢复到作品库");
    },
  });

  const permanentDeleteMutation = useMutation({
    mutationFn: permanentlyDeleteLibraryWork,
    onSuccess: async (_, id) => {
      await invalidateLibraryQueries(id);
      queryClient.removeQueries({ queryKey: ["library-work", id] });
      setDetailWorkId(null);
      setIsDeleteConfirmOpen(false);
      setFeedback("作品已彻底删除");
    },
  });

  const detailStageArtifact = detailQuery.data?.stages[detailStage].artifact ?? null;
  const detailBusy =
    renameMutation.isPending || trashMutation.isPending || restoreMutation.isPending || permanentDeleteMutation.isPending;

  const playDetailAudio = async () => {
    if (!audioRef.current) return;
    try {
      await audioRef.current.play();
    } catch {
      // 浏览器阻止自动播放时，保持静默，仍允许用户直接点原生控件。
    }
  };

  const closeDetail = () => {
    setDetailWorkId(null);
    setIsRenameMode(false);
    setIsDeleteConfirmOpen(false);
  };

  const renderLibraryEmpty = () => {
    if (libraryScope === "trash") {
      return (
        <section className="panel library-empty-state">
          <p className="eyebrow">垃圾箱</p>
          <h3>现在这里是空的。</h3>
          <p className="subtle">移入垃圾箱的作品会先存放在这里，之后仍可恢复回作品库。</p>
        </section>
      );
    }
    return (
      <section className="panel library-empty">
        <div className="library-empty-copy">
          <p className="eyebrow">作品库还是空的</p>
          <h3>先生成第一首作品，这里才会开始像作品集。</h3>
          <p className="subtle">完成生成后的作品会自动进入这里，按时间整理成可回看的卡片墙。</p>
          <button
            type="button"
            className="primary inline-action"
            onClick={() => {
              setSection("workspace");
              setMode("user");
            }}
          >
            去生成第一首作品
          </button>
        </div>
        <div className="library-ghost-grid" aria-hidden="true">
          {Array.from({ length: 3 }).map((_, index) => (
            <article key={index} className="ghost-card">
              <div className="ghost-thumb" />
              <div className="ghost-line long" />
              <div className="ghost-line medium" />
              <div className="ghost-line short" />
            </article>
          ))}
        </div>
      </section>
    );
  };

  return (
    <Fragment>
      <main className="studio-shell">
        <aside className="side-rail">
          <nav className="side-nav" aria-label="主导航">
            <button
              type="button"
              className={section === "workspace" ? "selected" : ""}
              onClick={() => setSection("workspace")}
            >
              <span>当前创作</span>
              <strong>{mode === "seeded" ? "示例模式" : "进行中"}</strong>
            </button>
            <button
              type="button"
              className={section === "library" ? "selected" : ""}
              onClick={() => setSection("library")}
            >
              <span>我的作品库</span>
              <strong>{section === "library" ? `${activeCount} 首作品` : "作品目录"}</strong>
            </button>
          </nav>
        </aside>

        <section className="app-shell">
          {section === "workspace" ? (
            <>
              <section className="workspace-stage">
                <form
                  className="input-panel"
                  onSubmit={(event) => {
                    event.preventDefault();
                    createMutation.mutate({ title, synopsis });
                  }}
                >
                  <label>
                    影视题材
                    <input
                      value={title}
                      onChange={(event) => setTitle(event.target.value)}
                      placeholder="输入电影或剧名"
                    />
                  </label>
                  <label>
                    剧情简介（可选）
                    <textarea
                      rows={3}
                      value={synopsis}
                      onChange={(event) => setSynopsis(event.target.value)}
                      placeholder="补一段剧情简介，能提高题材分析稳定性"
                    />
                  </label>
                  <div className="button-row">
                    <button className="primary" type="submit" disabled={createMutation.isPending || !title.trim()}>
                      生成当前版本
                    </button>
                    <button
                      type="button"
                      className="ghost"
                      onClick={() => {
                        setMode("user");
                        setSection("workspace");
                      }}
                    >
                      试试我的题材
                    </button>
                  </div>
                  {createMutation.error ? (
                    <p className="error-text">{(createMutation.error as Error).message}</p>
                  ) : null}
                </form>

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
                    <p className="subtle">
                      {activeSnapshot.input.title} · {TASK_STATUS_LABELS[activeSnapshot.status]}
                    </p>
                    {activeSnapshot.currentResult.audioUrl ? (
                      <audio controls src={activeSnapshot.currentResult.audioUrl} />
                    ) : (
                      <div className="audio-placeholder">音频生成完成后会出现在这里</div>
                    )}
                  </div>
                  <div className="status-panel">
                    <div className="status-chip">
                      <span>任务状态</span>
                      <strong>{TASK_STATUS_LABELS[activeSnapshot.status]}</strong>
                    </div>
                    <div className="status-chip">
                      <span>当前步骤</span>
                      <strong>{displayStageName(activeSnapshot.currentStage)}</strong>
                    </div>
                    <div className="status-chip">
                      <span>风格分支</span>
                      <strong>{localizeValue(activeSnapshot.currentResult.activeStyle)}</strong>
                    </div>
                  </div>
                </section>
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
                          className={`workflow-row ${selectedStage === stage ? "selected" : ""}`}
                          onClick={() => setSelectedStage(stage)}
                        >
                          <div>
                            <strong>{STAGE_LABELS[stage]}</strong>
                            <p>{stageSummary(stage, activeSnapshot)}</p>
                          </div>
                          <span className={`state ${activeSnapshot.stages[stage].status}`}>
                            {STAGE_STATUS_LABELS[activeSnapshot.stages[stage].status]}
                          </span>
                        </button>
                      ))}
                    </div>

                    <aside className="inspector">
                      <p className="eyebrow">步骤详情</p>
                      <h4>{STAGE_LABELS[selectedStage]}</h4>
                      {renderInspector(selectedStage, selectedStageArtifact)}
                    </aside>
                  </div>
                </section>
              </section>
            </>
          ) : (
            <>
              <section className="library-overview">
                <div className="library-copy panel">
                  <p className="eyebrow">我的作品库</p>
                  <h2>每首作品都可以被播放、重命名、移动到垃圾箱，或继续查看每个创作节点。</h2>
                  <p className="subtle">结果优先呈现，删除先进垃圾箱，作品仍然保留完整的节点剖面与恢复入口。</p>
                </div>
                <div className="library-summary panel">
                  <p className="eyebrow accent">Library Snapshot</p>
                  <strong>{activeCount} 首作品</strong>
                  <p className="subtle">{trashCount} 首在垃圾箱中，恢复后会重新回到主目录。</p>
                </div>
              </section>

              <section className="library-headline panel">
                <div>
                  <p className="eyebrow">我的作品库</p>
                  <h3>{libraryScope === "works" ? "全部作品" : "垃圾箱"}</h3>
                  <p className="subtle">
                    {libraryScope === "works"
                      ? "已完成的作品按最新生成时间排序，点击卡片可进入作品详情。"
                      : "移入垃圾箱的作品会先存放在这里，可恢复，也可彻底删除。"}
                  </p>
                </div>
                <ScopeToggle
                  scope={libraryScope}
                  activeCount={activeCount}
                  trashCount={trashCount}
                  onChange={setLibraryScope}
                />
              </section>

              {feedback ? (
                <section className="panel library-feedback" role="status">
                  <p>{feedback}</p>
                  <button type="button" className="text-action" onClick={() => setFeedback(null)}>
                    关闭提示
                  </button>
                </section>
              ) : null}

              {currentLibraryError ? (
                <section className="panel">
                  <p className="eyebrow">作品库异常</p>
                  <h3>{libraryScope === "works" ? "作品列表暂时没有加载出来" : "垃圾箱暂时没有加载出来"}</h3>
                  <p className="error-text">{(currentLibraryError as Error).message}</p>
                </section>
              ) : null}

              {currentLibraryLoading ? (
                <section className="library-grid" aria-label="作品加载中">
                  {Array.from({ length: 6 }).map((_, index) => (
                    <article key={index} className="library-card loading">
                      <div className="library-card-media skeleton" />
                      <div className="library-card-body">
                        <div className="ghost-line long" />
                        <div className="ghost-line medium" />
                        <div className="ghost-line short" />
                      </div>
                    </article>
                  ))}
                </section>
              ) : null}

              {!currentLibraryLoading && !currentLibraryError && currentLibraryList?.length ? (
                <section className="library-grid" aria-label={libraryScope === "works" ? "作品卡片墙" : "垃圾箱卡片墙"}>
                  {currentLibraryList.map((work) => (
                    <button
                      key={work.id}
                      type="button"
                      className="library-card library-card-button"
                      onClick={() => setDetailWorkId(work.id)}
                    >
                      <div className="library-card-media">
                        <img src={work.coverUrl} alt={work.title} />
                      </div>
                      <div className="library-card-body">
                        <p className="eyebrow accent">{localizeValue(work.activeStyle)}</p>
                        <h3>{work.title}</h3>
                        <dl className="library-meta">
                          <div>
                            <dt>生成来源</dt>
                            <dd>{work.sourceTitle}</dd>
                          </div>
                          <div>
                            <dt>{libraryScope === "works" ? "生成时间" : "删除时间"}</dt>
                            <dd>{formatTimestamp(libraryScope === "works" ? work.createdAt : work.deletedAt ?? work.createdAt)}</dd>
                          </div>
                        </dl>
                        <div className="library-card-footer">
                          <span>{work.hasAudio ? "可播放试听" : "仅保留作品记录"}</span>
                          <span>{libraryScope === "works" ? "查看节点详情" : "可恢复或彻底删除"}</span>
                        </div>
                      </div>
                    </button>
                  ))}
                </section>
              ) : null}

              {!currentLibraryLoading && !currentLibraryError && !currentLibraryList?.length ? renderLibraryEmpty() : null}
            </>
          )}
        </section>
      </main>

      {detailWorkId ? (
        <div className="modal-backdrop" onClick={() => !detailBusy && closeDetail()}>
          <section
            className="library-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="library-modal-title"
            onClick={(event) => event.stopPropagation()}
          >
            {detailQuery.isLoading ? <DetailSkeleton /> : null}

            {detailQuery.isError ? (
              <div className="library-modal-shell">
                <section className="panel modal-error">
                  <p className="eyebrow">作品详情</p>
                  <h3>这首作品详情暂时打开失败</h3>
                  <p className="error-text">{(detailQuery.error as Error).message}</p>
                  <div className="modal-action-row">
                    <button type="button" className="ghost" onClick={closeDetail}>
                      关闭
                    </button>
                  </div>
                </section>
              </div>
            ) : null}

            {detailQuery.data ? (
              <div className="library-modal-shell">
                <section className="library-master-strip">
                  <div className="modal-cover">
                    {detailQuery.data.coverUrl ? (
                      <img src={detailQuery.data.coverUrl} alt={detailQuery.data.title} />
                    ) : (
                      <div className="cover-placeholder">封面待生成</div>
                    )}
                  </div>
                  <div className="master-copy">
                    <p className="eyebrow accent">
                      {detailQuery.data.isTrashed ? "垃圾箱作品" : localizeValue(detailQuery.data.activeStyle)}
                    </p>
                    {isRenameMode && !detailQuery.data.isTrashed ? (
                      <form
                        className="rename-form"
                        onSubmit={(event) => {
                          event.preventDefault();
                          renameMutation.mutate({ id: detailQuery.data!.id, title: renameDraft });
                        }}
                      >
                        <input
                          aria-label="作品标题"
                          value={renameDraft}
                          onChange={(event) => setRenameDraft(event.target.value)}
                          disabled={renameMutation.isPending}
                        />
                        <div className="inline-actions">
                          <button type="submit" className="primary" disabled={renameMutation.isPending}>
                            保存
                          </button>
                          <button
                            type="button"
                            className="ghost"
                            onClick={() => {
                              setIsRenameMode(false);
                              setRenameDraft(detailQuery.data!.title);
                            }}
                          >
                            取消
                          </button>
                        </div>
                      </form>
                    ) : (
                      <h2 id="library-modal-title">{detailQuery.data.title}</h2>
                    )}
                    <p className="subtle">
                      {detailQuery.data.sourceTitle} · 创建于 {formatTimestamp(detailQuery.data.createdAt)}
                    </p>
                    {detailQuery.data.deletedAt ? (
                      <p className="subtle">移入垃圾箱于 {formatTimestamp(detailQuery.data.deletedAt)}</p>
                    ) : null}
                    {detailQuery.data.currentResult.audioUrl ? (
                      <audio
                        ref={audioRef}
                        controls
                        src={detailQuery.data.currentResult.audioUrl}
                        className="detail-audio"
                      />
                    ) : (
                      <div className="audio-placeholder">当前作品还没有音频，但每个节点内容仍可查看。</div>
                    )}
                    {renameMutation.error ? (
                      <p className="error-text">{(renameMutation.error as Error).message}</p>
                    ) : null}
                  </div>
                  <div className="master-actions">
                    {detailQuery.data.isTrashed ? (
                      <>
                        <button
                          type="button"
                          className="primary"
                          onClick={() => restoreMutation.mutate(detailQuery.data!.id)}
                          disabled={detailBusy}
                        >
                          恢复
                        </button>
                        <button
                          type="button"
                          className="danger"
                          onClick={() => setIsDeleteConfirmOpen(true)}
                          disabled={detailBusy}
                        >
                          彻底删除
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          type="button"
                          className="primary"
                          onClick={playDetailAudio}
                          disabled={!detailQuery.data.currentResult.audioUrl}
                        >
                          播放
                        </button>
                        <button
                          type="button"
                          className="ghost"
                          onClick={() => {
                            setIsRenameMode(true);
                            setRenameDraft(detailQuery.data!.title);
                          }}
                          disabled={detailBusy}
                        >
                          重命名
                        </button>
                        <button
                          type="button"
                          className="danger"
                          onClick={() => setIsDeleteConfirmOpen(true)}
                          disabled={detailBusy}
                        >
                          删除到垃圾箱
                        </button>
                      </>
                    )}
                    <button type="button" className="ghost icon-button" onClick={closeDetail} disabled={detailBusy}>
                      关闭
                    </button>
                  </div>
                </section>

                <section className="library-modal-body">
                  <div className="workflow-list">
                    {STAGE_ORDER.map((stage) => (
                      <button
                        key={stage}
                        type="button"
                        className={`workflow-row ${detailStage === stage ? "selected" : ""}`}
                        onClick={() => setDetailStage(stage)}
                      >
                        <div>
                          <strong>{STAGE_LABELS[stage]}</strong>
                          <p>{stageSummary(stage, detailQuery.data!)}</p>
                        </div>
                        <span className={`state ${detailQuery.data!.stages[stage].status}`}>
                          {STAGE_STATUS_LABELS[detailQuery.data!.stages[stage].status]}
                        </span>
                      </button>
                    ))}
                  </div>

                  <aside className="inspector">
                    <p className="eyebrow">节点详情</p>
                    <h4>{STAGE_LABELS[detailStage]}</h4>
                    {renderInspector(detailStage, detailStageArtifact)}
                  </aside>
                </section>

                {isDeleteConfirmOpen ? (
                  <div className="confirm-layer" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title">
                    <div className="confirm-card">
                      <p className="eyebrow accent">危险操作</p>
                      <h3 id="confirm-title">
                        {detailQuery.data.isTrashed ? "彻底删除这首作品？" : "把这首作品移入垃圾箱？"}
                      </h3>
                      {detailQuery.data.isTrashed ? (
                        <p className="subtle">彻底删除后，作品和所有创作节点都会消失，之后无法恢复。</p>
                      ) : (
                        <p className="subtle">作品会从作品库移入垃圾箱，创作节点内容暂时保留，之后仍可恢复。</p>
                      )}
                      {(trashMutation.error || permanentDeleteMutation.error) ? (
                        <p className="error-text">
                          {((trashMutation.error ?? permanentDeleteMutation.error) as Error).message}
                        </p>
                      ) : null}
                      <div className="modal-action-row">
                        <button type="button" className="ghost" onClick={() => setIsDeleteConfirmOpen(false)}>
                          取消
                        </button>
                        <button
                          type="button"
                          className="danger"
                          onClick={() =>
                            detailQuery.data!.isTrashed
                              ? permanentDeleteMutation.mutate(detailQuery.data!.id)
                              : trashMutation.mutate(detailQuery.data!.id)
                          }
                          disabled={detailBusy}
                        >
                          {detailQuery.data.isTrashed ? "确认彻底删除" : "确认移入垃圾箱"}
                        </button>
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </section>
        </div>
      ) : null}

      <main className="mobile-fallback">
        <p className="eyebrow">桌面优先</p>
        <h1>这个工作台推荐在更宽的窗口里打开</h1>
        <p>当前窗口太窄时，完整创作界面会收成简化视图。把浏览器再拉宽一点，就能继续使用完整工作台。</p>
      </main>
    </Fragment>
  );
}

export default App;
