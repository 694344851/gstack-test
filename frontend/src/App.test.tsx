import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

type StageName =
  | "source_analysis"
  | "lyric_plan"
  | "composition_brief"
  | "cover_direction"
  | "audio_render";

type StageSnapshot = {
  status: "not_started" | "running" | "succeeded" | "failed";
  artifact: Record<string, unknown> | null;
};

type Card = {
  id: string;
  title: string;
  coverUrl: string | null;
  sourceTitle: string;
  createdAt: string;
  activeStyle: string;
  currentHighlight: string | null;
  hasAudio: boolean;
  deletedAt: string | null;
};

type Detail = {
  id: string;
  title: string;
  coverUrl: string | null;
  sourceTitle: string;
  createdAt: string;
  updatedAt: string;
  activeStyle: string;
  currentHighlight: string | null;
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
    currentHighlight: string | null;
  };
};

function createDetail(id: string, title: string, options?: Partial<Detail>): Detail {
  return {
    id,
    title,
    coverUrl: `https://example.com/${id}.jpg`,
    sourceTitle: options?.sourceTitle ?? "哪吒",
    createdAt: "2026-03-26T08:00:00+00:00",
    updatedAt: "2026-03-26T08:00:00+00:00",
    activeStyle: "电影流行",
    hasAudio: true,
    isTrashed: false,
    deletedAt: null,
    input: {
      title: options?.sourceTitle ?? "哪吒",
      synopsis: "一个反抗命运的故事",
    },
    stages: {
      source_analysis: {
        status: "succeeded",
        artifact: { summary: "识别出主要冲突" },
      },
      lyric_plan: {
        status: "succeeded",
        artifact: { concept: "副歌聚焦不认命" },
      },
      composition_brief: {
        status: "succeeded",
        artifact: { tempo: "92 BPM", key: "D Minor" },
      },
      cover_direction: {
        status: "succeeded",
        artifact: { coverTitle: title, visualConcept: "霓虹封面" },
      },
      audio_render: {
        status: "succeeded",
        artifact: {
          versionTitle: `${title}·导演说明版`,
          performanceDirection: "副歌需要明显抬升和宣告感。",
        },
      },
    },
    currentResult: {
      title,
      coverUrl: `https://example.com/${id}.jpg`,
      audioUrl: `https://example.com/${id}.mp3`,
      activeStyle: "电影流行",
      currentHighlight: "命可以压我一程，压不灭我这口气。",
    },
    currentHighlight: "命可以压我一程，压不灭我这口气。",
    ...options,
  };
}

function toCard(detail: Detail): Card {
  return {
    id: detail.id,
    title: detail.title,
    coverUrl: detail.coverUrl,
    sourceTitle: detail.sourceTitle,
    createdAt: detail.createdAt,
    activeStyle: detail.activeStyle,
    currentHighlight: detail.currentHighlight,
    hasAudio: detail.hasAudio,
    deletedAt: detail.deletedAt,
  };
}

function setupMockApi(initial: { active: Detail[]; trash?: Detail[] }) {
  let active = initial.active.map((item) => structuredClone(item));
  let trash = (initial.trash ?? []).map((item) => structuredClone(item));

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const pathname = new URL(url, "http://localhost").pathname;
    const method = init?.method ?? "GET";
    const json = (body: unknown, status = 200) =>
      Promise.resolve(
        new Response(JSON.stringify(body), {
          status,
          headers: { "Content-Type": "application/json" },
        }),
      );

    const detailId = pathname.match(/^\/library\/works\/([^/]+)$/)?.[1];
    const trashId = pathname.match(/^\/library\/works\/([^/]+)\/trash$/)?.[1];
    const restoreId = pathname.match(/^\/library\/works\/([^/]+)\/restore$/)?.[1];

    if (pathname === "/library/works" && method === "GET") return json(active.map(toCard));
    if (pathname === "/library/trash" && method === "GET") return json(trash.map(toCard));

    if (detailId && method === "GET") {
      const detail = active.concat(trash).find((item) => item.id === detailId);
      return detail ? json(detail) : json({ detail: "Work not found" }, 404);
    }

    if (detailId && method === "PATCH") {
      const payload = JSON.parse(String(init?.body ?? "{}")) as { title: string };
      const detail = active.find((item) => item.id === detailId);
      if (!detail) return json({ detail: "Cannot rename a trashed work" }, 400);
      detail.title = payload.title;
      detail.currentResult.title = payload.title;
      return json(detail);
    }

    if (trashId && method === "POST") {
      const detail = active.find((item) => item.id === trashId);
      if (!detail) return json({ detail: "Work not found" }, 404);
      active = active.filter((item) => item.id !== trashId);
      detail.isTrashed = true;
      detail.deletedAt = "2026-03-26T09:00:00+00:00";
      trash = [detail, ...trash];
      return json(detail);
    }

    if (restoreId && method === "POST") {
      const detail = trash.find((item) => item.id === restoreId);
      if (!detail) return json({ detail: "Work is not in trash" }, 400);
      trash = trash.filter((item) => item.id !== restoreId);
      detail.isTrashed = false;
      detail.deletedAt = null;
      active = [detail, ...active];
      return json(detail);
    }

    if (detailId && method === "DELETE") {
      trash = trash.filter((item) => item.id !== detailId);
      active = active.filter((item) => item.id !== detailId);
      return json({ ok: true });
    }

    return json({ detail: `Unhandled route: ${method} ${pathname}` }, 500);
  });

  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function setupFallbackDetailMock(detail: Detail) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    const pathname = new URL(url, "http://localhost").pathname;
    const json = (body: unknown, status = 200) =>
      Promise.resolve(
        new Response(JSON.stringify(body), {
          status,
          headers: { "Content-Type": "application/json" },
        }),
      );

    if (pathname === "/library/works") return json([toCard(detail)]);
    if (pathname === "/library/trash") return json([]);
    if (pathname === `/library/works/${detail.id}`) return json({ detail: "Not Found" }, 404);
    if (pathname === `/generation-tasks/${detail.id}`) {
      return json({
        id: detail.id,
        status: "completed",
        currentStage: "completed",
        input: detail.input,
        stages: detail.stages,
        currentResult: detail.currentResult,
        error: null,
        createdAt: detail.createdAt,
        updatedAt: detail.updatedAt,
      });
    }

    return json({ detail: `Unhandled route: ${pathname}` }, 500);
  });

  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function setupCreateFlowMock() {
  const createdSnapshot = {
    id: "task_created",
    status: "queued",
    currentStage: "source_analysis",
    input: {
      title: "流浪地球",
      synopsis: "一个关于存续与选择的故事",
    },
    stages: {
      source_analysis: { status: "not_started", artifact: null },
      lyric_plan: { status: "not_started", artifact: null },
      composition_brief: { status: "not_started", artifact: null },
      cover_direction: { status: "not_started", artifact: null },
      audio_render: { status: "not_started", artifact: null },
    },
    currentResult: {
      title: null,
      coverUrl: null,
      audioUrl: null,
      activeStyle: "创作工作台",
      currentHighlight: null,
    },
    error: null,
  };

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const pathname = new URL(url, "http://localhost").pathname;
    const method = init?.method ?? "GET";
    const json = (body: unknown, status = 200) =>
      Promise.resolve(
        new Response(JSON.stringify(body), {
          status,
          headers: { "Content-Type": "application/json" },
        }),
      );

    if (pathname === "/generation-tasks" && method === "POST") {
      return json({ taskId: "task_created", snapshot: createdSnapshot });
    }
    if (pathname === "/generation-tasks/task_created" && method === "GET") {
      return json({ detail: "Task query failed" }, 500);
    }
    if (pathname === "/library/works" && method === "GET") return json([]);
    if (pathname === "/library/trash" && method === "GET") return json([]);

    return json({ detail: `Unhandled route: ${method} ${pathname}` }, 500);
  });

  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
}

async function openLibrary() {
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: /我的作品库/i }));
  return user;
}

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("library modal flows", () => {
  it("opens detail modal and switches node inspector content", async () => {
    setupMockApi({
      active: [createDetail("work_1", "哪吒·逆光版")],
    });
    const user = userEvent.setup();
    renderApp();

    await user.click(screen.getByRole("button", { name: /我的作品库/i }));
    await user.click(await screen.findByRole("button", { name: /哪吒·逆光版/i }));

    const dialog = await screen.findByRole("dialog", { name: /哪吒·逆光版/i });
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByRole("heading", { name: "剧情提炼" })).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: /音频渲染/i }));

    expect(await within(dialog).findByText("当前阶段输出导演说明，尚未生成可播放音频。")).toBeInTheDocument();
    expect(within(dialog).getByText("哪吒·逆光版·导演说明版")).toBeInTheDocument();
  });

  it("renames a work inline and syncs modal plus card title", async () => {
    setupMockApi({
      active: [createDetail("work_1", "哪吒·逆光版")],
    });
    renderApp();
    const user = await openLibrary();

    await user.click(await screen.findByRole("button", { name: /哪吒·逆光版/i }));
    await user.click(await screen.findByRole("button", { name: "重命名" }));

    const input = screen.getByRole("textbox", { name: "作品标题" });
    await user.clear(input);
    await user.type(input, "哪吒·重命名版");
    await user.click(screen.getByRole("button", { name: "保存" }));

    const headings = await screen.findAllByRole("heading", { name: "哪吒·重命名版" });
    expect(headings.length).toBeGreaterThan(1);
    await waitFor(() => {
      expect(screen.getAllByText("哪吒·重命名版").length).toBeGreaterThan(1);
    });
  });

  it("moves a work to trash with confirm layer and shows trash empty guidance", async () => {
    setupMockApi({
      active: [createDetail("work_1", "哪吒·逆光版")],
      trash: [],
    });
    renderApp();
    const user = await openLibrary();

    await user.click(await screen.findByRole("button", { name: /哪吒·逆光版/i }));
    await user.click(await screen.findByRole("button", { name: "删除到垃圾箱" }));

    expect(await screen.findByRole("alertdialog", { name: /把这首作品移入垃圾箱/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "确认移入垃圾箱" }));

    expect(await screen.findByText("已移入垃圾箱，可恢复")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /垃圾箱/i }));
    expect(await screen.findByRole("button", { name: /哪吒·逆光版/i })).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: /全部作品/i }));
    expect(await screen.findByText(/先生成第一首作品，这里才会开始像作品集/)).toBeInTheDocument();
  });

  it("restores a trashed work from trash detail modal", async () => {
    setupMockApi({
      active: [],
      trash: [createDetail("work_2", "封神·夜航版", { isTrashed: true, deletedAt: "2026-03-26T09:00:00+00:00" })],
    });
    renderApp();
    const user = await openLibrary();

    await user.click(screen.getByRole("tab", { name: /垃圾箱/i }));
    await user.click(await screen.findByRole("button", { name: /封神·夜航版/i }));
    await user.click(await screen.findByRole("button", { name: "恢复" }));

    expect(await screen.findByText("已恢复到作品库")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /全部作品/i }));
    expect(await screen.findByRole("button", { name: /封神·夜航版/i })).toBeInTheDocument();
  });

  it("falls back to generation task detail when the library detail endpoint is unavailable", async () => {
    setupFallbackDetailMock(createDetail("work_fallback", "黑客帝国·逆光版"));
    renderApp();
    const user = await openLibrary();

    await user.click(await screen.findByRole("button", { name: /黑客帝国·逆光版/i }));

    const dialog = await screen.findByRole("dialog", { name: /黑客帝国·逆光版/i });
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByRole("heading", { name: "剧情提炼" })).toBeInTheDocument();
  });

  it("keeps showing the created task snapshot instead of seeded mock data when polling fails", async () => {
    setupCreateFlowMock();
    renderApp();
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "试试我的题材" }));
    await user.type(screen.getByLabelText("影视题材"), "流浪地球");
    await user.type(screen.getByLabelText("剧情简介（可选）"), "一个关于存续与选择的故事");
    await user.click(screen.getByRole("button", { name: "生成当前版本" }));

    expect(await screen.findByText("流浪地球 · 排队中")).toBeInTheDocument();
    expect(screen.getByText(/Task query failed。当前先显示本地任务草稿，不再回退到示例数据/)).toBeInTheDocument();
    expect(screen.queryByText("哪吒·逆光版")).not.toBeInTheDocument();
  });
});
