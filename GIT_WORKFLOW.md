# Git & GitHub 项目操作指南

本指南涵盖使用 Git 和 GitHub 管理 `astrbot_plugin_selfie` 项目时的核心操作流程。

---

## 目录

- [环境准备](#环境准备)
- [克隆项目](#克隆项目)
- [分支策略](#分支策略)
- [日常开发流程](#日常开发流程)
- [代码提交规范](#代码提交规范)
- [同步远程仓库](#同步远程仓库)
- [Pull Request 流程](#pull-request-流程)
- [发布新版本](#发布新版本)
- [冲突解决](#冲突解决)
- [常见问题](#常见问题)

---

## 环境准备

### 安装 Git

```bash
# 验证 Git 是否已安装
git --version
```

若未安装，从 [git-scm.com](https://git-scm.com) 下载安装。

### 配置用户信息（首次使用）

```bash
git config --global user.name "你的名字"
git config --global user.email "你的邮箱@example.com"
```

### 配置 SSH（推荐，避免每次输入密码）

```bash
# 生成 SSH Key
ssh-keygen -t ed25519 -C "你的邮箱@example.com"

# 查看公钥
cat ~/.ssh/id_ed25519.pub
```

将输出的公钥添加到 GitHub：Settings → SSH and GPG keys → New SSH key。

验证连接：

```bash
ssh -T git@github.com
# 输出：Hi xxx! You've successfully authenticated...
```

---

## 克隆项目

### HTTPS（首次）

```bash
git clone https://github.com/Litishs/astrbot_plugin_selfie.git
cd astrbot_plugin_selfie
```

### SSH（配置 SSH 后）

```bash
git clone git@github.com:Litishs/astrbot_plugin_selfie.git
cd astrbot_plugin_selfie
```

---

## 分支策略

项目采用 **GitHub Flow**（轻量级分支模型）：

```
main  ─── 稳定版本，始终可部署
    │
    ├── feat/new-feature    ← 新功能开发
    ├── fix/bug-name        ← Bug 修复
    ├── refactor/xxx        ← 代码重构
    └── docs/xxx            ← 文档更新
```

**规则**：
- `main` 分支始终保持稳定，禁止直接推送。
- 所有改动在**功能分支**上完成，通过 **Pull Request** 合并。
- 功能分支完成后及时删除，保持仓库整洁。

### 分支命名规范

| 前缀 | 用途 | 示例 |
|------|------|------|
| `feat/` | 新功能 | `feat/support-multi-image` |
| `fix/` | Bug 修复 | `fix/prompt-too-long` |
| `refactor/` | 重构 | `refactor/api-call-logic` |
| `docs/` | 文档 | `docs/add-api-example` |

---

## 日常开发流程

### 1. 同步 main 分支

```bash
# 切换到 main
git checkout main

# 拉取最新代码
git pull origin main
```

### 2. 创建功能分支

```bash
# 从 main 创建新分支
git checkout -b feat/your-feature-name
```

### 3. 查看当前状态

```bash
git status
```

建议在每次 `add` 前检查状态，确认改动的文件是否正确。

### 4. 暂存改动

暂存单个文件：

```bash
git add path/to/file.py
```

暂存所有改动（谨慎使用，确认无敏感文件）：

```bash
git add -A
```

建议逐个添加文件，避免误添加：

```bash
git add astrbot_plugin_selfie/main.py
git add astrbot_plugin_selfie/_conf_schema.json
```

### 5. 提交

```bash
git commit -m "type: 简短的描述"
```

见下方[提交规范](#代码提交规范)。

### 6. 提交多个独立改动

当工作区包含多个不相关的改动时，分步提交：

```bash
git add main.py
git commit -m "fix: correct prompt length validation"

git add _conf_schema.json
git commit -m "feat: add use_persona config option"
```

### 7. 推送到远程

```bash
# 首次推送（当前分支无远程跟踪）
git push -u origin feat/your-feature-name

# 后续推送
git push
```

### 8. 创建 Pull Request

推送到 GitHub 后，在网页端或通过 gh-cli 创建 PR：

```bash
# 安装 GitHub CLI 后
gh pr create --title "feat: 简短描述" --body "详细说明改动内容"
```

---

## 代码提交规范

### 提交信息格式

```
<type>: <简短描述>

<详细说明（可选）>
```

### Type 类型

| Type | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat: add anime style support` |
| `fix` | Bug 修复 | `fix: resolve 404 error on image API` |
| `refactor` | 重构 | `refactor: extract image API caller` |
| `docs` | 文档 | `docs: update README config table` |
| `style` | 格式 | `style: format code with ruff` |
| `chore` | 杂项 | `chore: update requirements.txt` |

### 最佳实践

- **描述要清晰**：说明"为什么改"而非"改了啥"
  - 好：`fix: handle empty reference image when no base64`
  - 差：`fix: fix bug`
- **一个提交只做一件事**：修复 Bug 和添加功能分开提交。
- **描述使用英文**：项目使用英文提交信息，保持统一。
- **长度控制**：第一行不超过 72 字符。

---

## 同步远程仓库

### 推送本地提交

```bash
git push
```

### 拉取远程更新

```bash
git pull
```

`git pull` = `git fetch` + `git merge`。若只想查看远程更新但不合并：

```bash
git fetch
git log --oneline main..origin/main  # 查看远程比本地多的提交
```

### 保持功能分支同步

功能分支开发周期较长时，定期同步 main 的更新：

```bash
# 方法一：rebase（推荐，历史更干净）
git checkout feat/your-feature
git rebase main

# 方法二：merge
git checkout feat/your-feature
git merge main
```

**rebase vs merge**：

| | rebase | merge |
|--|--------|-------|
| 提交历史 | 线性，整洁 ✅ | 有分叉合并节点 |
| 冲突解决 | 逐个提交解决 | 一次性解决 |
| 适用场景 | 个人分支同步 main | 多人协作分支合并 |

---

## Pull Request 流程

### 创建 PR

1. 推送功能分支到 GitHub 后进入仓库页面。
2. 点击 **"Compare & pull request"**。
3. 填写 PR 信息：

```markdown
## 改动说明

简述改了什么、为什么改。

## 测试方法

1. 在插件配置中启用 xxx
2. 发送"/selfie"指令
3. 确认日志中显示 xxx

## 相关 Issue

Closes #123
```

4. 指派 Reviewer（若有）。
5. 点击 **"Create pull request"**。

### Review 与修改

收到 Review 意见后，直接在本地修改并推送：

```bash
# 本地修改代码
git add file.py
git commit -m "fix: address review comments"
git push
```

PR 会自动更新，无需重新创建。

### 合并 PR

合并选项：

| 方式 | git 操作 | 效果 |
|------|----------|------|
| **Squash and merge** | 所有提交压缩为一个 | ✅ 推荐，main 历史干净 |
| **Rebase and merge** | 提交保持原样 | 线性历史 |
| **Merge commit** | 保留完整分叉历史 | 历史较乱 |

对本项目建议使用 **Squash and merge**。

### 合并后清理

```bash
# 切回 main 并拉取最新
git checkout main
git pull origin main

# 删除远程功能分支
git push origin --delete feat/your-feature

# 删除本地功能分支
git branch -d feat/your-feature
```

---

## 发布新版本

### 1. 更新版本号

```bash
# 修改 metadata.yaml 中的 version 字段
# v1.0.0 → v1.1.0
```

### 2. 提交版本更新

```bash
git add astrbot_plugin_selfie/metadata.yaml
git commit -m "chore: bump version to 1.1.0"
git push
```

### 3. 打标签并推送

```bash
git tag -a v1.1.0 -m "v1.1.0 - 改动简述"
git push origin v1.1.0
```

### 4. 在 GitHub 创建 Release

1. 打开 [Releases 页面](https://github.com/Litishs/astrbot_plugin_selfie/releases)。
2. 点击 **"Draft a new release"**。
3. 选择刚推送的标签。
4. 填写标题和更新日志。
5. 点击 **"Publish release"**。

---

## 冲突解决

### 产生冲突的场景

当两个分支修改了同一个文件的同一区域时，合并会产生冲突。

### 解决步骤

```bash
# 尝试合并，Git 会提示冲突
git merge main

# 查看冲突文件
git status
# 输出：both modified: astrbot_plugin_selfie/main.py
```

打开冲突文件，会看到：

```python
<<<<<<< HEAD
# 当前分支的代码
prompt = prompt[:200]
=======
# 合并进来的代码
prompt = prompt[:500]
>>>>>>> main
```

解决方式：

1. **手动编辑** — 删除 `<<<<<<<`、`=======`、`>>>>>>>`，保留需要的代码：

```python
prompt = prompt[:500]
```

2. **使用合并工具**：

```bash
git mergetool
```

### 完成后提交

```bash
git add astrbot_plugin_selfie/main.py
git commit -m "fix: resolve merge conflict in prompt length"
```

### 预防冲突

- 功能分支尽量**短生命周期**（1-3 天）。
- 开发前先 `git pull` 同步 main。
- 多人修改同一文件时提前沟通。

---

## 常见问题

### Q: 提交后发现漏了文件怎么办？

```bash
# 补加文件，合并到上一个提交
git add forgotten_file.py
git commit --amend --no-edit
git push --force-with-lease
```

> ⚠️ 仅在**未推送**或**个人分支**上使用 `--amend`。已合并到 main 的提交不要 amend。

### Q: 提交信息写错了怎么办？

```bash
# 修改最近一次提交的信息
git commit --amend -m "fix: correct commit message"
```

### Q: 误加到暂存区怎么办？

```bash
# 从暂存区移除，保留工作区改动
git reset HEAD file.py
```

### Q: 想撤销工作区的改动怎么办？

```bash
# 丢弃某个文件的改动
git checkout -- file.py

# ⚠️ 此操作不可逆，改动会丢失
```

### Q: 推送被拒绝（rejected）怎么办？

原因：远程有本地没有的提交。

```bash
# 先拉取远程更新
git pull --rebase

# 如果仍有冲突，解决后继续 rebase
git rebase --continue

# 推送
git push
```

### Q: 想回到之前的某个版本？

```bash
# 查看提交历史
git log --oneline

# 回退到某个提交（保留改动在工作区）
git reset --soft <commit-hash>

# ⚠️ 若已推送，不要使用 --hard 回退后 force push
# 这会影响其他人的仓库
```

### Q: 如何不提交暂时保存当前工作？

```bash
# 暂存当前改动
git stash

# 拉取更新或切换分支操作后恢复
git stash pop
```

### Q: 如何查看某次提交的具体改动？

```bash
git show <commit-hash>
git show HEAD         # 查看最新提交
git show HEAD~1       # 查看上一个提交
```

---

## 快速参考（命令速查表）

| 操作 | 命令 |
|------|------|
| 查看状态 | `git status` |
| 查看差异 | `git diff` |
| 暂存文件 | `git add <file>` |
| 提交 | `git commit -m "type: msg"` |
| 推送 | `git push` |
| 拉取 | `git pull` |
| 创建分支 | `git checkout -b <name>` |
| 切换分支 | `git checkout <name>` |
| 查看分支 | `git branch -a` |
| 删除本地分支 | `git branch -d <name>` |
| 删除远程分支 | `git push origin --delete <name>` |
| 打标签 | `git tag -a v1.0.0 -m "msg"` |
| 推送标签 | `git push origin v1.0.0` |
| 查看历史 | `git log --oneline --graph` |
| 暂存工作 | `git stash` |
| 恢复暂存 | `git stash pop` |

---

## 本项目专用 `.gitignore`

项目已配置 `.gitignore`，自动排除以下内容：

| 排除项 | 说明 |
|--------|------|
| `__pycache__/` | Python 缓存 |
| `*.pyc` | 编译文件 |
| `data/temp/` | 插件运行时生成的临时图片 |
| `.vscode/` / `.idea/` | IDE 配置 |
| `.DS_Store` / `Thumbs.db` | 系统文件 |

新增依赖或生成物时，记得更新 `.gitignore`。

---

> 建议将本文件放在项目根目录，方便协作时查阅。
