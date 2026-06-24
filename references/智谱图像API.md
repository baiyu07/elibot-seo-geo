# 智谱 GLM-Image API 参考

本文档说明如何调用智谱开放平台的 GLM-Image 模型生成图片，供艾利特文章配图使用。封装脚本见 `scripts/generate_image.sh`。

---

## 一、API 概览

| 项 | 值 |
|---|---|
| 端点 | `https://open.bigmodel.cn/api/paas/v4/images/generations` |
| 方法 | `POST` |
| 模型 | `glm-image` |
| 鉴权 | `Authorization: Bearer <API_KEY>` |
| 架构特点 | 自回归 + 扩散解码器混合架构，擅长科普插画、商业海报、文字密集场景 |

---

## 二、请求体

```json
{
  "model": "glm-image",
  "prompt": "图片的英文描述 prompt",
  "size": "1536x864"
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `model` | 是 | 固定 `glm-image` |
| `prompt` | 是 | 图片描述，建议英文（见配图指南） |
| `size` | 否 | 默认 `1024x1024`；封面用 `1536x864`，正文用 `1024x1024` |
| `response_format` | 否 | `url`（默认，返回链接）或 `b64_json`（返回 base64） |

---

## 三、size 规范

智谱 GLM-Image 支持自定义尺寸，约束（按官方文档分层）：

- **硬约束**：长宽均为 **32 的整数倍**
- **硬范围**：单边 **512–2048 px**
- **总像素** ≤ **2²²（约 419 万）**
- 推荐单边落在 **1024–2048**（软建议，非硬下限；512–1024 的短边也合法，如 `1536x864` 的 864）
- 支持任意比例（正方形 / 横版 / 竖版）

艾利特配图标准尺寸：

| 用途 | size | 说明 |
|---|---|---|
| 封面图 | `1536x864` | 16:9 横版，适合文章头图 |
| 正文配图 | `1024x1024` | 1:1 正方形，默认最稳 |
| 竖版封面（移动端，可选） | `864x1536` | 适合移动端头图 |

> 非法 size 会返回 400。脚本不会校验 size，调用者须自行保证长宽为 32 的整数倍、落在 1024–2048 内。

---

## 四、返回格式

默认返回 URL：

```json
{
  "created": 1719000000,
  "data": [
    {
      "url": "https://cdm.bigmodel.cn/xxxxx/xxxxx.png"
    }
  ],
  "model": "glm-image"
}
```

提取 URL：`jq -r '.data[0].url'`

> 智谱返回的 CDN URL 有时效（社区反馈约 24 小时）。当前 skill 版本采用 URL 直出策略，文末「配图说明」会标注时效；后续接入图床中转后输出永久 URL。

---

## 五、API Key 配置

脚本按优先级读取环境变量：

1. `ZHIPU_API_KEY`
2. `BIGMODEL_API_KEY`

### 配置方法（Windows / Git Bash）

在 `~/.bashrc` 或系统环境变量中设置：

```bash
export ZHIPU_API_KEY="你的智谱APIKey"
```

获取 Key：登录 [智谱开放平台](https://open.bigmodel.cn/) → API Keys → 创建。

> 说明：智谱 API Key 格式通常为 `xxxxxxxx.yyyyyyyy`（id.secret）。在 `~/.bashrc` 设置 `export ZHIPU_API_KEY="你的key"` 即可。

---

## 六、curl 调用模板

### 1. 生成单张图（返回 URL）

```bash
API_KEY="${ZHIPU_API_KEY:-${BIGMODEL_API_KEY}}"

RESPONSE=$(curl -s -X POST "https://open.bigmodel.cn/api/paas/v4/images/generations" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-image",
    "prompt": "a collaborative robot arm working on an assembly line, industrial sci-fi illustration, blue-grey and steel color palette, cinematic lighting, clean modern factory environment, high detail, no text, no watermark, no letters, no logo",
    "size": "1536x864"
  }')

# 提取 URL（需 jq；若无 jq 可用 python3）
echo "$RESPONSE" | jq -r '.data[0].url'
# python3 替代写法：
# echo "$RESPONSE" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['data'][0]['url'])"
```

### 2. 生成并下载到本地（可选兜底）

```bash
URL=$(echo "$RESPONSE" | jq -r '.data[0].url')
curl -s -o "cover.png" "$URL"
```

---

## 七、使用封装脚本

推荐用 `generate_image.sh`（已内置 key 读取、JSON 工具自动检测 jq/python、HTTP 状态检查、429/5xx 自动重试、内容审核拒绝识别）。**调用必须用绝对路径**（skill 目录即 `SKILL.md` 所在目录）：

```bash
SKILL_DIR="$HOME/.openclaw/skills/elibot-seo-geo"   # 按实际安装路径改

# 生成封面（标准输出最后一行即 URL）
bash "$SKILL_DIR/scripts/generate_image.sh" \
  --prompt "a palletizing robot stacking boxes..." \
  --size 1536x864

# 推荐加 --download 同步下载到文章同级 images/，规避智谱 CDN 约 24h 失效
bash "$SKILL_DIR/scripts/generate_image.sh" \
  --prompt "..." \
  --size 1024x1024 \
  --download images/02-palletizing.png
```

退出码：`0` 成功；`1` 参数/key/依赖错误；`2` API 调用失败；`3` prompt 疑似内容审核拒绝（改写措辞后重试）。脚本头部 `--help` 有完整用法。

---

## 八、错误处理

| HTTP / 错误码 | 含义 | 处理 |
|---|---|---|
| 401 | 鉴权失败 | 检查 API Key 环境变量是否设置、是否过期 |
| 429 | 限流 | 脚本自动等待重试（最多 3 次，指数退避） |
| 400 (size) | 尺寸不合法 | 确认长宽为 32 整数倍、单边 512–2048、总像素 ≤ 2²² |
| 400/403 (审核) | prompt 触发内容审核 | 脚本退出码 3 并提示；改写措辞，去掉焊接火花 / 防爆 / 人形特写 / 暴力 / 武器等强敏感词，或弱化场景后重试 |
| 5xx | 服务端错误 | 脚本自动指数退避重试 |

脚本行为：
- key 缺失 → 立即退出码 1，提示配置环境变量
- 429 / 5xx → 自动重试 3 次，每次等待 `attempt × 5` 秒
- 400/403 且响应含审核关键词 → 退出码 3，提示改写 prompt（去掉敏感词）
- 其他 HTTP 错误 → 退出码 2，打印响应体
- 响应体无 `data[0].url` → 退出码 2，打印响应体

---

## 九、额度与耗时

- 单张图生成耗时约 10–30 秒
- 一篇文章 3-4 张图，串行约 1–2 分钟
- 智谱按量计费，glm-image 单张成本较低；注意账户余额

---

## 十、图床中转：阿里云 OSS（已实现，输出永久链接）

智谱 CDN 链接约 24h 失效。接入阿里云 OSS 后，`generate_image.sh --host oss` 会自动把智谱生成的图上传到你的 OSS，输出**永久 URL**，兼职复制 MD 即可，图片永不过期、彻底零操作。

### 1. 工作流

智谱生成图 → 下载 → `upload_oss.py`（OSS V1 签名 + PUT 上传）→ 输出 OSS 永久 URL（上传失败自动降级智谱 URL）。

### 2. 需要的环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `OSS_ACCESS_KEY_ID` | 是 | RAM AccessKey ID |
| `OSS_ACCESS_KEY_SECRET` | 是 | RAM AccessKey Secret |
| `OSS_BUCKET` | 是 | Bucket 名 |
| `OSS_ENDPOINT` | 是 | 地域域名，如 `oss-cn-hangzhou.aliyuncs.com` |
| `OSS_DOMAIN` | 否 | 绑定的自定义域名 / CDN（含 https://）；不填用 Bucket 默认域名 |
| `OSS_PREFIX` | 否 | 对象前缀，如 `elibot/articles` |
| `ELIBOT_IMAGE_HOST` | 否 | 设为 `oss` 则 `generate_image.sh` 默认走 OSS |

### 3. 获取步骤（阿里云控制台）

1. **创建 Bucket**：OSS 控制台 → Bucket 列表 → 创建 → 选地域（如华东 1 杭州）→ 读写权限选「**公共读**」（图片要能公开访问）→ 记下 Bucket 名和 Endpoint（外网访问域名）。
2. **创建 RAM 子账号 + AccessKey**（强烈建议，**勿用主账号 AK**）：RAM 访问控制 → 用户 → 创建用户 → 勾选「OpenAPI 调用访问」→ 生成 AccessKey → 新建自定义授权策略，仅授予该 Bucket 的 `oss:PutObject` + `oss:GetObject` 权限，授权给该子账号。
3. **（可选）绑定自定义域名**：Bucket → 传输管理 → 域名管理 → 绑定自有域名或开通 CDN（加速 + 隐藏 bucket 名）。

### 4. 配置环境变量

在 `~/.bashrc`（Windows Git Bash）追加：

```bash
export OSS_ACCESS_KEY_ID="你的AccessKeyId"
export OSS_ACCESS_KEY_SECRET="你的AccessKeySecret"
export OSS_BUCKET="你的bucket名"
export OSS_ENDPOINT="oss-cn-hangzhou.aliyuncs.com"
export OSS_DOMAIN="https://img.yourdomain.com"  # 可选，没绑域名删掉这行
export OSS_PREFIX="elibot/articles"             # 可选
export ELIBOT_IMAGE_HOST="oss"                   # 可选，设了默认走 OSS
```

保存后 `source ~/.bashrc` 或新开终端生效。

### 5. 使用

```bash
# 方式A：单次指定 --host oss
bash "$SKILL_DIR/scripts/generate_image.sh" --prompt "..." --size 1536x864 --host oss --download images/01-cover.png

# 方式B：设了 ELIBOT_IMAGE_HOST=oss 后，默认就走 OSS（不用每次写 --host oss）
bash "$SKILL_DIR/scripts/generate_image.sh" --prompt "..." --size 1536x864 --download images/01-cover.png
```

输出最后一行是 OSS 永久 URL。

### 6. 安全要点（重要）

- **务必用 RAM 子账号 + 最小权限**（仅该 Bucket 的 PutObject/GetObject）。主账号 AK 泄露 = 全云资源风险。
- AccessKey 写在 `~/.bashrc`，**绝不**写进 skill 文件、**绝不**提交 git。
- Bucket 读写权限「公共读」即可（图片本就要公开访问），不要开「公共读写」、不要开 Bucket 列表列举权限。
- 定期在 RAM 控制台轮换 AccessKey（删旧建新）。

### 7. 实现说明

`upload_oss.py` 用纯 Python 标准库（`hmac`/`hashlib`/`base64`/`urllib`）实现 OSS V1 签名 + PUT 上传，**无需 `pip install oss2`**，兼容 python 3.14。签名实现经 hmac-sha1 标准向量（RFC/Wiki）验证正确，与阿里云官方 V1 签名 Python 示例一致。常见错误有针对性提示：`SignatureDoesNotMatch`（secret 错）、403 `AccessDenied`（RAM 权限不足）、`NoSuchBucket`（bucket/endpoint 不匹配）。
