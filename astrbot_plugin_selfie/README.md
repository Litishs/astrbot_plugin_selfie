# 🤳 AstrBot Selfie Plugin

**astrbot_plugin_selfie** — 让 AstrBot 中的角色能根据聊天氛围和角色设定，生成符合角色长相的自拍照。

> 📖 **更新日志**：查看 [CHANGELOG.md](CHANGELOG.md) 了解版本历史。

## ✨ 功能特点

- **📸 自拍生成** — 输入「我想看看你」「发张自拍」等自然语言，或使用 `/selfie` 指令，bot 会根据当前聊天氛围生成一张自拍照。
- **🎨 三视图参考** — 提供角色三视图（正/侧/后）合成图，确保生成的角色长相稳定一致。
- **🧠 角色人格感知** — 可选读取 AstrBot 中配置的角色人格卡，LLM 依据角色性格推断表情、姿态和氛围。
- **🔌 多模型支持** — 兼容 OpenAI 标准格式（SiliconFlow、智谱 CogView 等）和自定义 API（通义万相等）。
- **🔗 AstrBot 深度集成** — 直接读取 AstrBot Provider 系统的 API Key 和模型配置，无需额外填写密钥。
- **🌐 多平台** — 支持 aiocqhttp、Telegram、QQ 官方等平台。
- **📝 提示词模板可编辑** — LLM 提示词模板外置到 `templates/` 目录，用户可直接编辑模板文件调整 LLM 行为（如改写结构化槽位规则、调整场景提取策略），无需修改代码。
- **🎯 场景元素自动识别** — 插件从对话上下文中自动识别角色当前的动作/物品（如"吃冰淇淋"、"看书"），显式注入到自拍描述中，让画面更贴合聊天气氛。

## 📋 目录

- [安装](#-安装)
- [快速开始](#-快速开始)
- [使用指南](#-使用指南)
- [配置说明](#-配置说明)
- [技术栈](#-技术栈)
- [项目结构](#-项目结构)
- [贡献指南](#-贡献指南)
- [许可证](#-许可证)

## 📦 安装

### 前提条件

- AstrBot >= 4.16
- Python >= 3.10
- 已配置可用的 LLM 模型提供商（用于生成绘图 prompt）
- 已配置可用的图像生成模型提供商

### 安装步骤

#### 方式一：通过 AstrBot 插件市场（推荐）

1. 打开 AstrBot WebUI → 插件管理。
2. 搜索 `astrbot_plugin_selfie`。
3. 点击安装。

#### 方式二：手动安装

```bash
# 进入 AstrBot 的插件目录
cd path/to/astrbot/core/data/plugins

# 克隆仓库
git clone https://github.com/Litishs/astrbot_plugin_selfie.git

# 安装依赖
cd astrbot_plugin_selfie
pip install -r requirements.txt

# 重启 AstrBot
```

#### 方式三：下载压缩包

从 [Releases](https://github.com/Litishs/astrbot_plugin_selfie/releases) 下载最新版本，解压到 AstrBot 插件目录后重启。

## 🚀 快速开始

### 1. 准备三视图

将角色的正视图、侧视图、后视图合成为一张图片，命名为 `reference.png`，放到插件目录下的 `data/` 文件夹中：

```
astrbot_plugin_selfie/
└── data/
    └── reference.png    ← 三视图合成图
```

支持的格式：`.png`、`.jpg`、`.jpeg`、`.webp`（推荐 `.png`）。

可通过 `/selfie_view` 指令查看参考图是否生效。

### 2. 配置模型提供商

在 AstrBot WebUI → 模型提供商中，确保已添加以下两种模型：

| 用途 | 推荐提供商 | 配置方法 |
|------|-----------|---------|
| 生成绘图描述 | DeepSeek、通义千问等对话模型 | 提供商类型选 OpenAI API Chat Completion，填入 API Key 和地址 |
| 生成图片 | SiliconFlow、通义万相 qwen-image-2.0-pro 等 | 见下方说明 |

**图片生成模型配置示例（SiliconFlow）：**

```
提供商类型: OpenAI API Chat Completion
API Key: 你的 SiliconFlow API Key
API 地址: https://api.siliconflow.cn/v1
启用 → 添加模型:
  ID: siliconflow/stable-diffusion-3.5
  模型名: stable-diffusion-3.5
```

**图片生成模型配置示例（通义万相 qwen-image-2.0-pro）：**

```
提供商类型: OpenAI API Chat Completion
API Key: 你的 DashScope API Key
API 地址: https://dashscope.aliyuncs.com/compatible-mode/v1
启用 → 添加模型:
  ID: tongyi_qianwen/qwen-image-2.0-pro
  模型名: qwen-image-2.0-pro
```

### 3. 配置插件

在 AstrBot WebUI → 插件管理 → astrbot_plugin_selfie → 配置，选择：

- **LLM 模型**：选择你添加的对话模型（用于生成绘图 prompt）
- **图片生成模型**：选择你添加的图像生成模型
- **图片生成模式**：`openai`（标准 OpenAI 格式）或 `custom`（自定义格式）
- 根据所选模型调整其他配置项

### 4. 开始使用

```text
用户: 我想看看你
bot: 📸 来，拍一张~
bot: [图片]

用户: /selfie 在沙滩上看日落
bot: 📸 正在构思画面……
bot: [图片]
```

## 📖 使用指南

### 指令

| 指令 | 说明 | 示例 |
|------|------|------|
| `/selfie` | 生成自拍照 | `/selfie` 或 `/selfie 在咖啡厅看书` |
| `/selfie_view` | 查看三视图参考图 | `/selfie_view` |
| `/自拍` | `/selfie` 的中文别名 | `/自拍` |
| `/拍照` | `/selfie` 的中文别名 | `/拍照` |

### 自然语言触发

当用户消息包含配置中的触发关键词时，插件会自动响应。默认触发词：

```
我想看看你
让我看看你
发张自拍
自拍一张
看看你的样子
你现在什么样子
来张自拍
```

可在插件配置中自定义。

### 用例场景

- **日常问候**：用户说「让我看看你」，bot 生成一张日常居家自拍。
- **节日氛围**：用户在聊圣诞节时触发，bot 生成戴圣诞帽的自拍。
- **情绪关怀**：用户心情低落时触发，bot 生成温暖关怀表情的自拍。
- **角色互动**：开启了角色人格卡时，bot 会根据角色性格决定表情和姿态。

### 输出风格

| 风格 | 说明 |
|------|------|
| `auto`（推荐） | 自拍构图，自然抓拍感，由图像模型自行决定画风 |
| `anime` | 二次元动漫风格自拍 |
| `realistic` | 写实照片风格自拍 |
| `semi-realistic` | 半写实/插画风格自拍 |

### 自拍沉浸感优化

v1.1.0 引入了**第一人称自拍视角的 prompt 工程**，核心改进：

- **结构化模式（有角色人格卡）**：LLM 按 6 个槽位填写自拍描述：
  - `expression` — 角色面部表情（如：温柔微笑、俏皮眨眼）
  - `pose` — 举手机的角度和姿态（如：手机举高、歪头看镜头）
  - `background` — 自拍背景（如：阳光透过窗帘的卧室）
  - `lighting` — 光线打在脸上的感觉（如：日落暖光照在脸上）
  - `mood` — 此刻自拍的情绪氛围（如：安静的满足感）
  - `framing` — 自拍构图（如：近景脸和肩膀、半身照）
- **自由模式（无角色人格卡）**：LLM 被告知 "camera is in the character's hand — NOT a third-party observer"，强制以第一人称描述场景。
- **质量标签**：追加 `intricate details`, `natural skin texture`, `sharp focus` 等细节标签，提升成片质量。

> 所有优化均在 system prompt 层面实现，**不依赖特定模型**，切换 LLM 或图像模型也能生效。

## ⚙️ 配置说明

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `llm_provider_id` | select_provider | — | 用于生成绘图 prompt 的对话模型 |
| `image_provider_id` | select_provider | — | 用于生成图片的图像模型 |
| `image_api_mode` | string | `openai` | `openai`：标准格式；`custom`：自定义格式 |
| `image_api_url` | string | (通义万相地址) | 仅 custom 模式有效 |
| `custom_request_template` | text | (通义万相模板) | 自定义请求体 JSON 模板，支持 `{{prompt}}` 和 `{{reference_base64}}` 占位符 |
| `custom_response_path` | string | `output.choices[0].message.content[0].image` | 从 API 响应提取图片的 JSON 路径 |
| `image_size` | string | `1024x1024` | 仅 openai 模式有效 |
| `output_style` | string | `auto` | 输出风格：auto / anime / realistic / 3d-anime（3D动画渲染风格） |
| `use_persona` | bool | `true` | 是否读取 AstrBot 角色人格卡 |
| `trigger_keywords` | text | (见上方) | 自然语言触发关键词，每行一个 |

### 自定义 API 模板示例

**通义万相 qwen-image-2.0-pro（多模态图生图）：**

```json
{
  "model": "qwen-image-2.0-pro",
  "input": {
    "messages": [
      {
        "role": "user",
        "content": [
          {"image": "{{reference_base64}}"},
          {"text": "{{prompt}}"}
        ]
      }
    ]
  },
  "parameters": {
    "size": "1024*1024",
    "n": 1
  }
}
```

**Stable Diffusion / OpenAPI 兼容的非标准接口：**

```json
{
  "prompt": "{{prompt}}",
  "steps": 25,
  "width": 512,
  "height": 512,
  "init_images": ["{{reference_base64}}"]
}
```

## 🛠 技术栈

| 类别 | 技术 |
|------|------|
| **运行环境** | AstrBot >= 4.16 / Python >= 3.10 |
| **HTTP 客户端** | aiohttp >= 3.9 |
| **图片处理** | Pillow（PIL） |
| **AI 模型** | 任意 OpenAI 兼容图像生成 API（SiliconFlow、通义万相、智谱 CogView 等） |
| **LLM** | AstrBot 中配置的任意对话模型（DeepSeek、通义千问等） |

## 📁 项目结构

```
astrbot_plugin_selfie/
├── main.py                 # 插件主逻辑：指令路由、LLM prompt 生成、API 调用
├── _conf_schema.json       # 插件配置项定义（WebUI 配置面板）
├── metadata.yaml           # 插件元数据（名称、版本、作者等）
├── requirements.txt        # Python 依赖
├── CHANGELOG.md            # 版本更新日志
├── data/
│   ├── README.txt          # 三视图使用说明
│   └── reference.png       # ← 三视图合成图（用户放置）
└── README.md               # 本文件
```

### 核心文件说明

| 文件 | 职责 |
|------|------|
| `main.py` | 插件的全部核心逻辑，包括指令处理、对话上下文获取、LLM prompt 生成、图片 API 调用 |
| `_conf_schema.json` | 定义插件在 AstrBot WebUI 中的配置项，使用 `_special: select_provider` 关联模型提供商 |
| `metadata.yaml` | 插件元数据，供 AstrBot 插件管理器识别和加载 |
| `requirements.txt` | Python 依赖（`aiohttp>=3.9.0`） |

## 🤝 贡献指南

欢迎参与项目贡献！请遵循以下流程：

### 提交 Issue

- **Bug 报告**：请描述复现步骤、预期行为和实际行为，附上相关日志。
- **功能请求**：请说明需求场景和期望效果。

### 提交 Pull Request

1. Fork 本仓库。
2. 创建功能分支：`git checkout -b feat/your-feature-name`
3. 提交改动：`git commit -m "feat: add your feature"`
4. 推送到远程：`git push origin feat/your-feature-name`
5. 在 GitHub 上创建 Pull Request。

### 开发注意事项

- 代码风格请遵循 AstrBot 插件的通用规范。
- 为新增配置项同步更新 `_conf_schema.json` 中的定义。
- 确保同步更新 `README.md` 中的相关说明。
- 使用 `ruff format .` 和 `ruff check .` 格式化代码（如已安装）。

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源。

## 📬 联系方式

- 作者：Litishs
- 项目仓库：[https://github.com/Litishs/astrbot_plugin_selfie](https://github.com/Litishs/astrbot_plugin_selfie)
- 如有问题请通过 GitHub Issues 反馈。

---

**如果这个插件对你有帮助，请给一个 ⭐ Star 支持！**
