# 配套脚本使用说明

这些脚本是辅助工具，不代替读取当前平台结构、用户授权和业务验收。先读 `platform-console.md` 与 `verification-release.md`，再决定是否适用。所有命令中的地址、UUID、文件路径必须换成本次已核实的值；示例不包含真实项目凭据。

## 环境与身份

- Python 3.10+。JSON、接口请求和自测只需标准库；读取 YAML 另外需要 PyYAML。
- 脚本所在目录由当前 Skill 的实际路径确定，迁移电脑后不要沿用旧路径。
- 使用 API，不操作桌面；其他平台、Cookie/CSRF 登录体系或不同 API 结构需要重新核实适配，不能硬套。
- `--auth-env` 只接收**已有进程环境变量的名称**，不是 Token。没有它时在交互式终端隐藏输入 Token。不要把 Token 写入命令行参数、脚本、报告或 Skill；不要输出环境变量值。
- 用户粘贴的 Request URL 仅用于定位应用，不包含有效认证。认证失败时停止受保护操作，要求有效凭据，不从浏览器或系统里寻找其他凭据。
- HTTP 会明文传输凭据。优先 HTTPS；只有用户明确接受本次 HTTP 目标时才传 `--allow-insecure-http`。脚本拒绝携带认证的重定向。
- 原始工作流备份和日志可能含密钥、客户信息、内部话术，应存入受控项目目录，不能直接公开或打包进 Skill。报告分享前另外脱敏；脚本不会保证原始证据已脱敏。

以下 PowerShell 示例假定当前目录就是 Skill 根目录，已有本次授权使用的 `WORKFLOW_SESSION_TOKEN` 进程变量。变量名仅为示例，脚本不创建或保存凭据。

## 1. 定位与备份：只读

```powershell
python -B -X utf8 scripts/workflow_api.py target "https://workflow.example.invalid/app/11111111-2222-4333-8444-555555555555/workflow"
python -B -X utf8 scripts/workflow_api.py snapshot --base-url "https://workflow.example.invalid/console/api" --app-id "11111111-2222-4333-8444-555555555555" --auth-env WORKFLOW_SESSION_TOKEN --out "C:/WorkflowProject/evidence"
```

`target` 完全离线，只解析地址。`snapshot` 获取目标应用的草稿与发布版本，保存到新建的唯一子目录，不修改远端。

备份文件：`draft_before.json`、`published_before.json`、`target.json`、`operation_report.json`。平台返回发布版本 404 时记录为 `null`；其他错误不擅自当成“从未发布”。这些是 API 原始快照，不保证等价于平台可导入的完整 DSL；如需交付可导入文件，另行核实导出接口和结构。

## 2. 本地检查、制作候选、比较

```powershell
python -B -X utf8 scripts/workflow_core.py --out "C:/WorkflowProject/evidence/local-inspection.json" inspect "C:/WorkflowProject/baseline.json"
python -B -X utf8 scripts/workflow_core.py --out "C:/WorkflowProject/evidence/local-diff.json" compare "C:/WorkflowProject/baseline.json" "C:/WorkflowProject/candidate.json"
```

`--out` 放在 `inspect` / `compare` **之前**；必须是尚不存在的新文件。未传 `--out` 时输出结构报告，不输出原始 Prompt 值。节点名称、字段路径仍可能含内部信息，分享时需要检查。

从已备份的当前草稿制作候选，在本次允许范围内编辑；不要从旧对话导出文件直接覆盖最新草稿。遵循当前环境的文件编辑规则。

检查包含：重复 ID、悬空连线、常见变量引用、条件出口、显式环、起点可达性，以及普通有向无环图的最长路径。`--max-path-nodes N` 只传入**已证实适用于当前平台的上限**，未提供时报告“上限未确认”，不假定无限或固定为某个数值。

限制：不是平台完整 Schema 校验器，不保证所有节点输出、类型转换、插件、Prompt 语义及模型稳定性已验证。循环/迭代的嵌套作用域和平台计数不按扁平图猜测；当前写入助手会拒绝嵌套流程，须先完善并验证平台适配。不要为了绕过脚本拒绝而删除业务节点。合法但暂不启用的不可达节点也需要人工审查，脚本不会自动删除。

## 3. 保存草稿：默认只生成计划

```powershell
python -B -X utf8 scripts/workflow_api.py save-draft --base-url "https://workflow.example.invalid/console/api" --app-id "11111111-2222-4333-8444-555555555555" --auth-env WORKFLOW_SESSION_TOKEN --expected "C:/WorkflowProject/baseline.json" --candidate "C:/WorkflowProject/candidate.json" --out "C:/WorkflowProject/evidence"
```

默认仍会只读远端、核对版本并备份，但不 POST。只有本次用户已授权修改时才加 `--execute`；不需要为已明确授权的同一步再反复确认。

执行前比较目标应用、配置指纹及基线自带的平台 `hash`，备份后再次读取核对；提交时使用最新 `hash`。遇到不认识的顶层配置、候选遗漏配置、其他应用的基线/候选或并发变化就停止。保存后重新 GET 并比较业务配置。失败或不一致不会自动发布、重试或回滚。

成功后得到 `draft_after.json`。**下一步测试和发布使用这个新快照作为 `--expected`，不要继续使用保存前的 hash。** 平台自动变换字段而导致读回不一致时，先查明原因，不把不一致视为成功。

## 4. 查看会话及运行节点：只读

```powershell
python -B -X utf8 scripts/workflow_api.py messages --base-url "https://workflow.example.invalid/console/api" --app-id "11111111-2222-4333-8444-555555555555" --auth-env WORKFLOW_SESSION_TOKEN --conversation-id "22222222-3333-4444-8555-666666666666" --out "C:/WorkflowProject/evidence"
python -B -X utf8 scripts/workflow_api.py executions --base-url "https://workflow.example.invalid/console/api" --app-id "11111111-2222-4333-8444-555555555555" --auth-env WORKFLOW_SESSION_TOKEN --run-id "33333333-4444-4555-8666-777777777777" --out "C:/WorkflowProject/evidence"
```

会话 ID 不等于 workflow run ID。先从消息记录中取得运行 ID，再看对应节点轨迹；不能把“没有调用组件”解释为“组件报错”。`messages` 只取一页，默认最多 100 条，报告会标注；如果还有分页，依据返回结构和已核实分页参数补查，不能声称已查看完整历史。

## 5. 节点与多轮测试：会发生真实执行

`run-node` 必须显式提供 `--node-id` 和 `--inputs` JSON 文件，默认只核对并输出计划。加 `--execute` 才实际执行。助手只接受已列出的 LLM、分类、提取、解析及部分变量处理节点，不代为测试业务工具节点。模型调用仍可能计费、处理敏感信息或写测试状态，不等于纯只读。

输入变量必须从当前节点选择器及真实接口结构取得，不凭示例猜测。例如某些实例单节点接口使用 `{"inputs":{"#sys.query#":"测试问题","#123456.text#":"测试上下文"}}`；`--inputs` 文件存内层对象。检查节点实际渲染的 Prompt 和输入，不将没有注入上下文的单节点成功计为有效测试。

`run-chat` 的 `--body` 是本平台核实过的运行请求 JSON，必须有 `query` 字符串与 `inputs` 对象，其他必需字段按当前实例补齐。不要照抄其他项目的真实 userid、附件、会话 ID 或默认业务值。

```powershell
python -B -X utf8 scripts/workflow_api.py run-chat --base-url "https://workflow.example.invalid/console/api" --app-id "11111111-2222-4333-8444-555555555555" --auth-env WORKFLOW_SESSION_TOKEN --expected "C:/WorkflowProject/current-draft.json" --body "C:/WorkflowProject/case-turn-1.json" --out "C:/WorkflowProject/evidence"
```

完整流程执行须同时有 `--execute --allow-business-effects`，且用户本次已授权相应测试及业务副作用。后一个开关只是防误触，**不是授权来源**。测试可能真的建群、推 CRM、发消息。优先经批准的隔离环境或模拟组件；公司名含“测试”仅用于标记，不会屏蔽副作用。

每次运行保存原始结果；SSE 汇总为 `events`。`round_trip_seconds` 是发起运行请求到完整响应读取结束的耗时，不是首字时间或页面用户感知耗时，也不包括前置基线核对。脚本不会自动选测试剧本、推断会话 ID 或连续重跑。下一轮从真实返回提取同一测试会话 ID，保持相同测试身份和业务状态；不同角色/剧本另起会话。逐轮记录用户输入、实际回复、耗时、状态及工具执行，不仅看 HTTP 状态或节点颜色。

超时可能意味着服务端仍在执行。先检查日志和下游结果，再决定是否补跑，不能自动重复推送。每轮执行不是“全量通过”的证明。

## 6. 发布与读回

```powershell
python -B -X utf8 scripts/workflow_api.py publish --base-url "https://workflow.example.invalid/console/api" --app-id "11111111-2222-4333-8444-555555555555" --auth-env WORKFLOW_SESSION_TOKEN --expected "C:/WorkflowProject/current-draft.json" --out "C:/WorkflowProject/evidence"
```

默认只核对、备份、记录即将发布的差异。仅在本次授权发布后加 `--execute`。用户要求“不测试直接发布”时，不发模拟客户请求，但仍做必要结构检查与读回，明确未做业务回归；发现明确阻断项不能硬发布。

此发布接口没有已验证的原子版本前置条件，二次读取到 POST 之间仍有短暂并发窗口。多人编辑时约定发布窗口；不得声称脚本能杜绝覆盖。发布后核对实际发布版本与预期配置。POST 返回 200 但读回不一致时，状态为异常/待核实，不自动重试或覆盖。

无自动回滚命令。确需回滚时，先得到本次回滚授权，读取新的当前版本，用明确的备份和新基线重新规划保存/发布，注意旧会话变量兼容性。

## 7. 离线自测

```powershell
python -B -X utf8 scripts/test_workflow_tools.py
```

只使用临时文件、合成工作流和模拟客户端，不连接项目、不消费模型、不推送线索。该测试验证脚本自身的检查和保护行为，不能证明某个新平台接口兼容或业务回复效果合格。交付时分别报告脚本自测、静态结构检查、业务测试和发布核对结果。
