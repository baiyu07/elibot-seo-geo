---
name: elibot-seo-geo
description: 艾利特机器人官网 SEO/GEO 文章写作 + 智谱 GLM-Image 自动配图。输入文章主题或关键词，先按艾利特机器人行业 SEO/GEO 规范产出完整中文文章（长尾词、SEO 信息、正文、FAQ、总结、内链），再调用智谱 GLM-Image 生成 1 张封面图 + 2-3 张正文配图（共 3-4 张，B2B 科技信息海报风格，图带中文标题/标注），图片上传阿里云 OSS 输出永久链接嵌入 Markdown，复制即可发布。触发场景：写艾利特机器人 SEO 文章、艾利特官网博客/知识库内容、给艾利特文章配封面图和插图、协作机器人/码垛机器人/焊接工作站/人形机器人主题的内容创作与配图。
---

# 艾利特机器人 SEO/GEO 文章写作 + 智谱配图

本 skill 把「艾利特 SEO/GEO 文章写作提示词」与「智谱 GLM-Image 自动配图」打包为一个完整的内容生产流程：一篇文章从主题到带图成品，一次产出。

**输出富文本 HTML（可直接发布官网）**：官网 CMS 富文本编辑器只吃 HTML，直接粘 Markdown 会显示成纯文本。因此文章写完并配图后，用 `scripts/md2html.py` 把 Markdown 正文转成语义化 HTML（`<h2>/<h3>/<p>/<figure>/<table>` 等，结构与线上文章一致），兼职/OpenClaw 把 HTML 直接粘进 CMS 正文框即可，无需手动转换。

**图片永久链接**：配图走阿里云 OSS（`--host oss`），输出永久 URL，兼职零操作；OSS_DOMAIN 必须留空以用 bucket 默认域名（自带 HTTPS）。

## 能力边界

- **写作部分**：完全遵循 `references/写作提示词.md`（艾利特官方写作规范，1720 行），不改动、不重写。覆盖 SEO/GEO、产品匹配、品牌口径、数据合规、内链白名单等全部约束。
- **配图部分（新增）**：调用智谱 GLM-Image，按 **B2B 科技信息海报风格**（3D 写实场景 + 信息卡片中文文字排版）生成 3-4 张**带文字**的图（1 封面 + 2-3 正文），嵌入文章。封面含大标题/副标题/卖点图标，正文含小标题/关键标注——充分利用 GLM-Image「读懂指令、写对文字」的核心能力。

## 何时触发

- 用户给艾利特文章主题/关键词，要写 SEO/GEO 文章
- 用户要给艾利特文章配封面图、正文插图
- 用户说「写一篇关于协作机器人/码垛机器人/焊接工作站/人形机器人的艾利特文章」
- 用户要在艾利特官网博客/知识库发带图内容

## 前置条件：智谱 API Key

配图需要智谱开放平台 API Key。脚本按以下优先级自动读取环境变量：

1. `ZHIPU_API_KEY`
2. `BIGMODEL_API_KEY`

获取：登录智谱开放平台 → API Keys → 创建，然后 `export ZHIPU_API_KEY="你的key"`（或写进 `~/.bashrc`）。若缺失，配图步骤会跳过并提示配置；**文章写作不受影响**，会照常产出。

## 工作流（5 步）

### 第 1 步：写作

读取 `references/写作提示词.md`，严格按其规范创作文章，包括：长尾关键词拓展（10-15 个）、SEO 信息（Title / Keywords / Description / 文章URL）、文章内容（引言 + H2/H3 正文）、FAQ（4-8 个）、总结、内链建议（仅用白名单绝对路径）。

**写作部分一字不改地遵循原文提示词**，所有产品匹配、品牌口径、数据合规、禁用表达、内链白名单等约束全部生效。

### 第 2 步：配图规划

文章写完后，规划 3-4 张图：

- **1 张封面图**：横版 `1536x864`（16:9），高度概括文章主题，强视觉冲击
- **2-3 张正文配图**：`1024x1024` 正方形，配合核心 H2 段落

配图位置：封面图放 SEO 信息块之后、引言段之前；正文配图嵌在核心 H2 段落（产品选型、工艺解析、行业应用、技术原理）正文之后；最后一张放总结段之前。详见 `references/配图指南.md`。

### 第 3 步：构造配图 prompt

按 `references/配图指南.md` 为每张图构造**中文 prompt**（GLM-Image 中文理解强、文字渲染准，经实测标题/标注均无误）：

- 风格：**B2B 科技信息海报**（3D 写实场景 + 左侧信息卡片文字排版）
- 封面文字：大标题（文章标题精简版）+ 副标题（3-4 关键词用 · 分隔）+ 3 个卖点图标文字
- 正文文字：左上角小标题（对应 H2）+ 关键部位标注
- **关键技巧**：所有要出现在图上的文字，prompt 里用**中文双引号 `""` 包裹**（GLM-Image 对引号内文字精准渲染，词准确率 0.91）
- 配色：科技蓝 + 工业灰 + 棕色 + 白

### 第 4 步：调用智谱 GLM-Image 生成

**脚本路径约定（重要）**：调用脚本必须用**绝对路径**——skill 目录即 `SKILL.md` 所在目录（OpenClaw 下通常是 `~/.openclaw/skills/elibot-seo-geo`）。智能体执行命令时的 cwd 是用户工作目录，不是 skill 目录，所以**不要写** `bash scripts/generate_image.sh` 这种相对路径，会找不到脚本。先确认 skill 目录的绝对路径再调用。

```bash
SKILL_DIR="$HOME/.openclaw/skills/elibot-seo-geo"   # 按实际安装路径改

# 生成封面（标准输出最后一行即图片 URL）
bash "$SKILL_DIR/scripts/generate_image.sh" --prompt "..." --size 1536x864

# 推荐加 --download 同步下载到文章同级 images/，规避智谱 CDN 约 24h 失效
bash "$SKILL_DIR/scripts/generate_image.sh" --prompt "..." --size 1024x1024 \
  --download "images/02-palletizing.png"
```

每张图调用一次，拿到智谱 CDN URL。封面 1 次 + 正文 2-3 次 = 共 3-4 次调用。**强烈建议每次都带 `--download`** 把图片落到文章同级 `images/`，从源头规避链接失效对兼职的影响。

**图床中转（推荐，永久链接）**：若已配置阿里云 OSS（见 `references/智谱图像API.md` 第十节），加 `--host oss` 会自动把图上传到 OSS 输出**永久 URL**，兼职复制 MD 即可、图片永不过期：

```bash
bash "$SKILL_DIR/scripts/generate_image.sh" --prompt "..." --size 1536x864 --host oss --download "images/01-cover.png"
```

或在 `~/.bashrc` 设 `export ELIBOT_IMAGE_HOST=oss`，之后默认走 OSS。未配置 OSS 时默认 `none`（智谱直出）。OSS 上传失败会自动降级智谱 URL。

退出码：`0` 成功；`1` 参数/key/依赖错误；`2` 智谱 API 调用失败；`3` prompt 疑似内容审核拒绝；`4` OSS 上传失败（已降级输出智谱 URL）。

### 第 5 步：嵌入文章

把图片以 Markdown 语法嵌入：

```markdown
![协作机器人在食品饮料产线进行纸箱码垛作业](智谱URL)
*图1：协作机器人在食品饮料产线的码垛应用示意*
```

- `alt` 文案包含核心关键词 + 图片内容描述（SEO 友好，落地写作提示词第五节"图片建议写明 alt"）
- 图注用斜体，编号连续，辅助阅读与 GEO 引用

文末附「配图说明」HTML 注释块，标注图片链接类型（OSS 永久 / 智谱 CDN 24h）与兼职发布步骤。

### 第 6 步：转换富文本 HTML（官网发布）

**官网 CMS 富文本编辑器只吃 HTML，不吃 Markdown。** 把完整 Markdown 成稿（含封面图、正文、正文配图、FAQ、总结）写到一个 `.md` 文件后，用 `md2html.py` 转成可直接粘贴发布的富文本 HTML：

```bash
SKILL_DIR="$HOME/.openclaw/skills/elibot-seo-geo"   # 按实际安装路径改

# 方式A：读 .md 文件，输出 .html 文件
python "$SKILL_DIR/scripts/md2html.py" article.md -o article.html

# 方式B：读 .md 文件，打印 HTML 到 stdout（便于直接拷给 CMS）
python "$SKILL_DIR/scripts/md2html.py" article.md

# 方式C：管道，从 stdin 读
cat article.md | python "$SKILL_DIR/scripts/md2html.py" -
```

`md2html.py` 自动只提取**正文 + 配图**部分（从「## 文章内容」/首张图开始，到「## 内链建议」或「配图说明」注释之前），并排除 SEO 信息块、长尾词清单、内链建议清单、HTML 注释——这些不进正文 HTML（SEO Title/Keywords/Description/文章URL 填 CMS 对应字段；长尾词与内链建议由编辑单独处理）。

转换映射（结构与线上文章 `cms.jiasou.cn/news/*.html` 一致）：

| Markdown | 富文本 HTML |
|---|---|
| `## 标题` | `<h2>标题</h2>` |
| `### 标题` | `<h3>标题</h3>` |
| 普通段落 | `<p>...</p>` |
| `![alt](url)` + 下行 `*图注*` | `<figure><img alt src><figcaption>图注</figcaption></figure>` |
| `**加粗**` | `<strong>加粗</strong>` |
| `[锚文本](https://...)` | `<a href="...">锚文本</a>` |
| Markdown 表格 | `<table><thead>...<tbody>...</table>` |
| `1.` / `-` 列表 | `<ol>`/`<ul>` |

纯标准库实现，兼容 python 3.x，无需装包。转换后把 `article.html` 的内容粘进官网 CMS 正文富文本框即可直接发布。

## 输出格式

最终产出**两个文件**：

1. **`文章名.md`（Markdown 草稿，含全部信息）** —— 写作与配图的完整产物，结构：

```markdown
长尾关键词拓展：
1. ...
---
SEO Title：...
SEO Keywords：...
SEO Description：...
文章URL：...   （填 CMS 的 URL slug 字段）
---
![封面图alt](OSS永久URL)
*封面：...*

## 文章内容
【引言段落】
...正文（含 2-3 张正文配图，嵌在关键 H2 后）...
## FAQ
...
## 总结
...
## 内链建议
...
<!-- 配图说明（发布前请删除）... -->
```

2. **`文章名.html`（富文本正文，直接发布官网）** —— 由 `md2html.py` 从上面的 `.md` 转换得到，只含正文 + 配图（SEO 信息块、长尾词、内链建议、HTML 注释均已自动剔除）。把这份 HTML 的内容粘进官网 CMS 正文富文本框即可发布。

> 写作部分严格遵循 `references/写作提示词.md` 第十四节「最终输出格式」（产出 Markdown），本 skill 不改动该规范；富文本 HTML 是发布前的转换产物，由第 6 步生成。

## 文件指引

| 文件 | 作用 |
|---|---|
| `references/写作提示词.md` | 艾利特 SEO/GEO 写作规范原文（写作核心，不改） |
| `references/配图指南.md` | 配图规划、prompt 构造、风格规范、SEO 图注、配图说明区块 |
| `references/智谱图像API.md` | API 端点、size 规范、key 配置、curl 模板、错误处理 |
| `scripts/generate_image.sh` | 智谱图像生成脚本（含重试、审核识别、`--host oss` 图床中转） |
| `scripts/upload_oss.py` | 阿里云 OSS V1 签名上传（纯标准库，永久链接，见智谱图像API.md 第十节） |
| `scripts/md2html.py` | Markdown → 官网富文本 HTML 转换（第 6 步，CMS 直接粘贴发布） |

## 重要约束

1. **写作部分严格不变**：所有写作决策走 `references/写作提示词.md`。配图是文章完成后的独立增强环节，不回改写作逻辑、不修改写作提示词原文。
2. **配图数量 3-4 张**：封面 1 + 正文 2-3，不堆砌，避免影响 Core Web Vitals。
3. **B2B 科技信息海报风格**：全篇视觉统一，3D 写实场景 + 信息卡片文字排版，科技蓝 + 工业灰 + 棕色 + 白。
4. **图片带正确中文文字**：充分利用 GLM-Image「写对文字」能力——封面带标题/副标题/卖点，正文带小标题/标注；prompt 里文字用中文引号 `""` 包裹。右下角「AI生成」为智谱平台强制水印（国内 AI 内容合规标注），发布时可保留或裁剪。
5. **图片链接用 bucket 默认域名**：配图走阿里云 OSS（`--host oss`）输出永久链接。**`OSS_DOMAIN` 必须留空**，这样脚本用 bucket 默认域名（`ittx-ces.oss-cn-hongkong.aliyuncs.com`，自带 HTTPS）；若填自定义域名（如 `oss-cms.jiasou.cn`）且没配 SSL 证书，HTTPS 会裂图。详见智谱图像API.md 第十节。
6. **配图不替代产品实拍**：生成的插画是场景示意，涉及艾利特具体型号参数时，文字说明仍以官网为准（写作提示词的来源红线同样适用于配图说明）。
7. **产品匹配仍由写作提示词决定**：配图主体（协作/码垛/焊接/人形等）跟随写作提示词第四节「产品匹配逻辑」的结论，不另起炉灶。
8. **富文本 HTML 发布**：官网 CMS 富文本编辑器只吃 HTML，不吃 Markdown。写作产出 Markdown 草稿后，必须经第 6 步 `md2html.py` 转换为富文本 HTML 再发布；直接粘 Markdown 会显示成纯文本（标题、表格、图片全部失效）。
