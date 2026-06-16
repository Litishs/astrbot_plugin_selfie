# Changelog

All notable changes to the `astrbot_plugin_selfie` project will be documented in this file.

## [1.2.0] - 2026-06-15

### Added

- **提示词模板外置化**：System Prompt 移至 `templates/` 目录，用户可直接编辑模板文件来定制 LLM 行为，无需修改代码
  - `templates/structured_system.txt` — 角色人格卡模式（结构化槽位填充）
  - `templates/free_system.txt` — 通用模式（自由输出），支持 `{style_instruction}` 占位符
- **场景元素自动提取**（`_extract_scene_elements`）：独立 LLM 调用从对话上下文中识别物理动作/物品
  - 例如用户提到"在吃冰淇淋" → 提取为 `eating ice cream` → 显式注入到 prompt 生成中
  - 只在有相关场景元素时才触发，无场景时跳过（无额外开销）
- **双模式 prompt 增强**：结构化模式和自由模式均新增场景元素注入点，确保场景动作出现在最终图片中

### Changed

- `_build_prompt()` 新增 `scene_elements` 参数，支持显式场景元素注入
- `_do_selfie()` 流水线增加场景提取步骤（在上下文获取之后、prompt 生成之前）
- System Prompt 新增规则：要求 LLM 将对话中提到的场景动作/物品纳入 slots 描述
- 预定义类级别常量 `_DEFAULT_STRUCTURED_SYSTEM` 和 `_DEFAULT_FREE_SYSTEM`，作为模板文件缺失时的回退
- 模板系统默认启用：插件启动时 `templates/` 自动创建，缺失时使用内置默认（零破坏性）

### Technical Details

- 模板使用 `.txt` 纯文本格式，`{style_instruction}` 占位符由代码自动替换
- 场景提取 LLM 调用极其轻量（max 12 words 输出），token 消耗极低（约 100-200 token/次）
- 模板修改后需重启/重载插件生效（一次加载、运行时不变）
- 完全向后兼容：无新配置项，已有设置无需修改

## [1.1.0] - 2026-06-11

### Added

- **第一人称自拍沉浸感机制**（结构化模式）：
  - system prompt 全面重构，强调"相机在角色手中"的第一人称视角
  - 新增 `framing` 槽位，控制自拍构图（近景/半身/全身/镜子自拍）
  - 6 槽位结构化输出：`expression` → `pose` → `background` → `lighting` → `mood` → `framing`
  - 槽位示例词引导，提升 LLM 输出质量
- **自由模式沉浸感增强**：
  - 明确的 "camera is in the character's hand — NOT a third-party observer" 指令
  - 要求 prompt 包含自拍特定细节（framing、角度、面部光线）
- **质量标签升级**：追加 `intricate details`, `natural skin texture`, `sharp focus`
- `CHANGELOG.md` 版本更新日志

### Changed

- system prompt 文本全面重写，强化第一人称自拍 POV（两种模式均涉及）
- `style_map` 描述更新：从通用人像描述改为自拍构图描述
- prompt 组装逻辑优化：结构化模式下以 `selfie photo` 开头，各槽位按视觉重要性排序
- `metadata.yaml` 版本号从 `1.0.0` 升级至 `1.1.0`

### Technical Details

所有 prompt 工程优化均在 system prompt 层面实现，**不依赖特定 LLM 或图像模型**：
- 配置 `ds-v4-flash` / `千问 wan2.7` 等任意模型均可生效
- 无新配置项添加，`_conf_schema.json` 无需变更
- 完全向后兼容，已有配置无需修改

## [1.0.0] - 2026-06-10

### Added

- 初始版本发布
- `/selfie`、`/自拍`、`/拍照`、`/selfie_view` 指令
- 自然语言触发机制（"我想看看你"等关键词）
- OpenAI 兼容格式图片生成（SiliconFlow、智谱 CogView 等）
- 自定义 API 模板模式（通义万相 qwen-image-2.0-pro）
- 三视图参考图（`data/reference.png`）确保角色长相一致性
- AstrBot 角色人格卡读取（`use_persona` 配置）
- 对话上下文分析，根据聊天氛围生成自拍
- 多输出风格支持（auto / anime / realistic / semi-realistic）
- AstrBot Provider 系统深度集成，自动读取 API Key 和模型配置
