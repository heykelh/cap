"""Client de modèle de langage avec appel d'outils (format OpenAI), Groq puis Gemini en relais.

C'est ce qui permet aux agents de choisir eux-mêmes leurs actions : le modèle reçoit la liste
des outils et répond soit par un texte, soit par une demande d'appel d'outil avec ses paramètres.
"""
import os
import re
import time

import requests


class ToolChatError(RuntimeError):
    pass


class _Provider:
    def __init__(self, name, url, key_env, model, extra=None):
        self.name, self.url, self.key, self.model = name, url, os.getenv(key_env), model
        self.extra = extra or {}
        self.broken: str | None = None if self.key else f"{key_env} absente"

    @property
    def label(self) -> str:
        return f"{self.name} ({self.model})"

    def chat(self, messages, tools, timeout):
        payload = {"model": self.model, "messages": messages, "temperature": 0.2, **self.extra}
        if tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]
            payload["tool_choice"] = "auto"
        resp = requests.post(self.url, json=payload, timeout=timeout,
                             headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
        if resp.status_code >= 400:
            raise ToolChatError(f"{self.name} HTTP {resp.status_code} : {resp.text[:160]}")
        msg = resp.json()["choices"][0]["message"]
        return {"content": msg.get("content") or "", "tool_calls": msg.get("tool_calls") or []}


class ToolChat:
    """Essaie chaque fournisseur dans l'ordre ; un fournisseur en panne est écarté pour la suite."""

    def __init__(self, order: str | None = None):
        order = (order or os.getenv("CAP_AGENT_LLM", "groq,gemini,groq-20b")).split(",")
        catalog = {
            "groq": lambda: _Provider("Groq", "https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY",
                                      os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
                                      {"reasoning_effort": os.getenv("AGENT_REASONING_EFFORT", "low")}),
            "groq-20b": lambda: _Provider("Groq", "https://api.groq.com/openai/v1/chat/completions", "GROQ_API_KEY",
                                          "openai/gpt-oss-20b", {"reasoning_effort": "low"}),
            "gemini": lambda: _Provider("Gemini", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                                        "GEMINI_API_KEY", os.getenv("GEMINI_AGENT_MODEL", "gemini-2.5-flash")),
        }
        self.providers = [catalog[o.strip()]() for o in order if o.strip() in catalog]
        self.timeout = float(os.getenv("AGENT_TIMEOUT_S", "60"))
        self.used: str | None = None

    @property
    def name(self) -> str:
        return self.used or " puis ".join(p.label for p in self.providers if not p.broken) or "aucun"

    def available(self) -> bool:
        return any(not p.broken for p in self.providers)

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """Saturation passagère (429, 503) : on attend et on réessaie, puis on passe au fournisseur suivant.
        Un fournisseur n'est écarté pour la suite que sur une erreur durable (clé, modèle, requête)."""
        errors = []
        for p in self.providers:
            if p.broken:
                continue
            for attempt in range(4):
                try:
                    out = p.chat(messages, tools, self.timeout)
                    self.used = p.label
                    return out
                except (requests.RequestException, ToolChatError, KeyError, ValueError) as exc:
                    text = str(exc)
                    errors.append(f"{p.name} : {text[:120]}")
                    transient = any(c in text for c in ("HTTP 429", "HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504")) \
                        or isinstance(exc, requests.Timeout)
                    if transient and attempt < 3:
                        hint = re.search(r"try again in ([\d.]+)s", text)
                        time.sleep(min(float(hint.group(1)) + 1, 25) if hint else 4 * (attempt + 1))
                        continue
                    if not transient:
                        p.broken = text[:160]
                    break
        raise ToolChatError("aucun fournisseur d'IA disponible : " + " | ".join(errors[-3:]))
