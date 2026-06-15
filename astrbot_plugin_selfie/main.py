import os
import json
import re
import uuid
import base64
import asyncio
from pathlib import Path
from typing import Optional

import aiohttp

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api import logger


class SelfiePlugin(Star):
    """AstrBot 自拍插件：根据三视图和对话上下文，生成符合角色长相的自拍照。"""

    REFERENCE_FILENAME = "reference.png"

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
        # 并行获取独立数据
        context_text, personality_prompt = await asyncio.gather(
            self._get_context(event),
            self._get_personality_prompt(event),
        )

        prompt = await self._build_prompt(event, context_text, scene_desc, personality_prompt)
        if not prompt:
            yield event.plain_result("🤔 构思画面时卡壳了，再跟我说句话试试~")
            return

        logger.info(f"selfie prompt: {prompt}")

        image_result = await self._call_image_api(prompt)
        if not image_result:
            yield event.plain_result(
                "😅 拍照时出了点问题，请检查：\n"
                "1. 插件配置中是否选择了正确的图片生成模型\n"
                "2. 自定义 API 配置是否正确\n"
                "3. 余额是否充足"
            )
            return

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
                    return history[-800:] if len(history) > 800 else history
        except Exception as e:
            logger.warning(f"获取对话上下文失败：{e}")
        return ""

    # ─── 读取角色人格卡 ─────────────────────────────────

    async def _get_personality_prompt(self, event: AstrMessageEvent) -> str:
        """从 AstrBot 人格系统读取当前会话的角色人格提示词。

        当配置中 use_persona 开启时，通过 persona_manager 获取
        当前生效的人格（Personality.prompt），供 LLM 生成 <形容> 时参考。
        """
        if not self.config.get("use_persona", True):
            logger.info("已关闭角色人格卡参考")
            return ""

        try:
            pm = self.context.persona_manager
            if not pm:
                return ""

            umo = event.unified_msg_origin

            # 获取会话绑定的 persona_id
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

            # 通过 resolve_selected_persona 获取最准确的人格
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

            # fallback 到默认人格
            default = await pm.get_default_persona_v3(umo)
            if default and default.get("prompt"):
                prompt_text = default["prompt"]
                if prompt_text and prompt_text != "You are a helpful and friendly assistant.":
                    logger.info("已读取默认人格卡")
                    return prompt_text
        except Exception as e:
            logger.warning(f"读取人格卡失败：{e}")

        return ""

    # ─── LLM 生成绘图 Prompt ──────────────────────────────

    async def _build_prompt(
        self,
        event: AstrMessageEvent,
        context: str,
        user_scene: Optional[str],
        personality_prompt: str = "",
    ) -> Optional[str]:
        """调用 LLM 生成英文绘图 prompt。

        两种模式:
          1. 结构化模式（personality_prompt 非空）
             LLM 按槽位填空，输出 <表情>,<姿态>,<背景>,<光线>,<情绪>,<质量标签>
             代码拼接为完整 prompt，末尾自动追加 quality_tags

          2. 自由模式（personality_prompt 为空，或 use_persona 关闭）
             沿用原逻辑，LLM 自由输出，风格由 output_style 控制
        """
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
            system_prompt = (
                "You are a professional AI image prompt engineer specializing in FIRST-PERSON SELFIE photos.\n\n"
                "You have access to the character's personality card. Internalize who the character is — "
                "their traits, habits, voice. You are now thinking AS this character.\n\n"
                "A selfie is a photo the character takes of THEMSELVES with their phone/camera. "
                "The camera is in THEIR hand — not a third-party photographer. "
                "The image must feel like the character's own selfie: they see their own face, "
                "their own arm extending the phone OUTSIDE the frame, their own environment behind them.\n\n"
                "CRITICAL RULE: The PHONE and HAND holding the phone must NOT be visible in the selfie photo. "
                "The arm extends toward the camera but the phone itself is outside the frame.\n\n"
                "Generate a selfie description by filling each slot below with 2-6 English words, "
                "one slot per line. Use EXACTLY this format:\n\n"
                "expression:\npose:\nbackground:\nlighting:\nmood:\nframing:\n\n"
                "Rules:\n"
                "- CRITICAL: This is a FIRST-PERSON SELFIE. The character holds the phone OUTSIDE FRAME. "
                "Describe the scene AS THE CHARACTER EXPERIENCES IT.\n"
                "- CRITICAL: Replicate the art style from the reference image EXACTLY. Match the style perfectly.\n"
                "- Do NOT describe the character's appearance or clothes (the reference image handles that).\n"
                "- Do NOT mention phone, cellphone, or hand in any slot - the phone is outside the frame.\n"
                "- Use conversation context to infer current scene, mood, and why they'd take a selfie right now.\n"
                "- 'expression' = the character's own facial expression (e.g., gentle smile, playful wink, pensive look)\n"
                "- 'pose' = how the character angles their body for the selfie (arm extends toward camera but outside frame) "
                "(e.g., arm extended out of frame, gentle head tilt toward camera, looking at camera with smile)\n"
                "- 'background' = what's visible behind the character in the selfie frame "
                "(e.g., cozy sunlit bedroom, bustling street cafe, messy desk with warm lamp)\n"
                "- 'lighting' = light source as experienced by the character "
                "(e.g., warm sunset glow on face from window, soft neon signs casting purple hue)\n"
                "- 'mood' = the emotional atmosphere of this selfie moment "
                "(e.g., quiet contentment, playful excitement, tender nostalgia)\n"
                "- 'framing' = the selfie composition (phone/hand NOT visible) "
                "(e.g., close-up face and shoulders, waist-up casual shot, portrait orientation selfie)\n"
                "- Each slot exactly 2-6 words (short, vivid).\n"
                "- Output ONLY the six slot lines in order, no extra text, no markdown."
            )

            parts = []
            parts.append(f"=== Character Personality Card (embody this character) ===\n{personality_prompt}")
            if context:
                parts.append(f"=== Conversation Context (infer why the character takes this selfie right now) ===\n{context[:600]}")
            if user_scene:
                parts.append(f"=== User Requested Scene ===\n{user_scene}")
            parts.append("\nNow think as the character. Output the six slot lines for their selfie.")

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

            # 解析槽位（兼容新增的 framing 槽位）
            slots = {"expression": "", "pose": "", "background": "", "lighting": "", "mood": "", "framing": ""}
            for line in text.split("\n"):
                line = line.strip()
                for key in slots:
                    if line.lower().startswith(key + ":"):
                        val = line[len(key) + 1:].strip().strip("\"'")
                        if val:
                            slots[key] = val

            # 组装 prompt — 以第一人称自拍视角开头
            filled = [v for v in slots.values() if v]
            if not filled:
                # 结构化解析失败，回退到原始 LLM 输出
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
                prompt = ", ".join(parts_list)

            # 追加质量标签和负面提示词
            quality_tags = (
                "masterpiece, best quality, ultra-detailed, "
                "intricate details, detailed face, detailed eyes, "
                "natural skin texture, sharp focus, "
                "style consistent with reference image, match reference art style exactly, "
                "no phone, no cellphone, no hand holding phone, "
                "no smartphone, no camera visible, hands outside frame"
            )
            prompt += ", " + quality_tags

            logger.info(f"结构化模式生成的 prompt: {prompt}")

            if prompt:
                return prompt
            return None

        # ── 自由模式（无角色人格卡） ────────────────────────
        style_map = {
            "auto": "Strictly follow the art style of the reference image, replicate the style exactly, same art style as reference, selfie composition front-facing",
            "anime": "Style: anime, 2D illustration, cel-shaded, Japanese animation style, selfie composition",
            "realistic": "Style: photographic selfie, ultra-realistic, photorealistic, front-facing camera",
            "semi-realistic": "Style: semi-realistic, painterly, soft brush strokes, anime-inspired portrait, selfie",
        }
        style_key = self.config.get("output_style", "auto")
        style_instruction = style_map.get(style_key, style_map["auto"])

        system_prompt = (
            "You are a professional AI image prompt engineer specializing in SELFIE photos.\n\n"
            "A selfie means the character is holding their phone and taking a picture of THEMSELVES. "
            "The camera is in the character's hand — NOT a third-party observer. "
            "The PHONE and HAND holding the phone must NOT be visible in the image. "
            "The arm extends toward camera but is outside the frame.\n\n"
            "Rules:\n"
            "1. Start your prompt with \"selfie photo, \"\n"
            "2. Include selfie-specific details: framing (close-up, waist-up, etc.), "
            "expression, lighting on face, background from their perspective\n"
            "3. Use conversation context to infer the current scene and why a selfie fits\n"
            f"4. {style_instruction}\n"
            "5. DO NOT include phone, cellphone, hand, or holding phone in the prompt\n"
            "6. Keep under 200 characters\n"
            "7. Output ONLY the prompt text, no explanations"
        )

        parts = []
        if context:
            parts.append(f"Recent conversation context (infer the scene and why the character would take a selfie):\n{context[:600]}")
        if user_scene:
            parts.append(f"User requested scene: {user_scene}")
        parts.append("\nGenerate the selfie prompt now. Output ONLY the prompt text.")

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
                # 添加质量标签和负面提示词
                text += ", masterpiece, best quality, ultra-detailed, detailed face, detailed eyes, "
                text += "natural skin texture, sharp focus, style consistent with reference image, match reference art style exactly, "
                text += "no phone, no cellphone, no hand holding phone, "
                text += "no smartphone, no camera visible, hands outside frame"
                return text
        except Exception as e:
            logger.error(f"LLM prompt 生成失败：{e}")

        return None

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
            # 压缩到最长边 1024px，减小 payload
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
        except ImportError:
            # 没有 PIL 时 fallback 原图
            data = path.read_bytes()
            ext = path.suffix[1:] if path.suffix else "png"
            return f"data:image/{ext};base64,{base64.b64encode(data).decode()}"
        except Exception as e:
            logger.error(f"读取参考图失败：{e}")
            return None

    # ─── 图片生成 API ────────────────────────────────────

    async def _get_image_provider_info(self) -> Optional[dict]:
        """从 AstrBot provider 系统获取图片生成模型的 API 信息。

        读取用户在插件配置中选择的 image_provider_id，
        通过 provider_manager.inst_map 获取 provider 实例，
        提取 api_key、base_url、model_name。
        """
        provider_id = self.config.get("image_provider_id", "")
        if not provider_id:
            logger.warning("未配置图片生成模型")
            return None

        try:
            pm = self.context.provider_manager
            provider = await pm.get_provider_by_id(provider_id)
            if not provider:
                logger.warning(f"找不到 provider: {provider_id}")
                return None

            # 获取 API Key
            api_key = ""
            if hasattr(provider, "get_current_key"):
                api_key = provider.get_current_key()
            if not api_key:
                keys = provider.get_keys() if hasattr(provider, "get_keys") else []
                api_key = keys[0] if keys else ""

            # 获取 base_url（api_base）
            base_url = provider.provider_config.get("api_base", "") if hasattr(provider, "provider_config") else ""

            # 获取模型名
            model_name = provider.get_model() if hasattr(provider, "get_model") else ""
            if not model_name:
                model_name = getattr(provider, "model_name", "")

            logger.info(f"从 provider 系统获取到图片配置: model={model_name}, base_url={base_url}")
            return {"api_key": api_key, "base_url": base_url, "model": model_name}
        except Exception as e:
            logger.error(f"获取图片 provider 信息失败：{e}")
            return None

    async def _call_image_api(self, prompt: str) -> Optional[str]:
        """根据配置调用图片生成 API。"""
        mode = self.config.get("image_api_mode", "openai")
        if mode == "custom":
            return await self._call_custom_api(prompt)
        else:
            return await self._call_openai_api(prompt)

    async def _call_openai_api(self, prompt: str) -> Optional[str]:
        """通过 AstrBot provider 系统调用 OpenAI 兼容格式的图生图 API。

        自动从 provider 实例获取 api_key、base_url、model_name。
        """
        info = await self._get_image_provider_info()
        if not info:
            logger.warning("无法获取图片生成模型的配置信息")
            return None

        api_key = info["api_key"]
        base_url = info["base_url"]
        model = info["model"]
        size = self.config.get("image_size", "1024x1024")

        if not api_key:
            logger.warning("图片生成模型未配置 API Key")
            return None
        if not base_url:
            logger.warning("图片生成模型未配置 API 地址")
            return None

        # 拼出 /v1/images/generations 端点
        base_url = base_url.rstrip("/")
        if base_url.endswith("/v1"):
            api_url = f"{base_url}/images/generations"
        else:
            api_url = f"{base_url}/v1/images/generations"

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "prompt": prompt, "n": 1, "size": size}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, headers=headers, json=payload, timeout=120) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items = data.get("data", [])
                        if items:
                            img = items[0]
                            if "url" in img:
                                return img["url"]
                            if "b64_json" in img:
                                return self._save_b64(img["b64_json"])
                    else:
                        err = await resp.text()
                        logger.error(f"图片生成 API 错误 ({resp.status}): {err}")
        except asyncio.TimeoutError:
            logger.error("图片生成 API 超时")
        except Exception as e:
            logger.error(f"图片生成 API 请求失败：{e}")

        return None

    async def _call_custom_api(self, prompt: str) -> Optional[str]:
        """自定义 API，支持传入三视图参考图。

        模板中可使用:
          {{prompt}}            — 绘图提示词（由 LLM 生成）
          {{reference_base64}}  — 三视图合成图的 base64

        自动补全:
          - 如果请求体中没有 model 字段，会从 provider 系统自动注入模型名
        """
        # 优先从 provider 系统获取 API Key
        info = await self._get_image_provider_info()
        api_key = info["api_key"] if info else ""
        model = info["model"] if info else ""

        api_url = self.config.get("image_api_url", "")
        template_str = self.config.get("custom_request_template", "")
        resp_path = self.config.get("custom_response_path", "images[0]")

        if not api_url:
            logger.warning("未配置自定义 API 地址")
            return None
        if not template_str:
            logger.warning("未配置自定义 API 请求模板")
            return None

        # 替换模板占位符
        ref_b64 = self._get_reference_base64() or ""
        body = template_str.replace("{{prompt}}", prompt).replace("{{reference_base64}}", ref_b64)

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error(f"请求模板 JSON 解析失败：{e}")
            return None

        # 强制用 provider 系统的模型名（覆盖模板中填的值）
        if model:
            payload["model"] = model
            logger.info(f"注入模型名: {model}")

        # 调整 content 顺序：image 在前、text 在后（DashScope 图片编辑格式要求）
        try:
            messages = payload.get("input", {}).get("messages", [])
            for msg in messages:
                content = msg.get("content", [])
                if isinstance(content, list) and len(content) > 1:
                    images = [c for c in content if isinstance(c, dict) and "image" in c]
                    texts = [c for c in content if isinstance(c, dict) and "text" in c]
                    if images and texts:
                        msg["content"] = images + texts
        except Exception:
            pass

        # 如果没有参考图，从请求体中移除空的 image 字段
        if not ref_b64:
            try:
                messages = payload.get("input", {}).get("messages", [])
                for msg in messages:
                    content = msg.get("content", [])
                    msg["content"] = [c for c in content if not (isinstance(c, dict) and "image" in c and not c["image"])]
            except Exception:
                pass

        logger.info(f"自定义 API 请求: url={api_url}, payload={json.dumps(payload, ensure_ascii=False)[:300]}")

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, headers=headers, json=payload, timeout=120) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # 先用配置的路径提取
                        result = self._extract_path(data, resp_path)
                        # 提取不到时尝试常用回退路径
                        if not result or not isinstance(result, str):
                            for fallback in ["output.choices[0].message.content[0].image", "output.results[0].url", "output.choices[0].message.content[0].image_url.url", "data[0].url", "images[0].url", "image_url"]:
                                result = self._extract_path(data, fallback)
                                if result and isinstance(result, str):
                                    logger.info(f"使用回退路径 '{fallback}' 提取到图片")
                                    break
                        if result and isinstance(result, str):
                            if result.startswith(("http://", "https://")):
                                return result
                            if len(result) > 100:
                                return self._save_b64(result)
                            return result
                    else:
                        err = await resp.text()
                        logger.error(f"自定义 API 错误 ({resp.status}): {err}")
                        # 记录 payload 方便排查
                        logger.error(f"请求 payload: {json.dumps(payload, ensure_ascii=False)[:500]}")
        except asyncio.TimeoutError:
            logger.error("自定义 API 超时")
        except Exception as e:
            logger.error(f"自定义 API 请求失败：{e}")

        return None

    # ─── 工具方法 ─────────────────────────────────────────

    def _save_b64(self, b64_str: str) -> Optional[str]:
        """保存 base64 图片到临时目录，返回本地路径。"""
        try:
            if "," in b64_str:
                b64_str = b64_str.split(",")[1]
            data = base64.b64decode(b64_str)
            name = f"selfie_{uuid.uuid4().hex[:8]}.png"
            path = self.temp_dir / name
            path.write_bytes(data)
            return str(path)
        except Exception as e:
            logger.error(f"保存图片失败：{e}")
            return None

    @staticmethod
    def _extract_path(data, path_expr: str):
        """从嵌套的 dict/list 中按路径提取值。"""
        try:
            parts = re.findall(r"[^.\[\]]+|\[\d+\]", path_expr)
            cur = data
            for p in parts:
                if p.startswith("[") and p.endswith("]"):
                    cur = cur[int(p[1:-1])]
                elif isinstance(cur, dict):
                    cur = cur[p]
                else:
                    return None
            return cur
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"提取响应路径 '{path_expr}' 失败：{e}")
            return None

    @staticmethod
    def _extract_scene_desc(event: AstrMessageEvent) -> Optional[str]:
        text = event.message_str.strip()
        for prefix in ["/selfie", "/自拍", "/拍照"]:
            if text.startswith(prefix):
                rest = text[len(prefix):].strip()
                return rest if rest else None
        return None

    async def terminate(self):
        """插件卸载时清理临时文件。"""
        try:
            import shutil
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                logger.info("已清理自拍插件临时目录")
        except Exception as e:
            logger.warning(f"清理临时目录失败：{e}")
