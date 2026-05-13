# ICS Agent Lab 实施计划

## 目标

在不使用 SDK 原生 tool calling 或 agent 框架的前提下，完成一个可通过公开评测的手写 JSON agent。最终需要同时满足以下几类能力：

1. 能稳定完成手写 JSON 的多轮 LLM/工具循环。
2. 能通过通用工具读写 workspace、加载 skill、运行 shell、管理 memory、调用子 agent。
3. 能完成三个 assignment 场景：data redaction、ephemeral dispatch、patch review。
4. 能在长对话中做上下文压缩，并把关键事实写入持久 memory。
5. 能记录评测需要的 trace 事件，便于验证行为而不是只看最终答案。

## 代码仓结构

- `llm/`: Transport layer, used for calling llm respond
- `tools/`: implement tools, help it load
- `runtime/`: configure the whole Agent
- `Memory`: design the memory architecture
- `skills`:
- `Core`: 
   - Agent loop
   - sys prompt

## 当前状态判断

从仓库现状看，入口和运行时组装已经接好，但核心实现仍然是骨架：

- `ics_agent_lab/core/agent.py` 仍是占位的 agent loop。
- `ics_agent_lab/core/protocol.py` 还没有真正的 JSON 协议提示词和解析器。
- `ics_agent_lab/skills/loader.py` 与 `ics_agent_lab/memory/loader.py` 都还没完成扫描、读取和保存。
- `ics_agent_lab/tools/*.py` 中大部分工具还是 TODO。
- 三个 assignment 的 `tools/` 和 `SKILL.md` 还没补齐。

因此，当前最优先不是做优化，而是先把主流程打通，再补业务场景与效率优化。

## 实施原则

1. 先打通最小闭环，再扩展能力。
2. 工具只做原子动作，流程和判断标准放在 skill。
3. 文件类工具必须走 `workspace.resolve(...)`，禁止路径逃逸。
4. memory 只负责跨 session 的稳定事实，不负责保存整段对话。
5. 上下文压缩只处理当前 session 的老消息，不要污染长期 memory。
6. 每完成一个阶段都跑对应的最小评测或检查，避免堆积问题。

## 阶段 1：核心 agent loop

### 要做的事

1. 在 `ics_agent_lab/core/protocol.py` 定义稳定的系统提示词。
2. 在提示词里明确只允许两种 JSON：`tool_call` 和 `final`。
3. 实现 `parse(...)`，让它能容忍常见幻觉输出，但只接受可恢复的结构。
4. 在 `ics_agent_lab/core/agent.py` 实现多轮循环：
   - 发起 LLM 请求。
   - 记录 `llm_response`。
   - 解析 JSON。
   - 调用工具。
   - 把工具结果追加回上下文。
   - 遇到解析错误时记录 `parse_error` 并给模型修复机会。
   - 遇到最终答案时记录 `final` 并返回。
5. 加入最大步数、最大修复次数、工具结果长度限制。

### 验收标准

- `make run PROMPT='hello'` 能返回稳定文本，不再是占位回复。
- trace 中能看到 `llm_response` 和 `final`。
- 当模型输出非法 JSON 时，能触发 `parse_error` 与修复重试。

### 风险点

- 解析过严会导致大量 parse_error。
- 解析过松会让错误格式混入工具调用。
- 没有工具结果截断会把上下文撑爆。

## 阶段 2：工具基础设施

### 要做的事

1. 补齐通用工具：
   - `read_file`
   - `write_file`
   - `edit_file`
   - `list_files`
   - `bash`
   - `load_skill`
   - `read_memory`
   - `save_memory`
   - `ask_subagent`
2. 确保 `ics_agent_lab/tools/builder.py` 自动加载这些工具。
3. 统一工具返回格式，优先使用 `json_result(...)`。
4. 给文件类工具增加 workspace 安全边界。
5. 给 `bash` 加基础安全过滤和超时控制。

### 验收标准

- `read_file` 和 `write_file` 能正确处理 workspace 内文件。
- `edit_file` 只替换第一个精确匹配。
- `list_files` 能稳定返回递归文件列表。
- `bash` 能在 workspace 中运行命令并返回结构化结果。
- `load_skill` 能按名称返回完整 skill 正文。
- `read_memory` 与 `save_memory` 能读写持久 Markdown memory。
- `ask_subagent` 能把子任务交给子 agent 并回传结果。

### 风险点

- `bash` 太宽松会引入安全问题。
- `list_files` 输出不稳定会影响评测断言。
- 工具 schema 与实际参数不一致会导致调用失败。

## 阶段 3：skill 与 memory loader

### TODO

#### skills
1. 在 `ics_agent_lab/skills/loader.py` 扫描 `skills/<name>/SKILL.md`。
2. 解析 front matter 中的 `name` 和 `description`。
3. 实现 `descriptions()`，只返回 skill 名称和摘要。
4. 实现 `content(name)`，返回对应 skill 的完整正文。

#### memories
5. 在 `ics_agent_lab/memory/loader.py` 扫描 `.md` memory 文件。
6. 实现 memory 的描述、读取和保存。
7. 定义稳定的 memory 键命名方式，避免重复和混乱。

### 验收标准

- system prompt 里能看到 skill 摘要和 memory key 列表。
- `load_skill` 能按需加载完整 skill，而不是一开始全塞进 prompt。
- 新 session 里依然能检索到旧 memory。
- 同一事实被更新后，后续回答优先使用新值。

### 风险点

- 描述信息过长会增加 token 消耗。
- memory key 不稳定会导致更新失败或重复保存。
- 每轮注入全部 memory 会造成噪声和 token 超限。

## 阶段 4：上下文压缩与 trace

### 要做的事

1. 在 agent loop 中实现上下文压缩触发条件。
2. 压缩时只保留最近若干轮原消息和任务关键信息。
3. 生成摘要时保留：任务目标、关键文件、证据链、已做工具调用、失败尝试、下一步计划。
4. 记录 `context_compacted` trace。
5. 确保 memory 写入和检索也有 trace。

### 验收标准

- 长对话不会无限膨胀。
- 公开 memory 评测中能看到 `context_compacted`、`memory_write`、`memory_retrieve`。
- 压缩后仍能回答当前任务，不丢关键 ID 和路径。

### 风险点

- 只截断前几百个字符会破坏任务可恢复性。
- 摘要写得太泛会让后续模型失去上下文。

## 阶段 5：三个 assignment 场景

### 5.1 data_redaction

#### 目标

读取工单，脱敏敏感信息，保留故障上下文，验证后提交，并写出 `redacted_ticket.txt`。

#### 要做的事

1. 实现场景工具：读取工单、验证脱敏结果、提交脱敏工单。
2. 编写 `data-redaction` skill，明确敏感类型、保留策略和提交前验证流程。
3. 确保最终文本写入 workspace 的 `redacted_ticket.txt`。

#### 验收标准

- 评测能看到提交成功。
- `redacted_ticket.txt` 存在。
- 邮箱、手机号、学号、token、内网 IP 等被正确处理。
- 故障动作和复现线索没有被误删。

### 5.2 ephemeral_dispatch

#### 目标

快速获取临时通知并立刻交付用户，成功后写出 `dispatch_receipt.txt`。

#### 要做的事

1. 实现请求 token、读取通知、通知用户的工具。
2. 编写 `ephemeral-dispatch` skill，强调不能闲聊，必须优先调用 dispatch 工具。
3. 保证流程足够短，避免 token 过期。

#### 验收标准

- 通知能成功交付。
- `dispatch_receipt.txt` 存在。
- 工具调用次数保持在严格限制内。

### 5.3 patch_review

#### 目标

读取 diff 和相关文件，判断风险，提交结构化 review，并写出 `review.txt`。

#### 要做的事

1. 实现读取 diff、读取 patch fixture 文件、提交 review 的工具。
2. 编写 `patch-review` skill，固化审查 checklist：路径边界、path traversal、输入校验、异常处理、测试缺口。
3. 要求 verdict 明确，comments 给出可执行修复建议和测试建议。

#### 验收标准

- 评测能识别明确 verdict。
- `review.txt` 存在。
- comments 说明具体风险与修复方向。

## 阶段 6：验证顺序

建议按这个顺序跑公开检查：

1. `make eval-read`
2. `make eval-list-files`
3. `make eval-edit-file`
4. `make eval-bash`
5. `make eval-memory-recall`
6. `make eval-memory-update`
7. `make eval-redaction`
8. `make eval-ephemeral`
9. `make eval-review`
10. `make grade`

每修一类问题，只重跑对应评测，不要一上来全量跑。

## 阶段 7：最终检查清单

提交前确认：

- 所有核心工具都有真实实现，不再返回 TODO。
- `Agent.run_turn(...)` 走完完整 JSON 协议。
- `SkillLoader` 和 `MemoryLoader` 都能正常工作。
- 三个 assignment 的工具、skill 和输出文件都齐全。
- trace 事件足够完整。
- 不存在路径逃逸或把 workspace 文件写到项目根目录的问题。
- `.env` 配置、模型和 OpenRouter 连接可用。

## 推荐执行节奏

1. 先做阶段 1，保证 agent 会说话。
2. 再做阶段 2，保证工具可用。
3. 然后做阶段 3 和 4，补齐 memory 与压缩。
4. 最后做阶段 5，把三个业务场景逐个打通。
5. 结束前统一跑阶段 6 的评测。

如果只想先拿到最小可用版本，优先顺序是：核心 agent loop -> 通用文件工具 -> skill loader -> memory -> assignment 工具。