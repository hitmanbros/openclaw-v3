import aiohttp


class KimiClient:
    def __init__(self, api_key, model="kimi-2.6", base_url="https://api.moonshot.cn/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.token_tracker = {"input": 0, "output": 0}

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, messages, tools):
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
        }
        if tools is not None:
            payload["tools"] = tools
        return payload

    async def chat(self, messages, tools=None):
        payload = self._build_payload(messages, tools)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise RuntimeError(text)
                data = await response.json()
                if "usage" in data:
                    self.token_tracker["input"] += data["usage"].get("prompt_tokens", 0)
                    self.token_tracker["output"] += data["usage"].get("completion_tokens", 0)
                return data["choices"][0]["message"]["content"]
