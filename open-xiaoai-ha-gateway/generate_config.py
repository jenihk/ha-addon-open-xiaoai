#!/usr/bin/env python3
"""根据 add-on UI 选项（/data/options.json）生成 config.py。"""

import json
import os

OPTIONS_PATH = "/data/options.json"
OUTPUT_PATH = os.environ.get(
    "CONFIG_PATH", "/config/open-xiaoai-ha-gateway/config.py"
)

TEMPLATE = '''# -*- coding: utf-8 -*-
# 本文件由 add-on 的 UI 配置自动生成，请勿手动编辑。
# 修改方式：加载项 → 配置 → 修改选项 → 重启；或关闭 use_ui_config 后手动编辑。
AGENT_ROUTES = @AGENT_ROUTES@


async def before_wakeup(speaker, text, source, app):
    """
    处理收到的用户消息，并决定是否唤醒 Home Assistant Assist。
    """
    if source == "kws":
        from core.ha import HAManager

        # 按唤醒词路由到对应的 HA conversation agent
        for keyword, agent_id in AGENT_ROUTES.items():
            if keyword in text:
                app.set_ha_agent_id(agent_id)
                # 唤醒应答跟随该 agent 的 TTS 音色（session_tts_speakers）
                await HAManager.play_response_with_tts(f"{keyword}来了")
                return "ha"

        # 未匹配到路由表的唤醒词：仍进入 HA 连续对话（默认 agent）
        await HAManager.play_response_with_tts("来了")
        return "ha"

    if source == "xiaoai":
        if text == "召唤小爱":
            await speaker.abort_xiaoai()
            return "ha"

        if "让小爱" in text:
            await speaker.abort_xiaoai()
            await app.send_to_ha_and_play_reply(text.replace("让小爱", ""))
            return None

    return None


async def after_wakeup(speaker, source=None, session_key=None):
    """退出唤醒状态时的提示语。"""
    if source == "ha":
        from core.ha import HAManager

        await HAManager.play_response_with_tts("再见")


APP_CONFIG = {
    "wakeup": {
        "keywords": @KEYWORDS@,
        "timeout": 12,
        "before_wakeup": before_wakeup,
        "after_wakeup": after_wakeup,
        "extra_stop_command": "",
    },
    "kws": {
        "keywords_score": 0.8,
        "keywords_threshold": 0.08,
        "vad_threshold": 0.02,
        "min_silence_duration": 480,
    },
    "vad": {
        "threshold": 0.20,
        "min_speech_duration": 250,
        "min_silence_duration": 500,
    },
    "audio_input": {
        "gain": 5.0,
        "conversation_gain": 1.5,
    },
    "asr": {
        "model": "paraformer",
        "int8": True,
        "num_threads": 4,
        "replacements": {},
    },
    "xiaoai": {
        "continuous_conversation_mode": True,
        "exit_command_keywords": ["停止", "退下", "退出", "下去吧", "没叫你"],
        "max_listening_retries": 2,
        "exit_prompt": "再见，主人",
        "continuous_conversation_keywords": [
            "开启连续对话",
            "启动连续对话",
            "我想跟你聊天",
        ],
    },
    "ha": {
        "base_url": "@HA_BASE_URL@",
        "token": "@HA_TOKEN@",
        "agent_id": "@DEFAULT_AGENT_ID@",
        "conversation_id": "",
        "language": "",
        "input_mode": "local_asr",
        "exit_keywords": [
            "退出",
            "停止",
            "再见",
            "没事了",
            "不打扰了",
            "退下吧",
            "先这样吧",
            "拜拜",
            "没叫你",
        ],
        "response_timeout": 60,
        "listen_settle_seconds": 0.3,
        "tts_speaker": "@DEFAULT_TTS_SPEAKER@",
        "session_tts_speakers": @SESSION_VOICES@,
        "rule_prompt": "注意：将结果处理成纯文字版，不要返回任何 markdown 格式，也不要包含任何代码块，并将字数控制在 200 字以内",
    },
    "tts": {
        "doubao": {
            "api_key": "@DOUBAO_API_KEY@",
        "default_speaker": "@DOUBAO_DEFAULT_SPEAKER@",
            "audio_format": "pcm",
            "stream": True,
        }
    },
}
'''

DEFAULTS = {
    "kws": {
        "keywords_score": 0.8,
        "keywords_threshold": 0.08,
        "vad_threshold": 0.02,
        "min_silence_duration": 480,
    },
    "vad": {
        "threshold": 0.20,
        "min_speech_duration": 250,
        "min_silence_duration": 500,
    },
    "audio_input": {
        "gain": 5.0,
        "conversation_gain": 1.5,
    },
}

# UI 数字字段 -> (顶层键, 子键, 类型)
NUMERIC_FIELDS = {
    "kws_keywords_score": ("kws", "keywords_score", float),
    "kws_keywords_threshold": ("kws", "keywords_threshold", float),
    "kws_vad_threshold": ("kws", "vad_threshold", float),
    "kws_min_silence_duration": ("kws", "min_silence_duration", int),
    "vad_threshold": ("vad", "threshold", float),
    "vad_min_speech_duration": ("vad", "min_speech_duration", int),
    "vad_min_silence_duration": ("vad", "min_silence_duration", int),
    "audio_input_gain": ("audio_input", "gain", float),
    "audio_input_conversation_gain": ("audio_input", "conversation_gain", float),
}


def _py_list(items):
    return json.dumps(list(items), ensure_ascii=False, indent=4)


def _py_dict(d):
    return json.dumps(d, ensure_ascii=False, indent=4)


def _parse_value(raw):
    raw = str(raw).strip()
    low = raw.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _parse_legacy_advanced(lines):
    """兼容旧版 advanced_config（每行“点分键: 值”）解析成嵌套 dict。"""
    result = {}
    for item in lines or []:
        item = str(item).strip()
        if not item or ":" not in item:
            continue
        key, _, value = item.partition(":")
        key = key.strip()
        if not key:
            continue
        parts = key.split(".")
        node = result
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = _parse_value(value)
    return result


def _parse_wake_entries(opts):
    """解析 wake_entries。

    新版 UI 每条是一个字典：{keyword, agent_id, tts_speaker}；
    兼容旧版管道格式：唤醒词|agent_id|音色ID（音色可省略）；
    再兼容最早期的三个平铺字段。
    """
    entries = opts.get("wake_entries")
    if entries is None:
        # 兼容旧版三个平铺字段
        keywords = [
            str(w).strip()
            for w in opts.get("wake_words", []) or []
            if str(w).strip()
        ]
        routes = {}
        for item in opts.get("wake_word_routes", []) or []:
            item = str(item).strip()
            if ":" in item:
                kw, agent = item.split(":", 1)
                routes[kw.strip()] = agent.strip()
        voices = {}
        for item in opts.get("session_voices", []) or []:
            item = str(item).strip()
            if ":" in item:
                agent, spk = item.split(":", 1)
                voices[agent.strip()] = spk.strip()
        return keywords, routes, voices

    keywords = []
    routes = {}
    voices = {}
    for item in entries or []:
        if isinstance(item, dict):
            kw = str(item.get("keyword", "") or "").strip()
            agent = str(item.get("agent_id", "") or "").strip()
            speaker = str(item.get("tts_speaker", "") or "").strip()
        else:
            parts = [p.strip() for p in str(item).split("|")]
            if len(parts) == 3:
                kw, agent, speaker = parts
            elif len(parts) == 2:
                kw, agent, speaker = parts[0], parts[1], ""
            else:
                continue
        if not kw or not agent:
            continue
        if kw not in routes:
            keywords.append(kw)
        routes[kw] = agent
        if speaker:
            voices[agent] = speaker
    return keywords, routes, voices


def build_config(opts):
    default_agent = (
        str(opts.get("default_agent_id", "")) or
        "conversation.extended_openai_conversation"
    ).strip()
    default_speaker = (
        str(opts.get("default_tts_speaker", "")) or
        "xiaoai"
    ).strip()
    # 豆包接口兜底音色：避免把 "xiaoai"（小爱原生 TTS）误传给豆包
    doubao_default_speaker = (
        default_speaker
        if default_speaker and default_speaker != "xiaoai"
        else "zh_female_cancan_mars_bigtts"
    )

    keywords, routes, voices = _parse_wake_entries(opts)

    # 高级数字字段：新 UI 独立字段优先，旧版 advanced_config 仍可兼容
    advanced = {k: dict(v) for k, v in DEFAULTS.items()}
    for ui_key, (top, sub, cast) in NUMERIC_FIELDS.items():
        raw = opts.get(ui_key)
        if raw is None or raw == "":
            continue
        try:
            advanced[top][sub] = cast(raw)
        except (TypeError, ValueError):
            continue
    if opts.get("advanced_config"):
        for top, sub in _parse_legacy_advanced(opts.get("advanced_config")).items():
            advanced.setdefault(top, {}).update(sub)

    content = TEMPLATE
    content = content.replace("@AGENT_ROUTES@", _py_dict(routes))
    content = content.replace("@KEYWORDS@", _py_list(keywords))
    content = content.replace(
        "@HA_BASE_URL@",
        str(opts.get("ha_base_url", "http://homeassistant:8123")).strip(),
    )
    content = content.replace("@HA_TOKEN@", str(opts.get("ha_token", "")).strip())
    content = content.replace("@DEFAULT_AGENT_ID@", default_agent)
    content = content.replace(
        "@DOUBAO_API_KEY@", str(opts.get("doubao_api_key", "")).strip()
    )
    content = content.replace("@DEFAULT_TTS_SPEAKER@", default_speaker)
    content = content.replace("@DOUBAO_DEFAULT_SPEAKER@", doubao_default_speaker)
    content = content.replace("@SESSION_VOICES@", _py_dict(voices))
    content += (
        "\n\n# 高级配置覆盖（来自 UI 的数字字段，路径如 kws.keywords_score）\n"
        "_ADVANCED = " + _py_dict(advanced) + "\n\n"
        "def _deep_merge(base, extra):\n"
        "    for key, value in extra.items():\n"
        "        if isinstance(value, dict) and isinstance(base.get(key), dict):\n"
        "            _deep_merge(base[key], value)\n"
        "        else:\n"
        "            base[key] = value\n\n\n"
        "_deep_merge(APP_CONFIG, _ADVANCED)\n"
    )
    return content


def main():
    with open(OPTIONS_PATH, encoding="utf-8") as f:
        opts = json.load(f)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    content = build_config(opts)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("[Add-on] config.py 已根据 UI 配置生成: {}".format(OUTPUT_PATH))


if __name__ == "__main__":
    main()
