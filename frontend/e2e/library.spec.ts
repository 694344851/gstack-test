import { expect, test } from "@playwright/test";

type Detail = {
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
  stages: Record<string, { status: string; artifact: Record<string, unknown> | null }>;
  currentResult: {
    title: string | null;
    coverUrl: string | null;
    audioUrl: string | null;
    activeStyle: string;
  };
};

function createDetail(id: string, title: string, overrides?: Partial<Detail>): Detail {
  return {
    id,
    title,
    coverUrl: `https://example.com/${id}.jpg`,
    sourceTitle: overrides?.sourceTitle ?? "哪吒",
    createdAt: "2026-03-26T08:00:00+00:00",
    updatedAt: "2026-03-26T08:00:00+00:00",
    activeStyle: "电影流行",
    hasAudio: true,
    isTrashed: false,
    deletedAt: null,
    input: { title: overrides?.sourceTitle ?? "哪吒", synopsis: "一个反抗命运的故事" },
    stages: {
      source_analysis: { status: "succeeded", artifact: { summary: "识别出主要冲突" } },
      lyric_plan: { status: "succeeded", artifact: { concept: "副歌聚焦不认命" } },
      composition_brief: { status: "succeeded", artifact: { bpm: 92, key: "D Minor" } },
      cover_direction: {
        status: "succeeded",
        artifact: { artDirection: "霓虹封面", titleLock: title, coverUrl: `https://example.com/${id}.jpg` },
      },
      audio_render: {
        status: "succeeded",
        artifact: { title: `${title}·原始音频标题`, audioUrl: `https://example.com/${id}.mp3`, durationSeconds: 24 },
      },
    },
    currentResult: {
      title,
      coverUrl: `https://example.com/${id}.jpg`,
      audioUrl: `https://example.com/${id}.mp3`,
      activeStyle: "电影流行",
    },
    ...overrides,
  };
}

function toCard(detail: Detail) {
  return {
    id: detail.id,
    title: detail.title,
    coverUrl: detail.coverUrl,
    sourceTitle: detail.sourceTitle,
    createdAt: detail.createdAt,
    activeStyle: detail.activeStyle,
    hasAudio: detail.hasAudio,
    deletedAt: detail.deletedAt,
  };
}

async function mockLibraryApi(
  page: Parameters<typeof test.beforeEach>[0]["page"],
  initial: { active: Detail[]; trash?: Detail[] },
) {
  let active = initial.active.map((item) => structuredClone(item));
  let trash = (initial.trash ?? []).map((item) => structuredClone(item));

  await page.route("http://localhost:8000/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname;
    const method = request.method();
    const detailId = pathname.match(/^\/library\/works\/([^/]+)$/)?.[1];
    const trashId = pathname.match(/^\/library\/works\/([^/]+)\/trash$/)?.[1];
    const restoreId = pathname.match(/^\/library\/works\/([^/]+)\/restore$/)?.[1];

    const fulfill = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(body),
      });

    if (pathname === "/library/works" && method === "GET") return fulfill(active.map(toCard));
    if (pathname === "/library/trash" && method === "GET") return fulfill(trash.map(toCard));

    if (detailId && method === "GET") {
      const detail = active.concat(trash).find((item) => item.id === detailId);
      return detail ? fulfill(detail) : fulfill({ detail: "Work not found" }, 404);
    }

    if (detailId && method === "PATCH") {
      const payload = request.postDataJSON() as { title: string };
      const detail = active.find((item) => item.id === detailId);
      if (!detail) return fulfill({ detail: "Cannot rename a trashed work" }, 400);
      detail.title = payload.title;
      detail.currentResult.title = payload.title;
      return fulfill(detail);
    }

    if (trashId && method === "POST") {
      const detail = active.find((item) => item.id === trashId);
      if (!detail) return fulfill({ detail: "Work not found" }, 404);
      active = active.filter((item) => item.id !== trashId);
      detail.isTrashed = true;
      detail.deletedAt = "2026-03-26T09:00:00+00:00";
      trash = [detail, ...trash];
      return fulfill(detail);
    }

    if (restoreId && method === "POST") {
      const detail = trash.find((item) => item.id === restoreId);
      if (!detail) return fulfill({ detail: "Work is not in trash" }, 400);
      trash = trash.filter((item) => item.id !== restoreId);
      detail.isTrashed = false;
      detail.deletedAt = null;
      active = [detail, ...active];
      return fulfill(detail);
    }

    if (detailId && method === "DELETE") {
      trash = trash.filter((item) => item.id !== detailId);
      active = active.filter((item) => item.id !== detailId);
      return fulfill({ ok: true });
    }

    return fulfill({ detail: `Unhandled route: ${method} ${pathname}` }, 500);
  });
}

test("active work can be moved into trash", async ({ page }) => {
  await mockLibraryApi(page, {
    active: [createDetail("work_1", "哪吒·逆光版")],
    trash: [],
  });

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /我的作品库/i }).click();
  await page.getByRole("button", { name: /哪吒·逆光版/i }).click();
  await page.getByRole("button", { name: "删除到垃圾箱" }).click();
  await page.getByRole("button", { name: "确认移入垃圾箱" }).click();

  await expect(page.getByText("已移入垃圾箱，可恢复")).toBeVisible();
  await page.getByRole("tab", { name: /垃圾箱/i }).click();
  await expect(page.getByRole("button", { name: /哪吒·逆光版/i })).toBeVisible();
});

test("trashed work can be restored to active library", async ({ page }) => {
  await mockLibraryApi(page, {
    active: [],
    trash: [createDetail("work_2", "封神·夜航版", { isTrashed: true, deletedAt: "2026-03-26T09:00:00+00:00" })],
  });

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /我的作品库/i }).click();
  await page.getByRole("tab", { name: /垃圾箱/i }).click();
  await page.getByRole("button", { name: /封神·夜航版/i }).click();
  await page.getByRole("dialog", { name: /封神·夜航版/i }).getByRole("button", { name: "恢复" }).click();

  await expect(page.getByText("已恢复到作品库")).toBeVisible();
  await page.getByRole("tab", { name: /全部作品/i }).click();
  await expect(page.getByRole("button", { name: /封神·夜航版/i })).toBeVisible();
});

test("permanently deleted work becomes unreachable", async ({ page }) => {
  await mockLibraryApi(page, {
    active: [],
    trash: [createDetail("work_3", "流浪地球·引擎版", { isTrashed: true, deletedAt: "2026-03-26T09:00:00+00:00" })],
  });

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /我的作品库/i }).click();
  await page.getByRole("tab", { name: /垃圾箱/i }).click();
  await page.getByRole("button", { name: /流浪地球·引擎版/i }).click();
  await page.getByRole("dialog", { name: /流浪地球·引擎版/i }).getByRole("button", { name: "彻底删除" }).click();
  await page.getByRole("dialog", { name: /流浪地球·引擎版/i }).getByRole("button", { name: "确认彻底删除" }).click();

  await expect(page.getByRole("button", { name: /流浪地球·引擎版/i })).toHaveCount(0);

  const status = await page.evaluate(async () => {
    const response = await fetch("http://localhost:8000/library/works/work_3");
    return response.status;
  });
  expect(status).toBe(404);
});
