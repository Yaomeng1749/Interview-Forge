# 求职训练工场 / Interview Forge

![Interview Forge — 自适应面试练习](docs/assets/interview-forge-hero.png)

**本地运行的 MLE、SDE 与现代 AI 系统双语面试练习工具。**

你可以创建自适应试卷、用随机快速练习刷题、复习错题，并导入自己的题包。应用运行在本机，学习记录保存在本地 SQLite 数据库中。

> English is the primary documentation language. [Read the English README](README.md).

## 功能

- 创建 SDE、MLE 或混合方向的限时 40 题试卷。
- 使用快速练习随机刷题；做过的题会保留在复习流程中，而不是悄悄重复出现。
- 在英文与简体中文界面、题干和解析之间切换。
- 查看错题、收藏、知识点进度和逐题解析。
- 预览并校验双语 JSON/JSONL 题包后再导入。
- 可选连接决策 Provider 动态调整难度；不可用时最终回退到本地规则逻辑。

## 本机启动

### 环境要求

- Python 3.12 或更新版本
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Node.js 20.19+（或 22.12+）与 npm
- Bash（macOS/Linux；Windows 请使用 WSL2）

克隆仓库并进入项目目录后运行：

```bash
./scripts/start_local.sh
```

首次启动会安装后端和前端锁定依赖。后续如果依赖没有变化，可以跳过安装：

```bash
./scripts/start_local.sh --skip-install
```

浏览器打开 <http://127.0.0.1:5173>。API 与交互式 API 文档分别位于 <http://127.0.0.1:8000> 和 <http://127.0.0.1:8000/docs>。在终端按 `Ctrl+C` 会停止前后端。这套开发服务只监听本机，供个人使用，不是生产环境部署方案。

### 可选 Provider 配置

运行项目不需要付费 API 密钥。如需配置可选 Provider，可复制示例文件并在本机编辑：

```bash
cp backend/.env.example backend/.env
```

密钥应只保存在 `backend/.env` 或本机 shell 环境变量中，不要提交到 Git。启用外部决策 Provider 后，它会收到用于决定难度和知识点权重的学习进度汇总与题库统计信息；该请求不会包含题干或作答历史。Provider 不可用时，最终会使用本地规则逻辑。

## 个人数据

- 学习记录保存在 `backend/data/trainer.db`，该文件已从 Git 跟踪中排除。
- 题库以 JSONL 保存在 `question_bank/`；启动时会加载旧题库、精选题源和固定套卷。
- 已有试卷会保存题目快照，后续修改题库不会改写已创建或已完成的试卷。
- 更换电脑前，如需保留学习进度，请备份 `backend/data/trainer.db`。

## 导入自己的题目

请按[题目导入规范](docs/question-import-spec.md)和[schema](question_bank/schema.json)生成 JSON/JSONL。每道题需要提供英文与简体中文内容。应用内的导入预览会先报告无效记录；整批校验失败时不会部分写入，同 ID 冲突也不会覆盖已有题目。

## 开发验证

```bash
# 后端
cd backend
uv sync --extra dev
uv run pytest
uv run ruff check .

# 前端
cd ../frontend
npm ci
npm run test
npm run build
```

在仓库根目录运行 `./scripts/verify_all.sh` 可执行完整本机验证，包括题库校验、前后端检查、API smoke test 和浏览器端到端测试。

## 项目目录

| 路径 | 用途 |
| --- | --- |
| `frontend/` | React + TypeScript Web 应用 |
| `backend/` | FastAPI 服务、SQLite 存储、组卷与快速练习逻辑 |
| `question_bank/` | 版本化题库 schema、题源和固定精选卷 |
| `docs/` | 组卷蓝图、API 契约和导入说明 |
| `scripts/` | 本机启动和验证脚本 |

## 许可证

仓库目前没有添加许可证。重新分发或复用项目前，请先联系仓库所有者。
