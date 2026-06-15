import os
import json
import re
import uuid
import base64
import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

import aiohttp

try:
    import yaml
except ImportError:
    yaml = None

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger


class SelfiePlugin(Star):
    """AstrBot 自拍插件：根据三视图和对话上下文，生成符合角色长相的自拍照。"""

    REFERENCE_FILENAME = "reference.png"
    PROMPT_CONFIG_FILE = "prompts.yaml"

    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.plugin_dir = Path(__file__).parent
        self.data_dir = self.plugin_dir / "data"
        self.temp_dir = self.data_dir / "temp"
        self.data_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)

        # 解析触发关键词
        raw_triggers = self.config.get("trigger_keywords", "")
        self.triggers = [t.strip() for t in raw_triggers.split("\n") if t.strip()]

        # 加载外置提示词配置
        self.prompt_config = self._load_prompt_config()

    def _load_prompt_config(self) -> Dict[str, Any]:
        """加载外置的提示词配置文件。"""
        config_path = self.plugin_dir / self.PROMPT_CONFIG_FILE
        if not config_path.exists():
            logger.warning(f"提示词配置文件不存在: {config_path}")
            return self._get_default_prompt_config()
        
        if not yaml:
            logger.warning("PyYAML 未安装，使用默认提示词配置")
            return self._get_default_prompt_config()
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"加载提示词配置失败: {e}")
            return self._get_default_prompt_config()

    def _get_default_prompt_config(self) -> Dict[str, Any]:
        """返回默认的提示词配置（当外置配置加载失败时使用）。"""
        return {
            "structured": {
                "system_prompt": "You are a professional AI image prompt engineer specializing in FIRST-PERSON SELFIE photos. A selfie is a photo the character takes of THEMSELVES. The PHONE and HAND must NOT be visible. Generate a selfie description by filling each slot: expression, pose, background, lighting, mood, framing.",
                "context_sections": {
                    "personality": "=== Character Personality Card ===\n{content}",
                    "conversation": "=== Conversation Context ===\n{content}",
                    "time": "=== Current Time Context ===\n{content}",
                    "user_scene": "=== User Requested Scene ===\n{content}",
                    "final_instruction": "\nNow output the six slot lines for their selfie."
                }
            },
            "free": {
                "system_prompt": "You are a professional AI image prompt engineer specializing in SELFIE photos. Start your prompt with 'selfie photo, '. DO NOT include phone or hand. Keep under 200 characters.",
                "context_sections": {
                    "conversation": "Conversation context:\n{content}",
                    "time": "Current time: {content}",
                    "user_scene": "User requested scene: {content}",
                    "final_instruction": "\nGenerate the selfie prompt."
                }
            },
            "style_map": {
                "auto": "follow reference image style, selfie composition",
                "anime": "anime style, 2D illustration",
                "realistic": "photographic, realistic",
                "semi-realistic": "semi-realistic, painterly"
            },
            "quality_tags": {
                "positive": ["masterpiece", "best quality", "ultra-detailed", "detailed face", "detailed eyes"],
                "negative": ["no phone", "no cellphone", "no hand holding phone"]
            },
            "scene_elements": {
                "activities": ["eating", "drinking", "reading", "walking", "sitting"],
                "objects": ["ice cream", "coffee", "book", "phone", "flower"],
                "locations": ["home", "cafe", "beach", "park", "bedroom"],
                "time_of_day": {
                    "morning": "morning light",
                    "afternoon": "afternoon sunlight",
                    "evening": "evening sunset",
                    "night": "night lights"
                }
            }
        }

    # ─── 场景元素提取 ──────────────────────────────────────

    def _extract_scene_elements(self, context: str, user_scene: Optional[str]) -> str:
        """从对话上下文和用户场景描述中提取关键场景元素。"""
        elements = []
        
        # 合并上下文和用户场景
        full_text = (context or "") + " " + (user_scene or "")
        full_text = full_text.lower().strip()
        
        if not full_text:
            return ""

        # 从配置中获取场景元素关键词
        scene_elements = self.prompt_config.get("scene_elements", {})
        
        # 提取活动元素
        for activity in scene_elements.get("activities", []):
            if activity in full_text:
                elements.append(activity)
        
        # 提取物品元素
        for obj in scene_elements.get("objects", []):
            if obj in full_text:
                elements.append(obj)
        
        # 提取位置元素
        for location in scene_elements.get("locations", []):
            if location in full_text:
                elements.append(location)
        
        # 如果没有找到预定义元素，尝试提取名词短语
        if not elements and full_text:
            # 使用简单规则提取潜在场景元素
            patterns = [
                r"(eating|drinking|reading|cooking|working|playing)\s+(\w+)",
                r"(at|in|on)\s+(\w+\s?\w*)",
                r"(\w+)\s+(beach|park|cafe|room|office|bedroom)"
            ]
            for pattern in patterns:
                match = re.search(pattern, full_text)
                if match:
                    elements.extend([g for g in match.groups() if g])
        
        if elements:
            logger.info(f"提取到场景元素: {elements}")
            return ", ".join(elements)
        
        return ""

    # ─── 指令 ──────────────────────────────────────────────

    @filter.command("selfie", alias={"自拍", "拍照"})
    async def selfie(self, event: AstrMessageEvent):
        """ 生成一张符合当前聊天氛围的角色自拍照。

        用法:
          /selfie              自动生成
          /selfie 在沙滩看日落  指定场景
        """
        scene_desc = self._extract_scene_desc(event)
        yield event.plain_result("📸 正在构思画面……")
        async for result in self._do_selfie(event, scene_desc):
            yield result

    @filter.command("selfie_view")
    async def selfie_view(self, event: AstrMessageEvent):
        """🖼️ 查看角色的三视图参考图。

        请将三视图合成为一张图片，命名为 reference.png，
        放在插件目录的 data/ 文件夹下。
        """
        ref_path = self._get_reference_path()
        if ref_path and ref_path.exists():
            yield event.plain_result("📌 三视图参考图")
            yield event.image_result(str(ref_path))
        else:
            yield event.plain_result(
                "还没有添加三视图参考图哦~\n"
                "请将正视图、侧视图、后视图合成为一张图片，命名为\n"
                "  reference.png\n"
                "放在插件目录的 data/ 文件夹下。"
            )

    # ─── 自然语言触发 ─────────────────────────────────────

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_natural_trigger(self, event: AstrMessageEvent):
        """检测用户消息是否含有触发关键词，自动生成自拍。"""
        message = event.message_str.strip()
        if not message or not self.triggers:
            return

        for trigger in self.triggers:
            if trigger in message:
                yield event.plain_result("📸 来，拍一张~")
                async for result in self._do_selfie(event, None):
                    yield result
                event.stop_event()
                return

    # ─── 核心逻辑 ─────────────────────────────────────────

    async def _do_selfie(self, event: AstrMessageEvent, scene_desc: Optional[str]):
        """核心流程：获取上下文 → 人格卡 → LLM 生成 <形容> → 图片 API → 发送。"""
        start_time = time.time()
        llm_time = 0.0
        image_time = 0.0

        # 并行获取独立数据
        context_text, personality_prompt = await asyncio.gather(
            self._get_context(event),
            self._get_personality_prompt(event),
        )

        # 提取场景元素
        scene_elements = self._extract_scene_elements(context_text, scene_desc)
        if scene_elements:
            logger.info(f"场景元素分析完成: {scene_elements}")

        llm_start = time.time()
        prompt = await self._build_prompt(event, context_text, scene_desc, personality_prompt, scene_elements)
        llm_time = time.time() - llm_start
        
        if not prompt:
            yield event.plain_result("🤔 构思画面时卡壳了，再跟我说句话试试~")
            return

        logger.info(f"selfie prompt: {prompt}")

        image_start = time.time()
        image_result = await self._call_image_api(prompt)
        image_time = time.time() - image_start
        
        total_time = time.time() - start_time

        if not image_result:
            logger.info(f"生图失败 | 总耗时: {total_time:.2f}s (LLM: {llm_time:.2f}s, 图片API: {image_time:.2f}s)")
            yield event.plain_result(
                "😅 拍照时出了点问题，请检查：\n"
                "1. 插件配置中是否选择了正确的图片生成模型\n"
                "2. 自定义 API 配置是否正确\n"
                "3. 余额是否充足"
            )
            return

        logger.info(f"生图完成 | 总耗时: {total_time:.2f}s (LLM: {llm_time:.2f}s, 图片API: {image_time:.2f}s)")
        yield event.image_result(image_result)

    # ─── 对话上下文获取 ───────────────────────────────────

    async def _get_context(self, event: AstrMessageEvent) -> str:
        """获取当前会话最近的对话历史。"""
        try:
            umo = event.unified_msg_origin
            conv_mgr = self.context.conversation_manager
            curr_cid = await conv_mgr.get_curr_conversation_id(umo)
            if curr_cid:
                conv = await conv_mgr.get_conversation(umo, curr_cid)
                if conv and conv.history:
                    history = conv.history
                    return history[-1000:] if len(history) > 1000 else history
        except Exception as e:
            logger.warning(f"获取对话上下文失败：{e}")
        return ""

    # ─── 读取角色人格卡 ─────────────────────────────────

    async def _get_personality_prompt(self, event: AstrMessageEvent) -> str:
        """从 AstrBot 人格系统读取当前会话的角色人格提示词。"""
        if not self.config.get("use_persona", True):
            logger.info("已关闭角色人格卡参考")
            return ""

        try:
            pm = self.context.persona_manager
            if not pm:
                return ""

            umo = event.unified_msg_origin

            conversation_persona_id = None
            try:
                conv_mgr = self.context.conversation_manager
                curr_cid = await conv_mgr.get_curr_conversation_id(umo)
                if curr_cid:
                    conv = await conv_mgr.get_conversation(umo, curr_cid)
                    if conv:
                        conversation_persona_id = getattr(conv, "persona_id", None)
            except Exception:
                pass

            result = await pm.resolve_selected_persona(
                umo=umo,
                conversation_persona_id=conversation_persona_id,
                platform_name=event.get_platform_name(),
            )

            if result and result[1]:
                persona = result[1]
                prompt_text = persona.get("prompt", "")
                if prompt_text:
                    logger.info(f"已读取角色人格卡: {result[0]}")
                    return prompt_text

            default = await pm.get_default_persona_v3(umo)
            if default and default.get("prompt"):
                prompt_text = default["prompt"]
                if prompt_text and prompt_text != "You are a helpful and friendly assistant.":
                    logger.info("已读取默认人格卡")
                    return prompt_text
        except Exception as e:
            logger.warning(f"读取人格卡失败：{e}")

        return ""

    def _get_time_description(self) -> str:
        """获取当前现实时间的描述，用于生成符合时间场景的自拍。"""
        now = datetime.now()
        hour = now.hour
        
        time_map = self.prompt_config.get("scene_elements", {}).get("time_of_day", {})
        
        if 5 <= hour < 8:
            return time_map.get("early_morning", "early morning, sunrise")
        elif 8 <= hour < 12:
            return time_map.get("morning", "morning, bright daylight")
        elif 12 <= hour < 14:
            return time_map.get("noon", "noon, midday sun")
        elif 14 <= hour < 17:
            return time_map.get("afternoon", "afternoon, warm sunlight")
        elif 17 <= hour < 19:
            return time_map.get("evening", "evening, sunset")
        elif 19 <= hour < 22:
            return time_map.get("night", "night, evening lights")
        else:
            return time_map.get("late_night", "late night, dim lighting")

    # ─── LLM 生成绘图 Prompt ──────────────────────────────

    async def _build_prompt(
        self,
        event: AstrMessageEvent,
        context: str,
        user_scene: Optional[str],
        personality_prompt: str = "",
        scene_elements: str = "",
    ) -> Optional[str]:
        """调用 LLM 生成英文绘图 prompt。"""
        llm_provider_id = self.config.get("llm_provider_id", "")
        if not llm_provider_id:
            try:
                umo = event.unified_msg_origin
                llm_provider_id = await self.context.get_current_chat_provider_id(umo)
            except Exception:
                pass
        if not llm_provider_id:
            logger.warning("当前没有可用的 LLM 提供商")
            return None

        # ── 结构化模式（有角色人格卡） ──────────────────────
        if personality_prompt:
            config = self.prompt_config.get("structured", {})
            system_prompt = config.get("system_prompt", "")
            
            parts = []
            sections = config.get("context_sections", {})
            
            if personality_prompt:
                parts.append(sections.get("personality", "=== Character Personality ===\n{content}").format(content=personality_prompt))
            if context:
                parts.append(sections.get("conversation", "=== Conversation Context ===\n{content}").format(content=context[:600]))
            if self.config.get("use_real_time", False):
                time_desc = self._get_time_description()
                parts.append(sections.get("time", "=== Time Context ===\n{content}").format(content=time_desc))
            if scene_elements:
                parts.append(f"=== Key Scene Elements (incorporate these into selfie) ===\n{scene_elements}")
            if user_scene:
                parts.append(sections.get("user_scene", "=== User Scene ===\n{content}").format(content=user_scene))
            parts.append(sections.get("final_instruction", "\nOutput the selfie slots."))

            try:
                resp = await self.context.llm_generate(
                    chat_provider_id=llm_provider_id,
                    prompt="\n\n".join(parts),
                    system_prompt=system_prompt,
                )
                text = resp.completion_text.strip().strip("\"'")
            except Exception as e:
                logger.error(f"结构化 prompt 生成失败：{e}")
                return None

            slots = {"expression": "", "pose": "", "background": "", "lighting": "", "mood": "", "framing": ""}
            for line in text.split("\n"):
                line = line.strip()
                for key in slots:
                    if line.lower().startswith(key + ":"):
                        val = line[len(key) + 1:].strip().strip("\"'")
                        if val:
                            slots[key] = val

            filled = [v for v in slots.values() if v]
            if not filled:
                logger.warning("结构化解析失败，使用原始 LLM 输出")
                prompt = text
            else:
                parts_list = ["selfie photo"]
                if slots.get("framing"):
                    parts_list.append(slots["framing"])
                if slots.get("expression"):
                    parts_list.append(slots["expression"])
                if slots.get("pose"):
                    parts_list.append(slots["pose"])
                if slots.get("background"):
                    parts_list.append(slots["background"])
                if slots.get("lighting"):
                    parts_list.append(slots["lighting"])
                if slots.get("mood"):
                    parts_list.append(slots["mood"])
                if scene_elements:
                    parts_list.append(scene_elements)
                prompt = ", ".join(parts_list)

            prompt += ", " + self._build_quality_tags()

            logger.info(f"结构化模式生成的 prompt: {prompt}")

            if prompt:
                return prompt
            return None

        # ── 自由模式（无角色人格卡） ────────────────────────
        style_key = self.config.get("output_style", "auto")
        style_map = self.prompt_config.get("style_map", {})
        style_instruction = style_map.get(style_key, "follow reference image style")

        config = self.prompt_config.get("free", {})
        system_prompt = config.get("system_prompt", "").format(style_instruction=style_instruction)

        parts = []
        sections = config.get("context_sections", {})
        
        if context:
            parts.append(sections.get("conversation", "Conversation:\n{content}").format(content=context[:600]))
        if self.config.get("use_real_time", False):
            time_desc = self._get_time_description()
            parts.append(sections.get("time", "Time: {content}").format(content=time_desc))
        if scene_elements:
            parts.append(f"Key scene elements: {scene_elements}")
        if user_scene:
            parts.append(sections.get("user_scene", "User scene: {content}").format(content=user_scene))
        parts.append(sections.get("final_instruction", "\nGenerate prompt."))

        try:
            resp = await self.context.llm_generate(
                chat_provider_id=llm_provider_id,
                prompt="\n".join(parts),
                system_prompt=system_prompt,
            )
            text = resp.completion_text.strip().strip("\"'")
            if text:
                if not text.lower().startswith("selfie"):
                    text = "selfie photo, " + text
                if scene_elements and scene_elements not in text.lower():
                    text += ", " + scene_elements
                text += ", " + self._build_quality_tags()
                return text
        except Exception as e:
            logger.error(f"LLM prompt 生成失败：{e}")

        return None

    def _build_quality_tags(self) -> str:
        """构建质量标签字符串。"""
        quality_config = self.prompt_config.get("quality_tags", {})
        positive = quality_config.get("positive", [])
        negative = quality_config.get("negative", [])
        return ", ".join(positive + negative)

    # ─── 三视图参考图 ────────────────────────────────────

    def _get_reference_path(self) -> Optional[Path]:
        """获取三视图合成图文件的路径（支持多种扩展名）。"""
        for ext in [".png", ".jpg", ".jpeg", ".webp"]:
            path = self.data_dir / f"{self.REFERENCE_FILENAME.replace('.png', '')}{ext}"
            if path.exists():
                return path
        return None

    def _get_reference_base64(self) -> Optional[str]:
        """将三视图参考图读取为 base64 编码（自动压缩到 1024px 以内）。"""
        path = self._get_reference_path()
        if not path:
            return None
        try:
            from PIL import Image
            import io
            img = Image.open(path)
            max_size = 1024
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            logger.info(f"参考图已压缩: {path.name} ({img.size[0]}x{img.size[1]})")
            return f"data:image/png;base64,{b64}"
        except Exception as e:
            logger.error(f"读取参考图失败：{e}")
            return None

    # ─── 图片 API 调用 ──────────────────────────────────

    async def _call_image_api(self, prompt: str) -> Optional[str]:
        """根据配置调用图片生成 API。"""
        image_provider_id = self.config.get("image_provider_id", "")
        if not image_provider_id:
            logger.warning("未配置图片生成提供商")
            return None

        try:
            provider = await self.context.get_provider_by_id(image_provider_id)
            if not provider:
                logger.warning(f"未找到图片生成提供商: {image_provider_id}")
                return None

            model_name = getattr(provider, "model_name", "")
            api_key = getattr(provider, "api_key", "")
            base_url = getattr(provider, "api_base", "")
            
            logger.info(f"从 provider 系统获取到图片配置: model={model_name}, base_url={base_url}")

            if not model_name or not api_key:
                logger.warning("图片生成提供商配置不完整")
                return None

            reference_base64 = self._get_reference_base64()

            api_mode = self.config.get("image_api_mode", "openai")
            if api_mode == "openai":
                return await self._call_openai_api(prompt, api_key, base_url, model_name, reference_base64)
            else:
                return await self._call_custom_api(prompt, api_key, reference_base64)

        except Exception as e:
            logger.error(f"调用图片 API 失败：{e}")
            return None

    async def _call_openai_api(self, prompt: str, api_key: str, base_url: str, model_name: str, reference_base64: Optional[str]) -> Optional[str]:
        """调用 OpenAI 兼容的图片生成 API。"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{base_url.rstrip('/')}/v1/images/generations"
                payload = {
                    "model": model_name,
                    "prompt": prompt,
                    "n": 1,
                    "size": self.config.get("image_size", "1024x1024"),
                    "response_format": "url"
                }

                if reference_base64:
                    payload["image"] = reference_base64
                    payload["mode"] = "image-to-image"

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }

                async with session.post(url, json=payload, headers=headers, timeout=60) as resp:
                    if resp.status != 200:
                        logger.error(f"图片 API 返回错误: {resp.status}")
                        return None
                    data = await resp.json()
                    if data.get("data") and len(data["data"]) > 0:
                        return data["data"][0].get("url")
                    return None
        except Exception as e:
            logger.error(f"调用 OpenAI 图片 API 失败：{e}")
            return None

    async def _call_custom_api(self, prompt: str, api_key: str, reference_base64: Optional[str]) -> Optional[str]:
        """调用自定义格式的图片生成 API。"""
        try:
            async with aiohttp.ClientSession() as session:
                url = self.config.get("image_api_url", "")
                if not url:
                    logger.warning("未配置自定义 API 地址")
                    return None

                template = self.config.get("custom_request_template", "")
                if not template:
                    logger.warning("未配置自定义请求模板")
                    return None

                payload_str = template.replace("{{prompt}}", prompt)
                if reference_base64:
                    payload_str = payload_str.replace("{{reference_base64}}", reference_base64)
                else:
                    payload_str = payload_str.replace("\"{{reference_base64}}\"", "null")

                payload = json.loads(payload_str)

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }

                logger.info(f"自定义 API 请求: {url}, payload keys: {list(payload.keys())}")

                async with session.post(url, json=payload, headers=headers, timeout=60) as resp:
                    if resp.status != 200:
                        logger.error(f"自定义图片 API 返回错误: {resp.status}")
                        return None
                    data = await resp.json()
                    
                    response_path = self.config.get("custom_response_path", "output.choices[0].message.content[0].image")
                    return self._extract_from_json(data, response_path)
        except Exception as e:
            logger.error(f"调用自定义图片 API 失败：{e}")
            return None

    def _extract_from_json(self, data: dict, path: str) -> Optional[str]:
        """从 JSON 数据中按路径提取值。"""
        try:
            keys = path.split(".")
            result = data
            for key in keys:
                if key.isdigit():
                    result = result[int(key)]
                else:
                    result = result.get(key)
                if result is None:
                    return None
            return str(result)
        except Exception as e:
            logger.error(f"JSON 路径提取失败：{e}")
            return None

    def _extract_scene_desc(self, event: AstrMessageEvent) -> Optional[str]:
        """从指令中提取场景描述部分。"""
        msg = event.message_str.strip()
        if msg.startswith("/selfie") or msg.startswith("/自拍") or msg.startswith("/拍照"):
            parts = msg.split(None, 1)
            if len(parts) > 1:
                return parts[1]
        return None
