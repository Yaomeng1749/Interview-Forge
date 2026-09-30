# 求职训练工场 / Interview Forge

![Interview Forge — 自适应面试练习](docs/assets/interview-forge-hero.png)

**在本机运行的双语 SDE、MLE 与现代 AI 系统面试练习工具。**

[English](README.md) · [题目导入规范](docs/question-import-spec.md) · [JSON Schema](question_bank/schema.json)

Interview Forge 把限时套卷、短轮刷题、逐题解析和复习队列放在一起。应用运行在你的电脑上，作答与进度保存在本机 SQLite。题目尽量训练你在具体约束下选择方案，而不只是背术语或套算式。

## 演示视频

[![观看 Interview Forge 演示：建卷、快速练习、复习与设置](docs/assets/interview-forge-demo-preview.gif)](docs/assets/interview-forge-demo.mp4)

[观看完整 45 秒演示（MP4）](docs/assets/interview-forge-demo.mp4)。画面录自真实应用，使用全新的本机演示数据库；本次录制没有配置可选的 Jev Provider。

## 可以怎样练习

| 模式 | 实际行为 |
| --- | --- |
| 动态生成 A / D / G 卷 | 选择 SDE、MLE 或混合方向组 40 题。标准卷包含 30 道单选和 10 道填空，可选择难度预设、计时、题序和选项随机化。 |
| 四套固定精选卷 | A1（SDE）、D1（MLE）、G1（混合）、G2（更侧重场景与取舍的混合卷）各有固定的 40 题；启用自适应练习也不会替换它们的题目集合。 |
| 快速练习 | 可选 20、40、80、160 题或持续练习；从符合条件且未作答的题中随机抽取，提交后立即得到判分与解析。 |
| 复习与进度 | 在错题、到期题和收藏题中回看；控制台和学习地图展示正确率及知识点掌握情况。 |
| 导入自制题包 | 在题库页预览并导入中英双语 JSON/JSONL；校验失败不会只导入一部分，已有 ID 不会被覆盖。 |

题目覆盖概念、代码推理、调试、系统设计、评估和方案取舍。随项目提供的精选题源包含 SDE 基础，以及 RAG、Agent、LLM 推理服务、模型评估等 MLE/AI 内容。这些文件需要人工维护；项目不会自动抓取新论文，也不保证每道题都经过领域专家复核。

## 自适应练习与 Jev

决策路由会综合近期正确率、薄弱知识点、概念掌握情况和可用题量，安排下一段练习。**TypeSafe Jev 为可选接入：**配置并连通后，它在基础、标准、强化、高难四档难度配比中作选择；知识点优先级由本地规则计算。Jev 不可用时，最终会回退到本地决策逻辑。

| 决策时机 | 会发生什么 |
| --- | --- |
| 新建动态 A / D / G 卷前 | 在 40 道题冻结前确定难度配比与知识点优先级；你选定的 SDE/MLE/混合方向不变。 |
| 连续套卷交卷后 | 记录新决策，供下一张待开始的试卷使用；刚完成的试卷不变。 |
| 快速练习每答 10 题 | 按新的难度配比与知识点优先级，从合格的未作答题中重排*后续*一段题；当前题和已答题不变。 |
| 固定精选卷 | 保留原定的 40 个题目 ID。Jev 不生成、翻译、判题或改写题目。 |

Jev 决策请求只携带学习表现汇总和题库数量统计，不包含题干或逐条作答记录。API 密钥只在后端环境变量中使用，不进入浏览器或 SQLite。设置页会显示最近一次实际使用的决策 Provider。

## 本机启动

### 环境要求

- Python 3.12 或更新版本
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- Node.js 20.19+（或 22.12+）与 npm
- Bash（macOS/Linux；Windows 请使用 WSL2）

克隆仓库并启动前后端：

```bash
git clone https://github.com/Yaomeng1749/Interview-Forge.git
cd Interview-Forge
./scripts/start_local.sh
```

首次启动会安装后端和前端锁定依赖。后续如果依赖没有变化，可以跳过安装：

```bash
./scripts/start_local.sh --skip-install
```

浏览器打开 <http://127.0.0.1:5173>，交互式 API 文档位于 <http://127.0.0.1:8000/docs>；在终端按 `Ctrl+C` 停止两个开发服务。如果 8000 端口被占用，可换一个后端端口；启动脚本会自动把新地址传给前端：

```bash
BACKEND_PORT=8001 ./scripts/start_local.sh --skip-install
```

### 可选 Provider 配置

不配置 API 密钥也能运行。要启用 Jev，请复制示例配置，在本机副本里设置 `TYPESAFE_API_KEY`。`TYPESAFE_MODEL` 默认是 `jev-latest`；如果账号使用不同接口，也可以修改 `TYPESAFE_URL`。

```bash
cp backend/.env.example backend/.env
```

仅在本机编辑 `backend/.env`，之后重启应用。后端读取密钥，Git 不跟踪该文件。这两个开发服务只监听本机，面向个人使用，不是托管的多人服务。

## 个人数据

- 学习记录保存在 `backend/data/trainer.db`，该文件已从 Git 跟踪中排除。
- 题库以 JSONL 保存在 `question_bank/`；启动时会加载原始 seed、精选题源和固定套卷。新的快速练习从符合条件的活跃题中抽取，而不是旧的纯计算题库。
- 已有试卷会保存题目快照，后续修改题库不会改写已创建或已完成的试卷。
- 更换电脑前，如需保留学习进度，请备份 `backend/data/trainer.db`。

## 导入自己的题目

请按[中文导入规范](docs/question-import-spec.md)、[English guide](docs/question-import-spec.en.md)和 [schema](question_bank/schema.json)生成 JSON/JSONL。每道题需要完整中英文内容、答案、解析与校验字段。预览可检查结构和部分明显的质量问题，但不能证明答案或干扰项在专业内容上正确。

## 开发验证与现有边界

```bash
# 后端
cd backend
uv sync --extra dev
uv run pytest
# 前端
cd ../frontend
npm ci
npm run test
npm run build
```

在仓库根目录运行 `python3 scripts/validate_question_bank.py --root question_bank` 可检查内置题库。`./scripts/verify_all.sh` 还会运行 lint、覆盖率、API smoke 和浏览器测试。后端仍有历史 lint 问题，所以该脚本目前不是全绿的发布门槛。项目目前只支持单人本机使用，没有账号认证或云同步；精选题目仍值得继续人工审阅。

## 项目目录

| 路径 | 用途 |
| --- | --- |
| `frontend/` | React + TypeScript Web 应用 |
| `backend/` | FastAPI 接口、决策路由、判题和 SQLite 存储 |
| `question_bank/` | 版本化 schema、题源和四套固定卷 |
| `docs/` | 组卷蓝图、API 契约和导入说明 |
| `scripts/` | 本机启动和验证脚本 |

## 许可证

仓库目前没有添加许可证。重新分发或复用项目前，请先联系仓库所有者。
