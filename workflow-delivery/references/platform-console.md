# Console工作流平台适配说明

## 适用边界

这是从实际Console工作流操作中沉淀的适配，不是对所有Dify或其他平台版本的兼容承诺。端点形态在2026-09-07曾被核实；新实例/升级后先用只读操作验证。本文不包含服务器地址、真实应用ID或凭据。

用户URL常见形态：`https://host/app/{app_id}/workflow` 或 `https://host/console/api/apps/{app_id}/workflows/draft`。应用ID以用户指定为准，禁止根据名字猜测另一个应用。附带`target`命令可离线提取地址与ID。

## 已观察到的端点

下表相对于明确指定的API根目录（常见为`/console/api`）：

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/apps/{app_id}/workflows/draft` | 当前草稿 |
| POST | `/apps/{app_id}/workflows/draft` | 保存草稿，带当前hash |
| GET | `/apps/{app_id}/workflows/publish` | 当前已发布工作流 |
| POST | `/apps/{app_id}/workflows/publish` | 发布当前草稿，已观察请求体为`{}` |
| GET | `/apps/{app_id}/chat-messages?conversation_id=...&limit=...` | 一页会话消息 |
| GET | `/apps/{app_id}/workflow-runs/{run_id}/node-executions` | 该次运行的节点轨迹 |
| POST | `/apps/{app_id}/workflows/draft/nodes/{node_id}/run` | 单节点调试 |
| POST | `/apps/{app_id}/advanced-chat/workflows/draft/run` | 多轮草稿会话运行，常见SSE响应 |
| GET | `/apps/{app_id}/workflows/default-workflow-block-configs` | 部分节点默认配置，不是完整能力列表 |
| GET | `/workspaces/current/model-providers/{provider}/models/parameter-rules?model=...` | 模型参数支持情况 |

消息分页方式、鉴权方式、发布版本接口等以当前实际响应为准。附带`messages`只读一页，不能把截取结果称为完整历史。会话ID、消息ID、运行ID和应用ID不可混用。

## 工作流格式

常见结构包含`graph.nodes`、`graph.edges`、`features`、`conversation_variables`，并可能有`environment_variables`、`application_variables`、`reflection_learning`等。读取/差异分析支持原始响应、`data`包裹、导出文件的`workflow`包裹。

保存接口接受字段与导出文件内容并不一定相同。附带写入适配只对已观察字段构造请求；发现新的顶层字段必须先核实是否属于可写业务配置，不能悄悄丢弃。

原始工作流快照不等于可在平台直接导入的完整DSL。不要把仅含`workflow`的备份叫作正式项目导出包。

## 需要前置核实的兼容点

- 某部署曾限制单路径50节点，不能写死为全平台规则；确认后通过脚本参数传入。
- 历史有代码节点在发布后缺失、非数字节点ID引用未展开的情况。它们是兼容线索，不是“所有非数字ID/代码节点必然不可用”的定律。新的引用要在实际渲染/调试结果中确认。
- 原生`param-parse`在观察实例中出错会终止流程，未发现可配置异常分支。其他模型/工具节点有`exception_config`也不能据此断言解析节点支持。
- LLM/参数提取器输入可能要求字符串；知识检索输出常为对象列表，不能不经类型核对直接传入字符串参数。
- 模型节点调用成功仅表示返回内容；不证明JSON语法、字段或业务动作正确。
- 草稿能保存、发布回读保留、真实运行通过，是三个不同层次。

## 调试与身份

单节点运行常见请求体为`{"inputs": {...}}`。变量键的已观察形式为`#节点ID.字段#`，解析器可能使用`arg`；部分LLM节点即使Prompt没有显式引用，也需要`#sys.query#`。先检查有效渲染后的Prompt，不能把未展开占位符下的结果算作模型表现。

多轮运行必须保留返回的`conversation_id`，不能每轮新建会话；具体输入、父消息字段和用户身份按当前应用要求提供。没有真实渠道用户ID时，涉及渠道身份的工具可能失败，要记录为环境限制，不能据此忽略其他参数或业务错误。

## 电脑界面备用路径

只有当前提供了可用浏览器/电脑工具，且符合用户选择与任务范围时才用。先读取该工具的技能或文档。确认应用ID、草稿/发布状态、当前可见控件；不盲点、不接管其他窗口、不借后台存储拿凭据。界面保存/发布也必须留备份和核对结果。

API脚本不自动启动或控制电脑；界面工具不可用时明确说明，不承诺“仅有Skill就能操作任何电脑”。
