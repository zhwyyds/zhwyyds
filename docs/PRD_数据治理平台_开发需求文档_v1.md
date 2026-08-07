# 数据治理平台 · 开发需求文档（PRD）

| 项 | 内容 |
|----|------|
| 文档版本 | v1.2 |
| 创建日期 | 2026-08-07 |
| 最近更新 | 2026-08-07 |
| 文档状态 | 基线版（反映当前代码真实状态） |
| 适用范围 | 后续开发 Agent / 开发团队的需求依据 |
| 关联仓库 | git@github.com:zhwyyds/zhwyyds.git（分支 dev，本地 /Users/heyuan/DEVELOPMENT/data_go） |

> 本文档是**总纲**，与以下细化文档配套使用（均已在仓库内）：
> `docs/词根字段与规则.md`、`docs/批量指标导入需求规格.md`、`docs/开发与版本管理规范.md`、`docs/数据供给计划.md`、`docs/使用说明.md`、`docs/运维手册.md`
> 本文档优先；如与细化文档冲突，以本文档为准并修订细化文档。

---

## 1. 项目概述

### 1.1 背景与问题

家居卖场租赁业务的数据治理存在四大痛点：

1. **指标命名混乱** — 同一业务概念多种命名（中文/拼音/英文混用）
2. **口径不一致** — 同一指标不同系统定义不同，无法对齐
3. **字段名大量拼音化** — 历史系统字段名无法直接阅读与维护
4. **缺乏数据血缘** — 指标与源表、表与表之间关系不可追溯

### 1.2 项目目标

1. **词根驱动**：所有指标必须来源于词根（Root），词根是命名的唯一真源；词根支持单个维护与批量维护
2. **口径统一**：指标口径在平台上评审、定稿、发布，从源头根治口径不一致
3. **血缘可查**：指标 ↔ 表、表 ↔ 表血缘可视化
4. **简洁诚实**：整体设计克制、无过度包装；AI 能力可降级（Mock），配置状态透明

### 1.3 产品原则（不可违背）

- 所有指标必须能回溯到词根组合
- 词根与词根可单个维护、可批量维护
- 表血缘必须可查
- 本地优先：当前阶段平台本地运行，暂不部署服务器
- 企业级程序规范：API 统一错误处理、请求日志、超时配置、幂等保护、可测试
- 产品语言统一：全平台术语遵循第 1.5 节隐喻映射（构件/卡库/成品卡），不出现互相冲突的叫法

### 1.4 用户与角色

| 角色 | 职责 | 系统使用 |
|------|------|---------|
| 数据治理专员（当前核心用户） | 词根维护、指标评审、口径定稿 | 全部功能 |
| 数据产品/业务 | 提出指标需求、确认口径 | 指标管理、批量导入 |
| 开发（后续） | 维护平台代码 | 全部 + API |
| 管理员（后续） | 模型配置、发布控制 | 配置、发布 |

### 1.5 产品隐喻：卡牌世界 ↔ 数据治理（已确认的产品语言）

> **决策**：平台采用"卡牌收藏"隐喻统一产品语言与 UI 语义。隐喻沿**数据流程**展开（开包→提炼→合成→收藏），与使用者操作顺序一致，已由产品确认采用。
> **用词规范**：说「卡库」不说「卡盒」；说「数据包 / 评审包」分清表与批量导入组；说「素材」不说「素材卡」；说「构件」不说「碎片」；「卡包」默认指表（确定性数据包），不表达随机盲盒含义。

| 卡牌世界 | 数据治理 | 说明 |
|---------|---------|------|
| **卡包（数据包）** | **表（table）** | 打开表 = 开包，内含字段素材；表是数据的物理来源（ODS/DWD/DWS/ADS 分层） |
| 素材 | **字段（field）** | 开包得到的原始元素；词根在字段层的落点（对应"字段拼音化"治理） |
| 构件 | **词根（root）** | 标准件，同时用于字段命名与指标命名 |
| **成品卡** | **指标（metric）** | 从字段素材提炼、按构件命名、携带口径的业务度量 |
| **卡库** | **主题域（domain）** | 14 个主题域 = 14 个卡库，指标按业务分类收藏 |
| 合成卡 | **派生/复合指标** | 原子指标 + 修饰词组合 |
| 稀有度 ★ | **质量评分** | 优秀/良好/合格/待改进 |
| 卡面效果文字 | **口径描述** | 写在成品卡上给使用者看 |
| 卡组（deck） | **指标树 / 指标体系** | 特定分析场景的指标组合 |
| 开包/加工链记录 | **血缘（lineage）** | 成品卡经过哪些数据包、哪些层加工而来 |
| 评审包 | **批量导入任务组** | 待验收的一组指标卡（与"数据包=表"区分） |
| 卡册收集进度 | **治理覆盖率** | 指标治理完成度 |

**隐喻在 UI 中的承载方式**：

- **主题域 = 卡库封面**：主页卡库陈列，点开卡库进入该主题域指标集
- **表 = 数据包**：表资产页呈现为数据包陈列，开包（展开）查看字段素材
- **字段 = 素材**：数据包内素材清单，标注词根构件映射
- **指标 = 成品卡**：卡面展示名称、构件（词根组合）、素材来源（物理表）、属性、口径、稀有度（评分）
- **批量导入评审 = 评审包验收**：逐卡抽取（查看）→ 编辑（修正）→ 入册（进草稿）/ 打回
- **扇形堆叠/抽出** = 评审包展开与逐卡查看（现有交互保留，仅做企业级收敛）

**⚠️ 隐喻边界（必须守住，产品原则级）**：

1. **指标 ≠ 词根拼接。** 词根解决"叫什么"，口径解决"怎么算"。两个指标构件完全一样（如都用「销售」「额」），但口径不同（含税/不含税），就是**两张不同的卡** —— 这正是评分（稀有度）与口径评审存在的意义。
2. **表是"确定性数据包"，不是随机盲盒。** 打开表之前就知道里面有什么字段；隐喻不表达随机抽取。
3. **字段是"素材"，不是"卡"。** 素材与成品卡层级不同：字段经提炼成指标，指标才叫"卡"。避免层级混乱。
4. **隐喻任何情况下不得弱化口径治理的地位。**

### 1.6 术语表

| 术语 | 英文 | 定义 |
|------|------|------|
| 词根 | Root | 指标/字段命名的最小构件；含中英文名/缩写/类型/同义词；按主题域管理 |
| 修饰词 | Modifier | 与词根组合生成派生指标的限定词（如"日均""累计"） |
| 字段 | Field | 表的列，物理层素材；命名应词根化（治"拼音化"痛点） |
| 表 | Table | 数据物理载体（数据包），分 ODS/DWD/DWS/ADS 层 |
| 指标 | Metric | 由字段素材提炼、词根（+修饰词）命名的业务度量；分原子/衍生/复合三类 |
| 原子指标 | Atomic | 不可再分的指标，直接源于词根 |
| 派生指标 | Derived | 原子指标 × 修饰词组合而成 |
| 复合指标 | Composite | 多指标计算而成 |
| 口径 | Caliber | 指标的计算定义（业务/公式/周期/粒度/边界/来源） |
| 主题域 | Domain | 指标的业务分组（14 个卡库） |
| 血缘 | Lineage | 指标与表、表与表之间的数据流向关系（加工链） |
| 草稿 | Draft | 评审通过但未发布的指标状态 |
| 发布 | Release | 按域批量发布 approved 指标并分配版本号 |

---

## 2. 现状盘点（截至 2026-08-07）

### 2.1 已完成（✅ 基线能力）

| # | 能力 | 状态 |
|---|------|------|
| 1 | 词根体系：14 主题域、词根 CRUD、AI 生成、CSV 批量导入导出 | ✅ |
| 2 | 指标体系：指标 CRUD（30+ 字段）、AI 建议（同步/异步）、批量生成派生指标 | ✅ |
| 3 | 批量导入评审：CSV 上传→切分 30 条/组→去重→AI 生成→逐卡人工评审→草稿 | ✅ |
| 4 | 评审编辑：全字段（22 字段）可编辑，PATCH 落盘持久化 | ✅ |
| 5 | 口径管理：口径起草（AI）、口径评审、口径核查 | ✅ |
| 6 | 评分体系：规则评分 + 等级（优秀/良好/合格/待改进）+ 汇总 | ✅ |
| 7 | 血缘：JSON 结构化存储、上传校验、查询接口、表血缘页 | ✅ |
| 8 | 发布控制：按域发布 approved 指标、版本分配、回滚、版本 diff | ✅ |
| 9 | 配置管理：修饰词规则、LLM 模型配置（models.csv）CRUD | ✅ |
| 10 | AI 多路：Mock/Live 双模式，OpenAI/Anthropic/千问/智谱/DeepSeek（当前启用 DeepSeek） | ✅ |
| 11 | API 企业级基础：统一错误处理（code 字段）、请求日志、LLM 超时配置、process 幂等、CORS 收敛、API Key 认证中间件 | ✅ |
| 12 | 测试：37 个测试文件 / 196 用例，全量通过（约 4.2s） | ✅ |
| 13 | UI：14 个页面（仪表盘 / 指标 / 指标管理 / 词根 / 批量生成 / 批量导入 / 评审 / 血缘 / 表血缘 / 命名 / 口径 / 评分 / 口径核查 / 设置） | ✅ 原型级，企业级化待办 B6/B7 |

### 2.2 待办（❌ / 🚧）

| # | 事项 | 优先级 | 说明 |
|---|------|--------|------|
| B1 | API 版本化（/api/v1 前缀） | P1 | 推荐加，旧路径保留过渡 |
| B2 | 认证默认开启（未配 DATA_GOV_API_KEY 拒绝启动） | P1 | 当前默认不鉴权 |
| B3 | 列表分页（metrics/roots/import-tasks） | P2 | 加 page/page_size，默认全量兼容 |
| B4 | 写操作审计日志 | P2 | 企业级数据治理平台需记录操作者与变更 |
| B5 | 前端框架化（Vue3 渐进式） | P2 | 当前原生 JS 约 1.4 万行，维护成本高 |
| B6 | 批量导入评审 UI 企业级化 | P2 | **保留卡牌隐喻为产品语言**（构件槽/稀有度），交互形态向生产力收敛：表格+编辑抽屉为主，卡牌作展示态；已装 board-game-ui / impeccable / web-design-guidelines 三件套辅助 |
| B7 | 全平台 UI 统一企业级视觉 + 隐喻落地 | P3 | 14 页面统一规范，卡库/构件/稀有度视觉语言一致 |
| B8 | 存储升级（CSV→SQLite，事务与并发） | P3 | 当前 .lock 进程内锁，单机可用 |
| B9 | 限流 | P3 | 防滥用 |
| B10 | 表资产管理（数据包） | P2 | 表升级为一级治理对象：表 CRUD + 分层（ODS/DWD/DWS/ADS）+ 字段词根化 + 指标↔表映射可维护（血缘从"上传 JSON"变为"可维护关系"）；当前表仅是血缘节点 |

---

## 3. 功能需求

> 状态标记：✅ 已实现 / 🚧 部分实现 / ❌ 未实现
> 每个功能给出：描述、用户故事、关键接口、验收标准。

### 3.1 词根管理 = 构件库（✅）

**描述**：词根是指标命名的唯一真源（隐喻：构件）。支持按主题域（14 个卡库）管理，单个维护与批量维护。

**用户故事**：
- 作为治理专员，我想新增/修改词根（中英文名、缩写、类型、同义词），以便指标命名有依据
- 我想通过 CSV 批量导入词根，以便一次性治理历史词根
- 我想用 AI 辅助生成词根候选并评审后入库，以便提高效率

**接口**：
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/roots?domain= | 词根列表（可按域过滤） |
| POST | /api/roots | 创建词根（自动分配 R_{DOMAIN}_{seq}） |
| PUT | /api/roots/{root_id} | 更新词根字段 |
| POST | /api/roots/suggest | AI 字段建议 |
| POST | /api/roots/generate | AI 批量生成（候选） |
| POST | /api/roots/generate/commit | 生成结果确认入库 |
| GET | /api/roots/export | 导出 CSV |
| POST | /api/roots/import | CSV 批量导入（校验+去重） |

**词根字段**：root_id, root_cn, root_en, root_abbr, root_type（noun/verb/adj…）, description, synonyms, source_model, review_status, domain_code

**验收标准**：
- [ ] 14 域词根均可 CRUD
- [ ] CSV 导入：缺 domain/root_cn/root_en 的行跳过并计数；同域重复 root_en 跳过
- [ ] 导入接口性能：循环外加载 catalog（已修，O(n)）

### 3.2 指标管理 = 卡片库（✅）

**描述**：指标全字段管理（30+ 字段），支持 AI 建议、批量生成派生指标（合成卡）、评审、评分、发布。

**用户故事**：
- 作为治理专员，我想查看/新建/编辑指标的全部字段，以便维护指标定义
- 我想对模糊指标让 AI 生成完整定义（英文名/公式/口径），再人工确认
- 我想用 原子指标 × 修饰词 批量生成派生指标

**接口**：
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/metrics?domain= | 指标列表 |
| POST | /api/metrics | 创建指标（MetricCreateRequest 必填 metric_id/metric_cn） |
| PUT | /api/metrics/{metric_id} | 更新指标（MetricUpdateRequest 30+ 字段全可选） |
| POST | /api/metrics/suggest | AI 同步建议 |
| POST | /api/metrics/suggest/async | AI 异步建议（返回 task_id，轮询 /api/ai-tasks/{id}） |
| POST | /api/metrics/batch-generate | 批量生成派生指标（dry_run 可预览） |
| POST | /api/metrics/{id}/review | 多模型评审 |
| POST | /api/metrics/{id}/review/{review_id}/apply-revision | 应用评审修订建议（勾选字段） |
| GET | /api/metrics/export | 导出 CSV |
| GET | /api/metrics/stats | 指标统计 |
| GET | /api/metrics/{id}/score | 指标评分 |
| POST | /api/metrics/{id}/score/refresh | 重评单个指标 |

**指标核心字段**：metric_id, metric_cn, metric_en, domain_code, root_ids, metric_type（atomic/derived/composite）, caliber_desc, unit, frequency, owner, category_l1/l2, value_type, dimensions, scenario, formula, formula_cn, tech_caliber, source_table, data_sources, precision, alert_rules, reports, review_status, version

**验收标准**：
- [ ] PUT /api/metrics/{id} 支持上述全部字段更新（exclude_unset 语义）
- [ ] 新增指标 ID 格式 M_{DOMAIN}_{XXX}
- [ ] 指标卡面展示其词根组合（构件槽），词根可点击跳转（隐喻落地，随 B7）

### 3.3 批量导入与评审 = 开盒验收（✅）

**描述**：CSV 上传 → 每 30 条一组生成待办任务（评审包）→ 去重比对指标库 → AI 生成指标卡片 → 逐卡人工评审（通过→草稿入册 / 打回）→ 编辑修正。

**用户故事**：
- 作为治理专员，我想批量上传历史指标 CSV，自动切分任务，以便分批治理
- 我想在评审时看到去重结果（新/重/疑似），避免重复入库
- 我想逐卡评审，通过则入草稿，打回则修正重提
- 我想在评审时编辑卡片的所有字段并保存落盘

**接口**：
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/import-tasks/upload | CSV 上传 → 切分 → 生成任务 |
| GET | /api/import-tasks | 任务列表 |
| GET | /api/import-tasks/{task_id} | 任务详情 |
| POST | /api/import-tasks/{task_id}/process | 去重 + AI 生成（幂等：重复触发 409） |
| PATCH | /api/import-tasks/{task_id}/rows/{row_index} | 单行编辑落盘（仅接受 EDITABLE_FIELDS 白名单） |
| POST | /api/import-tasks/{task_id}/review | 逐卡评审（approve→草稿入库 / reject→打回） |

**EDITABLE_FIELDS（22 字段）**：metric_cn, metric_en, domain_code, metric_type, category_l1, category_l2, caliber_desc, unit, frequency, owner, formula, formula_cn, tech_caliber, precision, source_table, physical_table, data_sources, dimensions, scenario, alert_rules, value_type, reports

**任务状态机**：pending → processing → reviewing → done

**验收标准**：
- [ ] 上传后每 30 条一组生成任务
- [ ] process 重复调用返回 409
- [ ] PATCH 编辑落盘，重拉任务字段保留；非白名单字段被忽略
- [ ] approve 后指标以 draft 状态入库，携带编辑后的全部字段
- [ ] 任务全部评审完 → status=done

### 3.4 AI 能力（✅，依赖模型配置）

**描述**：词根生成、指标建议、口径起草/评审均接入 LLM；Mock/Live 双模式。

**模式规则**：
- `DATA_GOV_LLM_MODE=mock|live|auto`（auto：有 Key 则 live，否则 mock）
- live 需 models.csv 中启用且配置 Key 的模型；当前启用 deepseek-v4-flash
- 单次请求超时 `DATA_GOV_LLM_TIMEOUT`（默认 60s）

**透明性要求（诚实原则）**：
- `GET /api/llm/status` 返回当前模式、各厂商 Key 是否配置（不返回密钥）、.env/secrets 是否存在
- Mock 模式生成结果明确标注（英文名置 pending_naming，卡片显示待命名）

**验收标准**：
- [ ] live 模式实测 AI 生成（英文名/单位/口径来自 LLM）
- [ ] 无 Key 时自动降级 mock，不报错
- [ ] LLM 慢响应在 DATA_GOV_LLM_TIMEOUT 内超时，不长时间占用 worker

### 3.5 口径管理 = 卡面效果文字（✅）

**描述**：口径起草（AI 产出业务/公式/周期/粒度/边界/来源结构化口径）、口径评审、口径核查。

**接口**：`GET /api/caliber/pending`、口径起草（动态构建 prompt）、`GET /api/prompts/caliber_draft`（查看提示词）

### 3.6 评分体系 = 稀有度（✅）

**描述**：指标质量规则评分（命名/口径/血缘等维度），等级映射（≥90 优秀 / ≥75 良好 / ≥60 合格 / <60 待改进）。

**接口**：`POST /api/scores/refresh`（全量重评）、`GET /api/scores/summary`、`GET /api/metrics/{id}/score`、`POST /api/metrics/{id}/score/refresh`

### 3.7 血缘管理（✅）

**描述**：血缘 JSON 结构化（target_table → source_tables，含 layer/system/metric_ids 关联），上传校验、查询。

**接口**：`GET /api/lineage?domain=`、`GET /api/lineage/domains`、`POST /api/lineage/upload`（校验错误返回 400 并列出问题）

**验收标准**：
- [ ] 上传血缘数据时结构校验（target_table/source_tables 必填等）
- [ ] 血缘按域查询，前端表血缘页可视化

### 3.8 发布控制（✅）

**描述**：按域批量发布 approved 指标（整库发布），自动版本号；支持回滚与版本 diff。

**接口**：`POST /api/domains/{domain}/publish`、`GET /api/domains/{domain}/releases`、`POST /api/domains/{domain}/revert`、`GET /api/domains/{domain}/version-diff?from=&to=`、`GET /api/releases/overview`

### 3.9 配置管理（✅）

**描述**：修饰词规则 CRUD、LLM 模型配置 CRUD、域名管理（domains.csv，即卡库清单）。

**接口**：`GET/POST /api/modifier-rules`、`PUT/DELETE /api/modifier-rules/{id}`、`GET/POST /api/models`、`PUT/DELETE /api/models/{id}`、`GET /api/domains`

### 3.10 仪表盘与看板 = 卡册总览（✅）

**描述**：域级治理红绿灯（词根/指标/评分/血缘/口径/发布）、全局统计、验收报告 —— 即各卡库的收集进度与质量总览。

**接口**：`GET /api/dashboard/domains`、`GET /api/metrics/stats`、`GET /api/acceptance?refresh=true`、`GET /api/metric-tree`

### 3.11 表资产管理 = 数据包（❌ 规划中，对应待办 B10）

> 当前状态：**表不是一级治理对象** —— 仅在血缘 JSON 中作为节点存在（target_table / source_tables），无表 CRUD、无字段管理。本模块为规划需求，落地时接口可按下列设计，也可在实现中优化。

**描述**：表升级为一级治理对象（数据包）：表 CRUD、分层管理（ODS/DWD/DWS/ADS）、表名标准化、**字段词根化映射**（字段 ↔ 词根，直接治"字段名拼音化"痛点）、指标↔表映射可维护（血缘可维护而非仅上传）。

**用户故事**：
- 作为治理专员，我想登记/维护物理表（名称、分层、所属域、负责人），以便建立数据资产清单
- 我想对表的字段做词根映射（字段名 ↔ 词根构件），以便根治字段拼音化
- 我想维护"表 ↔ 指标"的关联（哪些指标从这张表算出来），使血缘可维护可追溯

**接口（规划）**：
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/tables?domain=&layer= | 表列表（可按域/分层过滤） |
| POST | /api/tables | 登记表 |
| PUT | /api/tables/{table_id} | 更新表元数据 |
| DELETE | /api/tables/{table_id} | 下线/删除表 |
| GET | /api/tables/{table_id}/fields | 字段清单（含词根映射） |
| POST | /api/tables/{table_id}/fields | 登记/导入字段（CSV） |
| PUT | /api/tables/{table_id}/fields/{field_id} | 字段词根映射 |
| GET | /api/tables/{table_id}/metrics | 该表支撑的指标 |
| POST | /api/tables/{table_id}/metrics | 维护指标↔表映射 |

**数据模型（规划）**：见 6.5 表 / 6.6 字段。

**验收标准**（B10 落地时）：
- [ ] 表 CRUD + 分层管理（ODS/DWD/DWS/ADS）
- [ ] 字段可登记/批量导入，字段名可映射词根构件
- [ ] 指标↔表映射可维护，血缘页基于该映射渲染（替代纯 JSON 上传）

---

## 4. 非功能需求（企业级规范）

### 4.1 API 规范（基线已达标）

- **统一错误响应**：`{"detail": "...", "code": "..."}`；code 取值：`HTTP_{status}` / `VALIDATION_ERROR` / `INTERNAL_ERROR` / 业务自定义（AppError）
- **统一异常处理**：全局 handler（AppError → 业务错误码；RequestValidationError → 422 + 字段位置；未捕获异常 → 500 兜底，堆栈只进日志）
- **HTTP 语义**：GET 查询 / POST 创建触发 / PUT 全量 / PATCH 部分 / DELETE 删除
- **路径安全**：task_id 等路径参数防目录穿越（白名单校验）
- **认证**：`DATA_GOV_API_KEY` 配置后启用（X-API-Key 或 Bearer），OPTIONS 预检放行
- **CORS**：配置化 allow_origins，默认本机端口白名单 + 正则

### 4.2 安全

- 前端输出全量转义（esc()），防 XSS
- 无 SQL 注入面（无数据库）；文件存储注意路径校验
- 密钥不落日志、接口不返回密钥
- **待办 B2**：认证默认开启（未配 Key 拒绝启动）

### 4.3 性能与超时

- LLM 调用超时配置化（`DATA_GOV_LLM_TIMEOUT`，默认 60s）
- AI 批量生成并发 `AI_GENERATE_PARALLEL`（默认 8）
- 词根导入 O(n)（已修）
- **待办 B3**：列表分页，防止数据量大时全量返回

### 4.4 日志与可观测

- 请求日志：`method / path / status / 耗时`，响应头 `X-Request-Duration-Ms`
- 应用日志级别 `DATA_GOV_LOG_LEVEL` 可配
- **待办 B4**：写操作审计日志

### 4.5 测试要求（强制）

- 每个新功能/修复必须有对应 pytest 用例
- 全量测试必须通过后才可提交（当前 196 用例基线）
- 测试覆盖：接口正常/异常路径、幂等、白名单、权限

---

## 5. 技术架构

### 5.1 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 后端 | Python 3.10+ / FastAPI / Pydantic v2 | uvicorn 运行 |
| 前端 | 原生 HTML/JS/CSS（ui-prototype/） | 无构建，静态挂载；待办 B5 渐进式 Vue3 |
| 存储 | CSV + JSON（文件系统） | 词根/指标/血缘/任务/评分/发布记录；.lock 文件锁 |
| AI | httpx + 多厂商 OpenAI 兼容接口 | DeepSeek（当前启用），可扩展 |
| 测试 | pytest + TestClient | 37 文件 / 196 用例 |
| 质量 | ruff / mypy（dev 依赖） | 规范约束 |
| 前端设计 skill | impeccable / board-game-ui / web-design-guidelines | 用户级 skill（~/.workbuddy/skills/），用于 B6/B7 企业级 UI |

### 5.2 分层

```
api/（路由薄层）→ services/（业务逻辑）→ io/（CSV/JSON 持久化）
  ├─ api/routes_metrics.py / routes_roots.py / routes_import_tasks.py
  ├─ api/middleware.py（CORS/认证/请求日志）
  ├─ api/errors.py（统一异常）
  └─ io/*_store.py / *_csv.py（原子写：tmp + replace）
```

### 5.3 LLM 集成

- `llm/env.py`：模式判定（mock/live/auto）+ Key 读取（环境变量/.env/secrets.json）
- `llm/factory.py`：按 models.csv 构建客户端，超时 LLM_TIMEOUT_S
- `llm/mock.py`：Mock 生成（相似指标复用 + 词根组合提示）
- 并发：ThreadPoolExecutor（pool.map 保持顺序）

### 5.4 存储文件布局

```
config/    domains.csv / modifier_rules.csv / models.csv / scoring_rules.json / metric_tree.csv
roots/     {domain}_roots.csv        # 构件库（按卡库分文件）
metrics/   {domain}_metrics.csv      # 卡片库（按卡库分文件）
lineage/   {domain}_lineage.json
tasks/     {task_id}.json（批量导入任务 = 待验收的评审包）
reviews/   {metric_id}.json（评审记录）
scores/    {metric_id}.json + _summary.csv
releases/  发布记录
```

---

## 6. 数据模型（核心）

### 6.1 词根 root（构件）
```
root_id: R_{DOMAIN}_{seq}  | root_cn: 中文名 | root_en: 英文名 | root_abbr: 缩写
root_type: noun/verb/adj/... | description | synonyms(;分隔) | source_model | review_status | domain_code
```

### 6.2 指标 metric（卡片）
```
metric_id: M_{DOMAIN}_{XXX} | metric_cn | metric_en | domain_code | root_ids(;分隔)
metric_type: atomic/derived/composite | caliber_desc | unit | frequency | owner
category_l1/l2 | value_type | dimensions | scenario | formula | formula_cn | tech_caliber
source_table | data_sources | precision | alert_rules | reports | review_status | version
```

### 6.3 批量导入任务 import_task（待验收评审包）
```
task_id: T{batch}_{seq} | batch_id | group_no | total_rows | status(pending/processing/reviewing/done)
dedup_result{total,dup_count,suspect_count,new_count} | generated[行] | review_progress{reviewed,approved,rejected,total}
```

### 6.4 血缘 lineage（加工链）
```
domain | lineages[{lineage_id, target_table, target_table_cn, target_layer,
  metric_ids[], source_tables[{table_name, table_cn, source_layer, source_system}]}]
```

### 6.5 表 table（数据包，规划 B10）
```
table_id: T_{DOMAIN}_{seq} | table_name | table_cn | layer(ods/dwd/dws/ads)
domain_code | owner | source_system | description | review_status
```

### 6.6 字段 field（素材，规划 B10）
```
field_id: F_{TABLE}_{seq} | field_name | field_cn | data_type | root_ids(词根映射;分隔)
table_id | precision | description | review_status
```

---

## 7. 开发路线图（里程碑）

| 里程碑 | 内容 | 目标 | 状态 |
|--------|------|------|------|
| M1 平台可用 | 核心功能全部落地 + 基线修复（编辑全字段/落盘、卡片布局、API 企业级基础） | 可日常使用 | ✅ 已完成（2026-08-07） |
| M2 企业级加固 | B1 版本化 / B2 认证默认开 / B3 分页 / B4 审计日志 | 达到内网企业级标准 | 🚧 待启动 |
| M3 体验升级 | B5 Vue3 框架化 / B6 评审企业级化 / B7 全平台隐喻视觉统一 | 生产力优先 + 隐喻自洽的成熟 UI | ❌ 待规划 |
| M4 数据底座 | B8 SQLite 迁移、多用户权限、实时血缘 | 多用户协作 | ❌ 远期 |

**建议顺序**：M2（加固）→ M3（体验）→ M4（底座）。M1 已完成，当前处于 M2 起点。

---

## 8. 开发约束与规范（开发 Agent 必读）

1. **代码修改后必须提交 git**（项目铁律），commit message 遵循 `<type>(<scope>): <description>`，一个 commit 只做一件事
2. **外科手术式改动**：只改必须改的，不顺手重构无关代码
3. **测试先行**：新功能/修复必须带 pytest 用例；全量测试通过（196+ 基线）才允许提交
4. **API 设计**：新接口遵循第 4.1 节规范（错误码、HTTP 语义、路径安全）；列表接口按 B3 规划加分页
5. **编辑字段白名单**：批量导入 EDITABLE_FIELDS 增删需前后端同步（routes_import_tasks.py 与 batch-import.js editCardHtml）
6. **LLM 调用**：必须考虑超时（DATA_GOV_LLM_TIMEOUT）与降级（无 Key → mock）
7. **环境注意**：本地 `.env` 已配 DEEPSEEK_API_KEY，`DATA_GOV_LLM_MODE=auto` 时 AI 走真实 DeepSeek（单次 30s+ 正常）；调试用 `DATA_GOV_LLM_MODE=mock`
8. **隐喻语言**：UI 文案与产品术语统一使用第 1.5 节映射（构件/卡库/数据包/成品卡/稀有度）；说「卡库」不说「卡盒」，说「数据包/评审包」分清表与批量导入组，说「素材」不说「卡」；**口径治理的地位不得被隐喻弱化**
9. **UI 方向**：企业级程序规范优先；卡牌隐喻保留为产品语言，交互形态向生产力收敛（表格/抽屉/分栏为主，卡牌作展示态）；可用 impeccable / board-game-ui / web-design-guidelines 辅助
10. **第三方依赖**：引入 skill/库前检查许可证与安全（如 board-game-ui 为 restricted 许可，商用需确认上游 fil512/upship）

---

## 9. 全局验收标准

- [ ] 全部 pytest 通过（当前基线 196）
- [ ] 词根/指标/血缘/口径/评分/发布六大核心模块可操作
- [ ] 批量导入全流程：上传→生成→评审→编辑→入库 无断点
- [ ] API 错误响应统一（detail + code），500 不泄露内部信息
- [ ] 服务日志可见、可配级别；LLM 超时可控
- [ ] 页面在 mock 与 live 模式下均可正常操作
- [ ] 所有修改已提交 git，commit 语义清晰
- [ ] 产品文案统一采用隐喻术语（构件/卡库/数据包/成品卡），无"卡盒/碎片"等冲突叫法
- [ ] 指标卡面可回溯其词根组合（构件槽），口径评审链路完整（隐喻边界守得住）

---

## 10. 风险与依赖

| # | 风险 | 级别 | 说明与应对 |
|---|------|------|-----------|
| R1 | 隐喻边界被弱化 | 中 | 用户可能误以为"词根拼一拼就是指标"，忽略口径。应对：产品原则 + 验收标准强制（见 1.5/9 章），卡面同时突出"构件"与"口径"两块 |
| R2 | live 模式依赖外部 LLM | 中 | DeepSeek 响应慢（单次 30s+）、网络抖动会导致 process 等待。应对：60s 超时兜底 + mock 降级 + 异步任务进度 |
| R3 | 单机文件存储 | 中 | CSV 无事务、进程内锁，多用户并发写会互相覆盖。应对：当前单机可用（B8 升级 SQLite） |
| R4 | 认证默认关闭 | 高 | 未配 DATA_GOV_API_KEY 时无鉴权，端口暴露即裸奔。应对：B2 待办（未配 Key 拒绝启动） |
| R5 | 第三方 skill 许可 | 低 | board-game-ui 标注 NOASSERTION/restricted。应对：仅内部原型使用；商用前确认上游许可（已记录） |
| R6 | 前端技术债 | 中 | 原生 JS 约 1.4 万行、多处 inline onclick。应对：B5 Vue3 渐进式迁移 |
| R7 | B10 表资产范围蔓延 | 中 | 表/字段/血缘可维护化的实施面大（涉及血缘数据结构变更），若一次性全做易挤占 M2/M3 排期。应对：分期 —— 先表+字段 CRUD 与词根映射，再改造血缘为可维护关系 |

---

## 11. 修订记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-08-07 | 基线版：现状盘点 + 功能需求 + 企业级规范 + 路线图 |
| v1.1 | 2026-08-07 | 新增 1.5 产品隐喻（卡牌世界↔数据治理，产品确认）、1.6 术语表、第 10 章风险与依赖；B6/B7 更新为"隐喻保留 + 企业级收敛"；开发约束补充隐喻语言与第三方许可条目；验收标准补充隐喻一致性 |
| v1.2 | 2026-08-07 | **隐喻映射修正**（采纳产品直觉）：表=数据包（非锻造车间）、主题域=卡库（非卡盒）、字段=素材；新增隐喻边界 4 条；新增 3.11 表资产管理（规划 B10）+ 6.5/6.6 表/字段数据模型 + 待办 B10 + 风险 R7 |
