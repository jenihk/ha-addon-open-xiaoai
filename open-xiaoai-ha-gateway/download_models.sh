#!/usr/bin/env bash
# 模型缺失时自动下载：
#   - VAD + KWS：open-xiaoai-bridge release（GitHub，自动尝试国内代理加速）
#   - Paraformer：hf-mirror（国内可达，可用 HF_ENDPOINT 覆盖）
# 用法: download_models.sh <models_dir>
set -e

MODELS_DIR="$1"
mkdir -p "${MODELS_DIR}"

REQUIRED_KWS=(silero_vad.onnx encoder.onnx decoder.onnx joiner.onnx tokens.txt bpe.model)

missing_kws=0
for f in "${REQUIRED_KWS[@]}"; do
  [ -f "${MODELS_DIR}/${f}" ] || missing_kws=1
done

para_ok=0
if [ -f "${MODELS_DIR}/sherpa-onnx-paraformer-zh-2024-03-09/model.int8.onnx" ] \
  && [ -f "${MODELS_DIR}/sherpa-onnx-paraformer-zh-2024-03-09/tokens.txt" ]; then
  para_ok=1
fi

if [ "${missing_kws}" -eq 0 ] && [ "${para_ok}" -eq 1 ]; then
  echo "[Add-on] 模型已齐全，跳过下载"
  exit 0
fi

echo "[Add-on] 检测到模型缺失，开始自动下载（约 340MB，请耐心等待）..."

KWS_URL="https://github.com/coderzc/open-xiaoai-bridge/releases/download/vad-kws-asr-models/models.zip"
# GitHub 加速代理列表（按顺序尝试）。GITHUB_PROXY 非空时仅使用它指定的前缀。
GH_PROXIES=(
  "https://ghfast.top/"
  "https://gh-proxy.com/"
  "https://mirror.ghproxy.com/"
)

HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
PARA_BASE="${HF_ENDPOINT%/}/csukuangfj/sherpa-onnx-paraformer-zh-2024-03-09/resolve/main"

# 优先 curl（断点续传 + 自动重试），没有 curl 时退回 python urllib
dl() {
  local url="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  echo "[Add-on] downloading: $url"
  if command -v curl >/dev/null 2>&1; then
    curl -fL -C - --retry 5 --retry-all-errors --connect-timeout 20 \
      -A "open-xiaoai-addon" -o "$dest" "$url"
  else
    python3 - "$url" "$dest" <<'PY'
import sys
import urllib.request

url, dest = sys.argv[1], sys.argv[2]
req = urllib.request.Request(url, headers={"User-Agent": "open-xiaoai-addon"})
with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
    while True:
        chunk = r.read(1 << 20)
        if not chunk:
            break
        f.write(chunk)
PY
  fi
}

# 依次尝试多个 URL，全部失败则返回非 0
dl_with_fallback() {
  local label="$1"
  shift
  local dest="$1"
  shift
  local url
  for url in "$@"; do
    if dl "$url" "$dest"; then
      return 0
    fi
    echo "[Add-on] ${label} 下载失败，尝试下一个镜像: ${url}"
    rm -f "$dest"
  done
  echo "[Add-on] ${label} 所有镜像均下载失败"
  return 1
}

if [ "${missing_kws}" -eq 1 ]; then
  echo "[Add-on] 下载 VAD + KWS 模型..."
  zip_path="${MODELS_DIR}/models.zip"
  if [ -n "${GITHUB_PROXY}" ]; then
    urls=("${GITHUB_PROXY}${KWS_URL}")
  else
    urls=("${KWS_URL}")
    for p in "${GH_PROXIES[@]}"; do
      urls+=("${p}${KWS_URL}")
    done
  fi
  if ! dl_with_fallback "VAD+KWS" "${zip_path}" "${urls[@]}"; then
    echo "[Add-on] 请手动把模型文件放入: ${MODELS_DIR}"
    echo "[Add-on] 或在配置中填写 GitHub 代理前缀（github_proxy），例如 https://ghfast.top/"
    exit 1
  fi
  # 校验 zip 完整性，损坏则删除并失败（下次启动重试）
  if ! python3 - "${zip_path}" <<'PY'
import sys
import zipfile

path = sys.argv[1]
with zipfile.ZipFile(path) as z:
    bad = z.testzip()
if bad:
    raise SystemExit(f"bad file in zip: {bad}")
PY
  then
    rm -f "${zip_path}"
    echo "[Add-on] models.zip 校验失败"
    exit 1
  fi
  python3 - "${MODELS_DIR}" "${zip_path}" <<'PY'
import os
import sys
import zipfile

models_dir, zip_path = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(zip_path) as z:
    z.extractall(models_dir)
os.remove(zip_path)
nested = os.path.join(models_dir, "models")
if os.path.isdir(nested):
    for name in os.listdir(nested):
        os.replace(os.path.join(nested, name), os.path.join(models_dir, name))
    os.rmdir(nested)
PY
fi

if [ "${para_ok}" -ne 1 ]; then
  echo "[Add-on] 下载 Paraformer ASR 模型（约 217MB）..."
  out="${MODELS_DIR}/sherpa-onnx-paraformer-zh-2024-03-09"
  dl "${PARA_BASE}/model.int8.onnx" "${out}/model.int8.onnx"
  dl "${PARA_BASE}/tokens.txt" "${out}/tokens.txt"
fi

echo "[Add-on] 模型下载完成"
