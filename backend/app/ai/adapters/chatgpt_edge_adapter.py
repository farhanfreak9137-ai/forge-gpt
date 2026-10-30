import asyncio
import json
import logging
import re
from typing import Dict, Any, Optional
from app.ai.adapters.base import AIConnectorBase
from app.ai.protocol.protocol import (
    AIResponseEnvelope,
    ResponseType,
    ReportAnalysisPayload,
    FinishPayload,
)
from app.browser.manager.browser_manager import browser_manager

logger = logging.getLogger("forgeagent.ai.chatgpt_edge")


class ChatGPTEdgeAdapter(AIConnectorBase):
    """
    Playwright-based Microsoft Edge adapter for interacting with ChatGPT (chatgpt.com).
    Uses persistent browser profile and Microsoft Edge channel to submit prompts and extract replies.
    """

    def __init__(self, name: str = "chatgpt_edge", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.website_url = self.config.get("website_url", "https://chatgpt.com")
        self.timeout_ms = int(self.config.get("timeout_ms", 60000))

    async def initialize(self) -> bool:
        self.is_initialized = True
        return True

    async def check_availability(self) -> bool:
        edge_path = browser_manager.find_edge_path()
        return edge_path is not None

    async def get_capabilities(self) -> Dict[str, Any]:
        return {
            "provider": "chatgpt_edge",
            "browser": "Microsoft Edge (msedge)",
            "website_url": self.website_url,
            "streaming_detection": True,
            "interactive": True,
        }

    async def send_request(
        self,
        prompt: str,
        task_id: str,
        request_id: str,
        system_instruction: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None,
    ) -> AIResponseEnvelope:
        logger.info(f"Opening Microsoft Edge to communicate with ChatGPT at {self.website_url}...")
        page = await browser_manager.new_page()

        try:
            await page.goto(self.website_url, timeout=self.timeout_ms)
            await page.wait_for_timeout(3000)

            # Locate prompt input element
            ta_selector = 'textarea[name="prompt"], textarea#mobile-composer-prompt, textarea'
            ta = await page.wait_for_selector(ta_selector, timeout=20000)
            if not ta:
                raise RuntimeError("Could not find prompt textarea on ChatGPT page")

            # Click, focus, and type prompt
            await ta.click()
            await ta.focus()
            
            # Format prompt for ChatGPT (keep studio chat clean of protocol metadata)
            if task_id == "chat-studio":
                full_prompt = prompt
            else:
                full_prompt = (
                    f"{prompt}\n\n"
                    f"[ForgeAgent Metadata: task_id={task_id}, request_id={request_id}]"
                )
            await page.keyboard.type(full_prompt, delay=10)
            await page.wait_for_timeout(1000)

            # Locate and click send button or press Enter
            send_btn = await page.query_selector(
                'button[aria-label="Send message"], button[aria-label="Send prompt"], button[data-testid="send-button"]'
            )
            if send_btn and not (await send_btn.is_disabled()):
                await send_btn.click()
                logger.info("Clicked Send message button in Edge.")
            else:
                await page.keyboard.press("Enter")
                logger.info("Pressed Enter to submit prompt in Edge.")

            # Await response generation & stream completion
            logger.info("Waiting for ChatGPT response to complete in Edge...")
            extracted_text = ""
            for _ in range(30):  # poll up to 60 seconds
                await page.wait_for_timeout(2000)

                # Check if still streaming
                stop_btn = await page.query_selector(
                    'button[aria-label="Stop streaming"], button[aria-label="Stop generating"]'
                )
                
                # 1. Try to extract ONLY the latest assistant turn container
                assistant_elements = await page.query_selector_all('[data-message-author-role="assistant"]')
                if not assistant_elements:
                    assistant_elements = await page.query_selector_all('article')

                if assistant_elements:
                    latest_turn = assistant_elements[-1]
                    raw_turn_text = (await latest_turn.inner_text() or "").strip()
                    # Exclude user's own prompt if matched
                    if raw_turn_text and raw_turn_text != full_prompt.strip():
                        extracted_text = raw_turn_text

                # 2. Fallback to filtered paragraphs if assistant turn selector was not found
                if not extracted_text:
                    paragraphs = await page.query_selector_all('p')
                    meaningful_paragraphs = []
                    for p in paragraphs:
                        txt = (await p.text_content() or "").strip()
                        if txt and not any(ign in txt for ign in [
                            "ChatGPT is AI and can make mistakes",
                            "Log in to get answers",
                            "Turn questions into research",
                            "Try advanced features",
                            "Choose an account",
                        ]) and txt != full_prompt.strip():
                            meaningful_paragraphs.append(txt)

                    if meaningful_paragraphs:
                        extracted_text = "\n\n".join(meaningful_paragraphs)

                # If stop button is gone and we have content, response is complete
                if not stop_btn and len(extracted_text) > 0:
                    logger.info(f"ChatGPT response streaming completed ({len(extracted_text)} chars).")
                    break

            if not extracted_text:
                raise TimeoutError("ChatGPT did not produce a response within the timeout limit.")

            logger.info(f"Extracted reply from ChatGPT: {extracted_text[:200]}...")

            # Attempt to parse as forgeagent.v1 protocol JSON
            # First check for code block ```json ... ```
            json_candidate = None
            code_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", extracted_text, re.DOTALL)
            if code_block_match:
                json_candidate = code_block_match.group(1)
            elif extracted_text.strip().startswith("{") and extracted_text.strip().endswith("}"):
                json_candidate = extracted_text.strip()

            if json_candidate:
                try:
                    parsed = json.loads(json_candidate)
                    parsed["task_id"] = task_id
                    parsed["request_id"] = request_id
                    return AIResponseEnvelope.model_validate(parsed)
                except Exception as e:
                    logger.warning(f"Could not parse JSON payload from ChatGPT: {e}")

            # If natural language text response, wrap in protocol report
            clean_reply = re.sub(r"\[ForgeAgent Metadata:[^\]]*\]", "", extracted_text).strip()
            return AIResponseEnvelope(
                protocol_version="forgeagent.v1",
                task_id=task_id,
                request_id=request_id,
                response_type=ResponseType.REPORT_ANALYSIS,
                payload={
                    "analysis": clean_reply or extracted_text,
                    "findings": ["Received live conversational reply from ChatGPT in Microsoft Edge"],
                    "suggested_next_steps": ["Proceed with verified Edge-to-ChatGPT communication"],
                },
            )

        except Exception as e:
            logger.error(f"ChatGPT Edge interaction failed: {e}")
            raise
        finally:
            await page.close()

