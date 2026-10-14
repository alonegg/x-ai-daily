# X 每日 AI 摘要

每天整理中英文 AI 与开发领域 X 账号的重要帖子。网站：https://alonegg.github.io/x-ai-daily/

## 结构
- `digests/YYYY-MM-DD.md` Markdown 源文件；`digests/YYYY-MM-DD.html` 渲染页面
- `index.html` 首页（最新一期 + 往期列表），`assets/style.css` 共享样式
- `scripts/publish.py` 发布脚本（仅用 Python 标准库）

## 发布
```bash
cd /workspace/x-ai-daily
git pull --rebase
python3 scripts/publish.py /path/to/2026-10-15.md   # 复制到 digests/，渲染、重建首页、提交并推送
python3 scripts/publish.py --no-push                 # 仅重新渲染全部
```
Markdown 格式：`# 标题`，`## 分区`，条目 `- [名字 @handle](原帖链接)：摘要`。
