# workflow搭建skill

用于 **需求分析、Agent / Workflow 方案设计、SOP 流程搭建和工作流开发交付** 的技能集合。

本仓库包含三个可独立使用的 Skill，帮助 AI 助手把业务资料整理成可理解的流程方案，并在具备相应工具和授权时推进实施。每个技能都包含 `SKILL.md`，并按需要配有参考文档、模板或脚本。

适合需要设计售前咨询、客服、销售跟进、直播运营等多阶段业务流程的开发者、运营人员和方案设计人员。工作流的具体产品规则、平台能力和验收标准由当前项目决定。

## 三个技能怎么选

| 技能 | 适合什么时候使用 | 主要工作与产出 |
| --- | --- | --- |
| [workflow-planner](workflow-planner/SKILL.md) · 需求分析与方案设计 | 有需求文档、业务资料或初步想法，需要先想清楚怎么做 | 梳理目标和场景、发现信息缺口、比较方案，形成流程蓝图、节点与变量设计、实施建议 |
| [sop-workflow-builder](sop-workflow-builder/SKILL.md) · SOP 工作流搭建 | 业务有明确阶段、触发事件、条件分支和固定话术 | 拆分阶段、状态变量、事件和路由，设计固定回复、LLM 节点、人工交接、无回复规则及测试用例 |
| [workflow-delivery](workflow-delivery/SKILL.md) · 工作流开发与交付 | 已有目标应用或需要在具体平台实施、排查和交付 | 接手项目、核实版本和平台能力、分析日志、修改草稿，并按任务授权完成测试、发布与回读核对 |

刚开始一个项目时，可以先用 `workflow-planner` 明确方案；业务需要严格的分阶段 SOP 时，再用 `sop-workflow-builder` 细化状态与路由；进入具体平台实施时，使用 `workflow-delivery`。

三个技能可以单独使用，不要求每个项目都依次调用全部技能。`workflow-planner` 的方案也可以交给其他实施工具或人员继续完成。

## 安装到 Codex

### 方式一：让技能安装器从仓库安装

在提供 `$skill-installer` 的 Codex 环境中输入：

```text
$skill-installer 请从 https://github.com/lyqf000w/workflow-skill
安装 workflow-planner、sop-workflow-builder 和 workflow-delivery 三个目录中的技能。
```

也可以只指定其中一个技能。安装后如果没有显示，重启 Codex 再检查技能列表。

### 方式二：手动复制完整技能目录

下载本仓库，或使用 Git 克隆：

```bash
git clone https://github.com/lyqf000w/workflow-skill.git
```

把需要的技能文件夹整体复制到 Codex 的技能目录，保留其中的 `references/`、`assets/`、`agents/` 和 `scripts/` 等子目录。

| 使用范围 | 目录 |
| --- | --- |
| 仅当前项目 | 项目根目录下的 `.agents/skills/` |
| 当前用户的多个项目 | `~/.agents/skills/`，Windows 下对应 `%USERPROFILE%\.agents\skills\` |

例如，安装到某个项目后应形成以下结构：

```text
你的项目/
└── .agents/
    └── skills/
        ├── workflow-planner/
        │   └── SKILL.md 及其配套目录
        ├── sop-workflow-builder/
        │   └── SKILL.md 及其配套目录
        └── workflow-delivery/
            └── SKILL.md 及其配套目录
```

每个 `SKILL.md` 应位于对应技能文件夹的根目录。已经通过现有环境安装过同名技能时，先确认实际加载位置，避免重复安装。

以上安装位置与调用方式参考 [OpenAI 官方技能文档](https://learn.chatgpt.com/docs/build-skills)。仓库中的文件需要被当前工具识别和加载后，才会作为技能使用。

## 使用示例

以下示例采用 Codex 的 `$技能名` 调用方式。使用支持技能选择器的界面时，也可以先选择对应技能，再描述任务。

### 1. 先分析需求和比较方案

```text
$workflow-planner
请根据我提供的业务资料，梳理这个售前咨询项目的目标、主要场景和信息缺口。
比较可行方案，给出推荐的 Workflow 蓝图、关键节点、必要变量和实施顺序。
本次先做方案设计。
```

### 2. 把业务 SOP 拆成阶段、状态和分支

```text
$sop-workflow-builder
请把我提供的客户跟进 SOP 拆成可搭建的工作流。
列出阶段、状态变量、触发事件、条件分支、固定回复和 LLM 节点职责，
并根据业务资料设计转人工规则、无回复规则和测试用例。
```

### 3. 接手已有工作流并修改草稿

```text
$workflow-delivery
请接手我提供的工作流应用，先核实草稿、已发布版本和平台能力。
排查重复询问问题，备份现有配置，按本次需求修改草稿，
完成已授权的测试和保存后回读。本次暂不发布。
```

提供资料时，尽量说明：服务对象、业务目标、已有流程或应用地址、必须保留的规则、本次允许的操作以及验收要求。信息不完整时，先梳理已有材料，再确认影响核心方案的缺口。

## 配套脚本

`workflow-delivery` 提供三个 Python 脚本：

| 文件 | 用途 |
| --- | --- |
| [workflow_core.py](workflow-delivery/scripts/workflow_core.py) | 在本地解析工作流、比较配置差异、检查图结构与常见引用 |
| [workflow_api.py](workflow-delivery/scripts/workflow_api.py) | 对已适配的 Console API 执行快照、日志读取、运行请求、带基线检查的草稿保存和发布 |
| [test_workflow_tools.py](workflow-delivery/scripts/test_workflow_tools.py) | 使用合成数据、临时文件和模拟客户端进行离线自测 |

运行环境为 **Python 3.10+**。JSON 处理、接口请求和离线自测使用标准库；读取 YAML 时另需安装 `PyYAML`。

在本仓库根目录查看帮助或运行离线自测：

```bash
python -B -X utf8 workflow-delivery/scripts/workflow_core.py --help
python -B -X utf8 workflow-delivery/scripts/workflow_api.py --help
python -B -X utf8 workflow-delivery/scripts/test_workflow_tools.py
```

离线自测验证的是脚本行为，不代表某个业务流程或平台接口已经通过实测。远程操作的参数、前提和示例见 [脚本使用说明](workflow-delivery/references/script-usage.md)。

## 仓库结构

```text
workflow-skill/
├── README.md
├── workflow-planner/
│   ├── SKILL.md
│   ├── agents/          # 技能名称、简介与默认提示
│   ├── assets/          # 方案模板
│   └── references/      # 需求分析、方案取舍与蓝图设计
├── sop-workflow-builder/
│   ├── SKILL.md
│   ├── agents/
│   └── references/      # SOP 参考模式与工作流蓝图模板
└── workflow-delivery/
    ├── SKILL.md
    ├── agents/
    ├── assets/          # 项目记录模板
    ├── references/      # 项目接手、设计、平台操作、验证与发布
    └── scripts/         # 本地检查、Console API 辅助与离线自测
```

## 使用边界

- **按当前任务确定操作范围。** 方案设计、修改草稿、真实运行和发布分别对应不同操作；说明本次需要完成哪些步骤。已有明确授权应沿用，范围变化时再确认。
- **平台操作依赖实际工具与有效授权。** 技能提供方法、资源和辅助脚本；运行环境仍需具备对应平台的访问能力。当前 API 脚本仅覆盖已适配的 Console 结构，其他平台需要先核实和适配。
- **区分参考模式和当前业务规则。** SOP 目录中的既有业务参考用于借鉴流程结构，产品边界、联系方式、留资条件和固定话术应以当前项目为准。
- **凭据和项目证据放在受控位置。** Token、Cookie、Webhook 密钥、客户日志及原始工作流备份不应提交到公开仓库。脚本支持从已授权的进程环境变量或隐藏输入读取 Token，具体方法见脚本说明。
- **以实际验证结果交付。** 本地检查、保存成功、业务测试和发布回读各自证明不同内容；记录已验证和未验证的部分。

## 进一步阅读

- 需求与方案：[需求分析和方案取舍](workflow-planner/references/requirements-and-options.md) · [蓝图设计与场景推演](workflow-planner/references/blueprint-and-walkthrough.md) · [方案模板](workflow-planner/assets/workflow-proposal-template.md)
- SOP 设计：[工作流蓝图模板](sop-workflow-builder/references/workflow-blueprint-template.md) · [直播流程参考](sop-workflow-builder/references/fengnuo-pattern.md) · [B2B 售前流程参考](sop-workflow-builder/references/shenzhou-digital-pattern.md)
- 开发交付：[项目接手](workflow-delivery/references/project-intake.md) · [设计规范](workflow-delivery/references/design-standard.md) · [平台操作](workflow-delivery/references/platform-console.md) · [验证与发布](workflow-delivery/references/verification-release.md)
