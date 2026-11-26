# X 每日 AI 摘要

每天整理中英文 AI 与开发领域 X 账号的重要帖子。网站：https://daily.chunlin.ch/

## 结构
- `digests/YYYY-MM-DD.md` Markdown 源文件；`digests/YYYY-MM-DD.html` 渲染页面
- `index.html` 首页（最新一期 + 往期列表），`assets/style.css` 共享样式
- `scripts/publish.py` 发布脚本（仅用 Python 标准库）
- `scripts/check.py` 校验摘要 HTML 和 RSS 音频链接（HEAD 状态及长度）；`--today` 同时检查北京时间当天的摘要 Markdown 和播客 JSON

## 发布
在仓库根目录执行（Python 3.10+）：

```bash
python3 scripts/publish.py /path/to/2026-10-15.md   # 复制到 digests/，渲染、重建首页、提交并推送
python3 scripts/publish.py --no-push                 # 仅重新渲染全部
python3 scripts/check.py                           # 检查生成结果和 RSS 音频链接
```

### GitHub Actions
- `.github/workflows/check.yml`：推送到 `main`、Pull Request、手动运行和每天北京时间 07:45 执行。重建后检查 Git 工作区无变化，再运行 `scripts/check.py`；仅定时检查要求当天的摘要和播客元数据都已发布。
- `.github/workflows/pages.yml`：推送到 `main` 时部署。北京时间 09:00 前，如果当天仅有摘要、没有播客 JSON，则跳过此次部署；每天 09:30 的兜底部署和手动部署不受此限制。
- 仓库 **Settings → Pages → Build and deployment → Source** 必须选择 **GitHub Actions**。

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
- 不同日期使用同一 id 即视为同一事件：每次发布会重建 `data/stories.json`（id → 标题与出现日期/锚点）。页面从该文件加载“同一事件”链接，无需因新增后续报道而修改旧期页面。`stories.html` 时间线仍在发布时生成（首页顶部有入口）。
- 可选后续说明：在详情中、`来源：` 之前写 `后续：说明文字`，会渲染为“后续（接 上一次日期）”并链接到前一次出现的条目。
- 未标 id 的条目使用自动锚点 `item-N`，不参与事件追踪。

## 长推 / 系列标记
- 在 `{#story-id}` 之后可加 `[长推]`、`[系列]` 或 `[长文]`，例如 `- **标题** {#id} [长推]：…`，页面会显示对应徽标，表示已阅读完整版本。

## 页面功能
- 顶部：日期前后导航、统计、今日要点、今日标题速览（按栏目分组）
- 搜索框 + 栏目筛选（纯静态内联脚本，无外部依赖）；桌面端左侧粘性目录带条数并高亮当前栏目
- 每条显示作者、徽标与原文按钮；自动适配深色模式与手机

## 播客（可选）
- 把当天音频放到 `podcast/YYYY-MM-DD.mp3`，发布时该日页面顶部（以及首页）自动出现播客播放器；没有 mp3 就不显示。往期列表会给有播客的日期加「▶ 播客」标记。
- 可选 `podcast/YYYY-MM-DD.json`：`title`、`desc`、`voice`、`duration`（秒，缺省时用 ffprobe 读取）、`chapters`（`[{"t": 秒, "title": "…", "group": "今日快讯|今日重点|值得评论 · 一起讨论"}]`）。
- 可选 `podcast/YYYY-MM-DD.md`：口播文字稿，以 `## ` 分段，渲染为可折叠「文字稿」。
- `site_config.json` 的 `podcast.owner_email`：为空则省略，填写后会作为公开的播客所有者邮件地址写入 RSS。
- 播放器：播放/暂停、后退 15 秒 / 前进 30 秒、进度条、1× / 1.25× / 1.5× / 2× 倍速（记住上次选择）、章节跳转、断点续听（localStorage）、滚动后底部迷你播放条、锁屏媒体信息（Media Session）。
- 体积提醒：每期约 18 MB（96 kbps）。仓库建议只保留最近若干期音频，或改放对象存储 / Release 附件。
