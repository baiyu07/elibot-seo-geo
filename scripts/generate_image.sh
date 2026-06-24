#!/usr/bin/env bash
# generate_image.sh — 调用智谱 GLM-Image 生成图片
#
# 用法：
#   bash generate_image.sh --prompt "..." --size 1536x864
#   bash generate_image.sh --prompt "..." --size 1024x1024 --download images/fig2.png --host oss
#
# 参数：
#   --prompt   必填，图片描述（见 references/配图指南.md，建议中文 + 引号包裹文字）
#   --size     可选，默认 1024x1024；封面建议 1536x864（长宽须为 32 整数倍，1024-2048 内）
#   --download 可选，下载到指定本地路径
#   --host     可选，图床：none=智谱CDN直出(默认) / oss=上传阿里云OSS输出永久URL
#              默认值可由环境变量 ELIBOT_IMAGE_HOST 控制（设为 oss 即默认走 OSS）
#   --model    可选，默认 glm-image
#
# 智谱 Key 环境变量（按优先级）：
#   ZHIPU_API_KEY > BIGMODEL_API_KEY
#
# OSS 环境变量（--host oss 时必填，见 scripts/upload_oss.py）：
#   OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET / OSS_BUCKET / OSS_ENDPOINT
#   OSS_DOMAIN(可选,自定义域名) / OSS_PREFIX(可选,对象前缀)
#
# 依赖：curl + (jq 或 python/python3 任一，用于 JSON)；--host oss 额外需 python（标准库，无需装包）
# 退出码：0 成功；1 参数/key/依赖错误；2 智谱 API 调用失败；3 prompt 疑似内容审核拒绝；4 OSS 上传失败（已降级输出智谱 URL）

set -euo pipefail

# 加载 skill 内 OSS 配置（若存在；命令行/系统环境变量优先级更高）
_SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -f "$_SKILL_DIR/config/oss.env" ]]; then
  set -a
  source "$_SKILL_DIR/config/oss.env"
  set +a
fi

PROMPT=""
SIZE="1024x1024"
DOWNLOAD=""
MODEL="glm-image"
HOST="${ELIBOT_IMAGE_HOST:-none}"
ENDPOINT="https://open.bigmodel.cn/api/paas/v4/images/generations"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt)   PROMPT="$2"; shift 2 ;;
    --size)     SIZE="$2"; shift 2 ;;
    --download) DOWNLOAD="$2"; shift 2 ;;
    --host)     HOST="$2"; shift 2 ;;
    --model)    MODEL="$2"; shift 2 ;;
    -h|--help)  sed -n '2,26p' "$0"; exit 0 ;;
    *) echo "未知参数: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$PROMPT" ]]; then
  echo "错误：--prompt 必填" >&2
  exit 1
fi

# 读取 API Key（多来源兼容，用循环避免嵌套 ${:-} 出错）
API_KEY=""
for k in ZHIPU_API_KEY BIGMODEL_API_KEY; do
  v="${!k:-}"
  if [[ -n "$v" ]]; then API_KEY="$v"; break; fi
done
if [[ -z "$API_KEY" ]]; then
  echo "错误：未配置智谱 API Key。" >&2
  echo "请设置环境变量之一：ZHIPU_API_KEY / BIGMODEL_API_KEY" >&2
  exit 1
fi

# JSON 工具检测（jq 优先，降级 python3 / python）
JSON_BIN=""
if command -v jq >/dev/null 2>&1; then
  JSON_BIN="jq"
elif command -v python3 >/dev/null 2>&1; then
  JSON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  JSON_BIN="python"
else
  echo "错误：未找到 jq 或 python，无法处理 JSON。请安装其一。" >&2
  exit 1
fi

# 构造请求体（安全转义 prompt 中的特殊字符）
if [[ "$JSON_BIN" == "jq" ]]; then
  PAYLOAD=$(jq -n --arg m "$MODEL" --arg p "$PROMPT" --arg s "$SIZE" \
    '{model:$m, prompt:$p, size:$s}')
else
  PAYLOAD=$("$JSON_BIN" -c \
    "import json,sys; print(json.dumps({'model':sys.argv[1],'prompt':sys.argv[2],'size':sys.argv[3]}))" \
    "$MODEL" "$PROMPT" "$SIZE")
fi

# 从 stdin 的 JSON 提取 data[0].url
extract_url() {
  if [[ "$JSON_BIN" == "jq" ]]; then
    jq -r '.data[0].url // empty'
  else
    "$JSON_BIN" -c "import json,sys; d=json.load(sys.stdin); print(((d.get('data') or [{}])[0]).get('url',''))"
  fi
}

# 带重试的调用（429/5xx 指数退避，最多 3 次）
call_api() {
  local attempt max_wait tmp_file http_code body
  for attempt in 1 2 3; do
    tmp_file=$(mktemp)
    http_code=$(curl -s -o "$tmp_file" -w "%{http_code}" -X POST "$ENDPOINT" \
      -H "Authorization: Bearer $API_KEY" \
      -H "Content-Type: application/json" \
      -d "$PAYLOAD") || http_code="000"
    body=$(cat "$tmp_file" 2>/dev/null || true)
    rm -f "$tmp_file"

    if [[ "$http_code" == "200" ]]; then
      echo "$body"
      return 0
    elif [[ "$http_code" == "429" || "$http_code" =~ ^5[0-9][0-9]$ ]]; then
      max_wait=$((attempt * 5))
      echo "警告：HTTP $http_code，第 $attempt 次重试前等待 ${max_wait}s..." >&2
      sleep "$max_wait"
    elif [[ "$http_code" == "400" || "$http_code" == "403" ]]; then
      # 内容审核拒绝：prompt 含敏感词（焊接火花 / 防爆 / 人形特写等）
      if grep -iqE "content|sensitive|审核|违规|risk|policy|moderation|reject|prohibit" <<< "$body"; then
        echo "提示：该 prompt 疑似被智谱内容审核拒绝（HTTP $http_code）。" >&2
        echo "请改写措辞——去掉焊接火花、危险动作、人形特写、防爆等强敏感词，或弱化场景描述后重试。" >&2
        echo "$body" >&2
        return 3
      fi
      echo "错误：HTTP $http_code" >&2
      echo "$body" >&2
      return 2
    else
      echo "错误：HTTP $http_code" >&2
      echo "$body" >&2
      return 2
    fi
  done
  echo "错误：重试耗尽（429/5xx，已重试 3 次）" >&2
  return 2
}

RESPONSE=$(call_api) || exit $?

# 提取 URL
IMAGE_URL=$(echo "$RESPONSE" | extract_url)
if [[ -z "$IMAGE_URL" || "$IMAGE_URL" == "null" ]]; then
  echo "错误：响应中未找到图片 URL" >&2
  echo "$RESPONSE" >&2
  exit 2
fi

# 下载（可选，本地兜底）
if [[ -n "$DOWNLOAD" ]]; then
  mkdir -p "$(dirname "$DOWNLOAD")"
  if curl -s -o "$DOWNLOAD" "$IMAGE_URL"; then
    echo "已下载: $DOWNLOAD" >&2
  else
    echo "警告：下载失败，仅输出 URL" >&2
  fi
fi

# 图床中转（可选）：--host oss 时，把智谱图上传到阿里云 OSS，输出永久 URL
if [[ "$HOST" == "oss" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  OSS_UPLOADER="$SCRIPT_DIR/upload_oss.py"
  PY_BIN=""
  command -v python3 >/dev/null 2>&1 && PY_BIN="python3"
  [[ -z "$PY_BIN" ]] && command -v python >/dev/null 2>&1 && PY_BIN="python"

  if [[ ! -f "$OSS_UPLOADER" || -z "$PY_BIN" ]]; then
    echo "警告：缺少 upload_oss.py 或 python，跳过 OSS，输出智谱 URL" >&2
  else
    # 复用已下载文件；否则临时下载到带 .png 后缀的文件（OSS 按 content-type 识别）
    UPLOAD_SRC=""; UPLOAD_IS_TMP=0
    if [[ -n "$DOWNLOAD" && -f "$DOWNLOAD" ]]; then
      UPLOAD_SRC="$DOWNLOAD"
    else
      UPLOAD_SRC="${TMPDIR:-/tmp}/elibot-upload-$$.png"; UPLOAD_IS_TMP=1
      curl -sf -o "$UPLOAD_SRC" "$IMAGE_URL" || true
    fi
    if [[ ! -s "$UPLOAD_SRC" ]]; then
      echo "警告：下载智谱图失败，跳过 OSS，输出智谱 URL" >&2
    else
      OBJECT_NAME="elibot-$(date +%Y%m%d-%H%M%S)-$$.png"
      OSS_OUT=$(mktemp)
      if "$PY_BIN" "$OSS_UPLOADER" "$UPLOAD_SRC" "$OBJECT_NAME" >"$OSS_OUT" 2>&1; then
        OSS_URL=$(tail -1 "$OSS_OUT")
        if [[ "$OSS_URL" == http* ]]; then
          echo "已上传 OSS: $OSS_URL" >&2
          IMAGE_URL="$OSS_URL"
        else
          echo "警告：OSS 响应异常，降级智谱 URL：" >&2; cat "$OSS_OUT" >&2
        fi
      else
        echo "警告：OSS 上传失败，降级智谱 URL（约24h失效）。错误：" >&2; cat "$OSS_OUT" >&2
      fi
      rm -f "$OSS_OUT"
    fi
    [[ "$UPLOAD_IS_TMP" == "1" ]] && rm -f "$UPLOAD_SRC"
  fi
fi

# 标准输出 URL（最后一行，便于 $(...) 或管道提取）
echo "$IMAGE_URL"
