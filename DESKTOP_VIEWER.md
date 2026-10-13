# GitHub 排行榜桌面查看器

在 Windows 上双击 `open_ranking_viewer.vbs` 可无命令行窗口地启动程序：后台先抓取一次最新 Stars Top 100，成功后打开桌面查看器；发生错误时才显示错误弹窗。也可以双击 `open_ranking_viewer.bat`，它会立即转交给隐藏启动器。抓取需要项目根目录中的 `access_token.txt` 保存有效的 GitHub Token，并且需要网络连接。也可以单独运行 `start_github_ranking.bat` 更新榜单。首次使用离线翻译前，请先双击 `setup_local_translation.bat` 安装本地翻译引擎和英中语言包。安装完成后，项目简介会始终通过本地离线模型翻译，不请求在线翻译服务。

查看器会自动读取 `Data` 文件夹中的 `github-ranking-YYYY-MM-DD.csv` 文件：

- **总榜**：显示最新快照中的 Stars 总数排名。
- **日榜**：比较选中日期与前一日的 Stars 快照，只列出有连续两日数据的日期。
- **月榜**：比较该月最后一份快照与该月开始前最近一份快照的 Stars 变化。
- **年榜**：比较该年最后一份快照与该年开始前最近一份快照的 Stars 变化。
- 日、月、年增长榜只统计两个快照中都在 Stars Top 100 的项目；未同时出现在两个快照中的项目不参与增长排名。界面会显示实际比较的快照日期。
- 输入项目名称、用户名、语言或简介文字可筛选当前榜单。点击“联网搜索”或在搜索框按 Enter，会连接 GitHub 搜索仓库名称、简介和 README；结果按 Stars 排序，每页最多 100 条，可继续翻页，GitHub 搜索最多提供 1,000 条匹配结果。联网搜索需要有效的 Token 和网络连接。
- 所选榜单中的全部项目简介都会自动翻译成中文；译文保存在当前 Windows 用户的本地缓存中，后续打开或切换期间时可直接复用。失败时可点击“补全 / 重试翻译”。原始 CSV 和 README 不会更改。
- 点击列标题排序；双击项目或选中项目后点击“打开选中项目”，可在浏览器打开其 GitHub 页面。

安装时需要联网下载 Argos Translate 和英中离线模型；下载完成后，简介翻译在本机运行，不会将项目简介发送给在线翻译服务。

安装脚本会使用 Python 3.11 创建独立的 `.venv-local-translate` 环境，不影响其他 Python 项目。需要安装 Python 3.11；如果找不到，请先安装 Python 3.11 后再运行安装脚本。若双击查看器时提示找不到 Python，请安装包含 Tkinter 的 Python 3。

抓取会更新本地历史 CSV、README 和 Stars Top 100 页面，仅使用一次 GitHub GraphQL 请求，不再查询 Forks 榜或各语言榜。
