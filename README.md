# elibot-seo-geo · OpenClaw（小龙虾）Skill

艾利特机器人官网 SEO/GEO 文章写作 + 智谱 GLM-Image 自动配图 + 阿里云 OSS 永久图床。一次产出：文章主题 → 完整带图文章（封面 + 正文配图，B2B 科技信息海报风格，图片带中文标题/标注）→ 图片自动传 OSS 输出永久链接。

## 能力

- **写作**：严格遵循艾利特 1720 行 SEO/GEO 写作规范（长尾词、SEO 信息、正文 H2/H3、FAQ、总结、内链白名单、产品匹配、品牌口径、数据合规）
- **配图**：智谱 GLM-Image 生成 3-4 张 B2B 科技信息海报（3D 写实场景 + 中文文字排版），封面带标题/副标题/卖点，正文带小标题/标注
- **图床**：自动上传阿里云 OSS，输出永久 URL（兼职复制 Markdown 即可，图片永不过期）

## 环境依赖

- bash（Git Bash / Linux / macOS）
- curl
- python 3（3.8+，纯标准库实现 OSS V1 签名，无需 pip install）
- 智谱开放平台 API Key（GLM-Image）
- 阿里云 OSS（可选，用于永久图床）

## 安装到 OpenClaw

### 方式一：本地技能目录（推荐）

1. 解压本包，把 `elibot-seo-geo/` 放到 OpenClaw 技能目录（任选其一）：
   - 全局共享：`~/.openclaw/skills/elibot-seo-geo/`
   - 工作区：`<workspace>/skills/elibot-seo-geo/`
2. 重载技能：
   ```bash
   openclaw gateway restart
   ```
3. 验证：
   ```bash
   openclaw skills list    # 应看到 elibot-seo-geo
   ```
4. （可选）若技能加载不到，执行 `openclaw skills scan` 后重试。

### 方式二：ClawHub

把整个 `elibot-seo-geo/` 打包成 zip 上传到 ClawHub，再 `clawhub install <user>/elibot-seo-geo`。

## 配置

### 1. 智谱 API Key（配图必需）

在 shell 环境变量设置（或写进 `~/.bashrc` / `~/.zshrc`）：

```bash
export ZHIPU_API_KEY="你的智谱APIKey"
```

获取：智谱开放平台 → API Keys → 创建。脚本读取顺序 `ZHIPU_API_KEY` > `BIGMODEL_API_KEY`。

### 2. 阿里云 OSS（可选，启用永久图床）

```bash
cp config/oss.env.example config/oss.env
# 编辑 config/oss.env，填入 OSS 凭证（文件内有注释指引）
```

不配置 OSS 时，配图用智谱 CDN 直出（约 24h 失效，需尽快本地化）；配置后输出永久 URL，兼职复制即用。

## 使用

在 OpenClaw 新会话里对智能体说：

> 写一篇艾利特关于「码垛机器人厂家」的 SEO 文章，配好图

智能体会按 SKILL.md 工作流：写作 → 规划 3-4 张配图 → 构造中文 prompt（图上文字用引号包裹）→ 调智谱 GLM-Image 生成 → 上传 OSS → 输出带永久图链接的 Markdown。

## 文件结构

```
elibot-seo-geo/
├── SKILL.md                  入口（frontmatter + 5 步工作流）
├── references/
│   ├── 写作提示词.md          艾利特 SEO/GEO 写作规范原文（写作核心）
│   ├── 配图指南.md            配图规划 + prompt 模板 + 风格规范
│   └── 智谱图像API.md         智谱 API + OSS 接入参考
├── scripts/
│   ├── generate_image.sh     智谱图像生成（含 OSS 上传 --host oss）
│   └── upload_oss.py         阿里云 OSS V1 签名上传（纯标准库）
├── config/
│   └── oss.env.example       OSS 凭证模板（复制为 oss.env 后填值）
└── README.md                 本文件
```

## 安全

- `config/oss.env` 含 OSS AccessKey，**勿提交 git、勿分享、勿上传 ClawHub**（已默认被 `.gitignore` 排除）
- 务必用 RAM 子账号 + 最小权限（仅该 Bucket 的 `oss:PutObject` / `oss:GetObject`）
- 智谱 Key 建议放环境变量，不硬编码

## 平台无关

本 skill 不依赖任何特定 AI 平台。SKILL.md 用标准 YAML frontmatter（`name` + `description`），脚本用标准 bash + python，可装到任何兼容 SKILL.md 格式的智能体（OpenClaw 等）。
