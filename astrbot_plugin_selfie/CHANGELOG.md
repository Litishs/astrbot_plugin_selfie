# Changelog

All notable changes to the `astrbot_plugin_selfie` project will be documented in this file.

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
