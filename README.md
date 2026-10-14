# X 每日 AI 摘要

每天整理中英文 AI 与开发领域 X 账号的重要帖子。网站：https://alonegg.github.io/x-ai-daily/

## 结构
- `digests/YYYY-MM-DD.md` Markdown 源文件；`digests/YYYY-MM-DD.html` 渲染页面
- `index.html` 首页（最新一期 + 往期列表），`assets/style.css` 共享样式
- `scripts/publish.py` 发布脚本（仅用 Python 标准库）

## 发布
```bash
cd /workspace/x-ai-daily
git pull --rebase origin main
python3 scripts/publish.py /path/to/2026-10-15.md   # 复制到 digests/，渲染、重建首页、提交并推送
python3 scripts/publish.py --no-push                 # 仅重新渲染全部
```
## Markdown 格式
```markdown
# X 每日 AI 摘要 · YYYY-MM-DD

> 今日要点：一段总览（可选，渲染为高亮框）

## 主题分区（按重要性排序）
- **短标题**：2–4 句详细说明，可含 **加粗** 和 `代码`。来源：[名字 @handle](原帖链接) · [名字2 @handle2](原帖链接2)
```
- 标题条目以 `- **标题**` 开头；行尾 `来源：` 后的所有链接会显示为来源列表（支持多个）。
- 旧格式 `- [名字 @handle](原帖链接)：摘要` 仍然支持。

## 跨天事件追踪
- 在标题后加 `{#story-id}` 标记事件 id（小写字母、数字、连字符），例如 `- **Gemini 4 Argon 降价** {#gemini-4-argon}：…`。该 id 同时作为条目锚点（`digests/日期.html#story-id`）。
- 不同日期使用同一 id 即视为同一事件：每次发布会重建 `data/stories.json`（id → 标题与出现日期/锚点）、重新渲染所有页面，条目下自动显示“📌 同一事件”链接到其他日期，并生成 `stories.html` 时间线（首页顶部有入口）。
- 可选后续说明：在详情中、`来源：` 之前写 `后续：说明文字`，会渲染为“后续（接 上一次日期）”并链接到前一次出现的条目。
- 未标 id 的条目使用自动锚点 `item-N`，不参与事件追踪。

## 长推 / 系列标记
- 在 `{#story-id}` 之后可加 `[长推]`、`[系列]` 或 `[长文]`，例如 `- **标题** {#id} [长推]：…`，页面会显示对应徽标，表示已阅读完整版本。

## 页面功能
- 顶部：日期前后导航、统计、今日要点、今日标题速览（按栏目分组）
- 搜索框 + 栏目筛选（纯静态内联脚本，无外部依赖）；桌面端左侧粘性目录带条数并高亮当前栏目
- 每条显示作者、徽标与原文按钮；自动适配深色模式与手机
