# Design System — Visual Movie-to-Song Release Workflow

## Product Context
- **What this is:** 一个桌面端中文 Web 创作工作台。用户输入电影、剧集或故事题材，系统把题材转化为歌曲，并把题材理解、歌词结构、编曲判断、封面和结果做成可见推导链。
- **Who it's for:** 音乐制作爱好者、偏创作型用户、愿意看过程和改过程的人。
- **Space/industry:** AI 音乐创作 / 音乐制作工具 / 影视题材二次创作。
- **Project type:** 桌面优先的专业工作台型 Web App。

## Aesthetic Direction
- **Direction:** 深夜电影配乐控制台
- **Decoration level:** intentional
- **Mood:** 整体气质应该像专业录音棚里的控制台，而不是娱乐平台或聊天工具。第一眼要让人觉得“这里已经在出声，而且我能控制它”，而不是“这里会帮我想一个答案”。
- **Reference sites:** https://www.ableton.com/en/live/create/ , https://suno.com/blog/suno-studio , https://help.udio.com/en/articles/10716509-explore-the-udio-interface , https://support.splice.com/en/articles/8652645-what-is-create-how-do-i-use-it

## Typography
- **Display/Hero:** `Sora` — 用于当前版本标题、关键数值、风格标签标题。它有未来感，但不像消费级 AI 产品那样轻浮。
- **Body:** `IBM Plex Sans` — 用于正文、说明、辅助文案。它的技术感和秩序感适合专业工作台。
- **UI/Labels:** `IBM Plex Sans` + 中文 `Noto Sans SC` / `思源黑体 SC` — 中文要稳、窄、清楚，避免圆润可爱。
- **Data/Tables:** `IBM Plex Sans` with tabular numbers — 用于 BPM、调式、时长、状态等参数信息。
- **Code:** `IBM Plex Mono`
- **Loading:** 
  - Web font preview/loading: `Sora`, `IBM Plex Sans`, `IBM Plex Mono`, `Noto Sans SC` via Google Fonts
  - Production strategy: 优先自托管或稳定 CDN，避免字体闪烁破坏工具感
- **Scale:**
  - `display-xl`: 56px / 1.0 / 700
  - `display-lg`: 40px / 1.05 / 700
  - `title-lg`: 28px / 1.15 / 600
  - `title-md`: 22px / 1.2 / 600
  - `body-lg`: 16px / 1.6 / 400
  - `body-md`: 14px / 1.6 / 400
  - `label-md`: 13px / 1.4 / 500
  - `label-sm`: 11px / 1.3 / 600 / uppercase only for Latin micro-labels

## Color
- **Approach:** restrained
- **Primary:** `#FFB000` — 主要动作、当前版本、确认、活跃播放与主导状态
- **Secondary:** `#3CD6C8` — 推导链、状态推进、可编辑建议、理解层高亮
- **Neutrals:**
  - `--bg`: `#0B0F14`
  - `--surface-1`: `#111923`
  - `--surface-2`: `#182230`
  - `--surface-3`: `#1E2A39`
  - `--line`: `#263244`
  - `--text`: `#EAF0F8`
  - `--text-muted`: `#91A1B4`
  - `--text-dim`: `#6E7C90`
- **Semantic:**
  - success: `#6DD3A0`
  - warning: `#FFB000`
  - error: `#FF5C4D`
  - info: `#3CD6C8`
- **Dark mode:** 本产品默认就是暗色工作台。若未来做浅色模式，不允许简单反相；要重新设计表面层级，降低强调色饱和度 10-20%，保留“专业控制台”气质。

### CSS Variables

```css
:root {
  --bg: #0B0F14;
  --surface-1: #111923;
  --surface-2: #182230;
  --surface-3: #1E2A39;
  --line: #263244;
  --text: #EAF0F8;
  --text-muted: #91A1B4;
  --text-dim: #6E7C90;
  --accent-primary: #FFB000;
  --accent-secondary: #3CD6C8;
  --accent-success: #6DD3A0;
  --accent-danger: #FF5C4D;
}
```

## Spacing
- **Base unit:** 8px
- **Density:** compact-comfortable
- **Scale:** `2xs(4) xs(8) sm(12) md(16) lg(24) xl(32) 2xl(40) 3xl(56) 4xl(72)`

### Spacing Rules
- 顶部当前版本主模块内边距：24px
- 工作流行项目高度：56-64px
- Inspector 内区块间距：16px / 24px
- 主区块间垂直节奏：32px
- 同一信息层的控件间距要稳定，不允许一块松一块紧

## Layout
- **Approach:** hybrid
- **Grid:** 
  - Desktop 1440+: 12-column shell
  - Laptop 1280+: 12-column shell, tighter gutters
  - Small laptop 1024+: 8-column shell, inspector remains visible
- **Max content width:** 1440px
- **Border radius:**
  - xs: 6px
  - sm: 10px
  - md: 14px
  - lg: 20px
  - pill: 9999px

### Composition Rules
- 第一屏是结果优先，不是居中 hero 文档。
- 顶部当前版本像一条 `master strip` 横向主结果，包含封面、标题、播放、当前风格、关键参数。
- 核心流程区必须是：
  - 左侧：流程行项目
  - 右侧：当前步骤 inspector
- 下方才是题材参考区。
- 卡片只能用于对象本身：
  - 当前歌曲模块
  - 封面预览
  - 分支版本块
- 禁止把页面主体做成一堆同级卡片往下堆。

## Motion
- **Approach:** minimal-functional
- **Easing:** 
  - enter: `cubic-bezier(0.22, 1, 0.36, 1)`
  - exit: `cubic-bezier(0.4, 0, 1, 1)`
  - move: `cubic-bezier(0.2, 0.8, 0.2, 1)`
- **Duration:**
  - micro: 80ms
  - short: 160ms
  - medium: 260ms
  - long: 420ms

### Motion Rules
- 生成过程必须逐步亮起，不允许整页转圈等待。
- 展开步骤时，优先用 inspector 的淡入/位移，而不是整页重排。
- 当前风格切换时保留页面骨架稳定，只替换内容。
- 必须支持 `prefers-reduced-motion: reduce`。

## Chinese Interface Voice
- 中文语气偏专业音乐制作语言，不偏电影海报口号。
- 推荐词汇：
  - `当前版本`
  - `创作流程`
  - `题材参考`
  - `分支版本`
  - `编曲设定`
  - `歌词结构`
  - `情绪走向`
  - `生成中`
  - `重新生成这一段`
- 避免词汇：
  - `命运抉择`
  - `灵感风暴`
  - `终极史诗版`
  - `一键神作`

## Interaction Design Rules
- 首次进入默认展示一个已完成热门示例，用于教学，不是用户草稿。
- 用户点击 `试试我的题材` 后进入新的创作工作区，不能直接覆盖示例。
- 创作流程默认折叠，每行必须同时包含：
  - 步骤标题
  - 一句人话摘要
  - 当前状态
- 状态必须清晰区分：
  - 未开始
  - 生成中
  - 已完成
  - 失败
- 已完成步骤不能因为后一步失败而消失。

## Responsive
- v1 为桌面优先。
- 目标断点：
  - 1440px+ 主目标
  - 1280px+ 必须保持完整体验
  - 1024px+ 必须可用
- 小屏移动端本期不做完整创作工作台。
- 小屏只允许显示轻量 fallback 页面，说明该产品推荐桌面端使用。

## Accessibility
- 所有工作流行项目必须可键盘访问。
- 焦点态必须明显，不可只靠淡边框。
- `当前歌曲 / 创作流程 / 题材参考 / 分支版本` 必须具备清晰 landmark。
- 状态词 `生成中 / 已完成 / 失败` 需要可读屏。
- 交互命中区最小 44px。
- 文本与状态色不能依赖低对比度装饰。

## Anti-Slop Rules
- 不要紫色/蓝紫渐变。
- 不要 3 列图标 feature grid。
- 不要整页居中排版。
- 不要统一大圆角的 SaaS 模板感。
- 不要用卡片当整页默认布局。
- 不要聊天窗口心智。
- 不要“平台会帮你创造一切”式营销语言。

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-26 | Initial design system created | Created by `/design-consultation` based on office-hours plan, plan-design-review outputs, external design research, and independent design voice synthesis |
| 2026-03-26 | Desktop-first workspace | The product's core value depends on dense, inspectable production structure |
| 2026-03-26 | Result-first top composition | The first screen must prove there is a real song artifact, then explain how it was made |
| 2026-03-26 | Inspector workflow layout | This avoids AI card-dashboard slop and aligns with music-production mental models |
