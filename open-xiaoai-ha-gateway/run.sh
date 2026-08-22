#!/usr/bin/env bash
set -e

CONFIG_DIR="/config/open-xiaoai-ha-gateway"
MODELS_DIR="${CONFIG_DIR}/models"
APP_DIR="/app/open-xiaoai-server"

mkdir -p "${CONFIG_DIR}" "${MODELS_DIR}"

# 模型自动下载（UI 选项 auto_download_models，默认开启）
AUTO_DL="$(python3 -c "import json;print(json.load(open('/data/options.json')).get('auto_download_models', True))" 2>/dev/null || echo true)"
GITHUB_PROXY="$(python3 -c "import json;print(json.load(open('/data/options.json')).get('github_proxy',''))" 2>/dev/null || echo '')"
HF_ENDPOINT="$(python3 -c "import json;print(json.load(open('/data/options.json')).get('hf_endpoint','https://hf-mirror.com'))" 2>/dev/null || echo 'https://hf-mirror.com')"
export GITHUB_PROXY HF_ENDPOINT
if [ "${AUTO_DL,,}" = "true" ]; then
  /download_models.sh "${MODELS_DIR}" || exit 1
fi

# UI 配置模式：每次启动由 generate_config.py 从 UI 选项生成 config.py
USE_UI_CONFIG="$(python3 -c "import json;print(json.load(open('/data/options.json')).get('use_ui_config', True))" 2>/dev/null || echo true)"
export USE_UI_CONFIG="${USE_UI_CONFIG,,}"
export CONFIG_PATH="${CONFIG_DIR}/config.py"

if [ "${USE_UI_CONFIG}" = "true" ]; then
  python3 /generate_config.py
else
  # 手动模式：首次启动复制默认配置，之后由用户自行编辑
  if [ ! -f "${CONFIG_DIR}/config.py" ]; then
    cp "${APP_DIR}/config.py" "${CONFIG_DIR}/config.py"
    echo "[Add-on] 已生成默认配置: ${CONFIG_DIR}/config.py（请自行编辑）"
  fi
fi

# 模型目录：用户需自行放入 VAD/KWS/Paraformer 模型文件
if [ ! -e "${APP_DIR}/core/models" ]; then
  ln -s "${MODELS_DIR}" "${APP_DIR}/core/models"
fi

# 读取 add-on UI 选项（/data/options.json）
API_SERVER_ENABLE="$(python3 -c "import json;print(json.load(open('/data/options.json')).get('api_server_enable', False))" 2>/dev/null || echo false)"
export API_SERVER_ENABLE="${API_SERVER_ENABLE,,}"

cd "${APP_DIR}"

# 生成唤醒词（模型缺失时忽略，仅提示）
python core/services/audio/kws/keywords.py || echo "[Add-on] 唤醒词生成失败，请检查模型目录: ${MODELS_DIR}"

exec python main.py
