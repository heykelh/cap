"""Fournisseurs de LLM interchangeables.

  gemini  : API Gemini (Google AI Studio), clé GEMINI_API_KEY, modèle GEMINI_MODEL
  groq    : API Groq, clé GROQ_API_KEY, modèle GROQ_MODEL
  offline : aucun appel ; chaque agent utilise son texte gabarit

Le LLM ne reçoit jamais de valeurs chiffrées : seulement les balises et leur signification.

Chaîne de secours : --llm gemini,groq essaie Gemini, puis Groq si Gemini est en panne.

Disjoncteur : au premier échec (délai dépassé, quota, erreur réseau), le fournisseur se
coupe pour le reste du dossier. Les agents suivants passent directement sur leur gabarit
au lieu d'attendre une nouvelle panne.
"""
import os

import requests


def timeout_s() -> float:
    """Lu à chaque création de fournisseur, donc après le chargement du fichier .env."""
    return float(os.getenv("LLM_TIMEOUT_S", "30"))


class LLMError(RuntimeError):
    pass


class _Breaker:
    """Coupe le fournisseur après la première panne."""

    disabled_reason: str | None = None

    def complete(self, system: str, prompt: str) -> str | None:
        if self.disabled_reason:
            raise LLMError(f"LLM coupé après une panne : {self.disabled_reason}")
        try:
            return self._complete(system, prompt)
        except Exception as exc:
            self.disabled_reason = str(exc)[:120]
            raise


class OfflineLLM:
    name = "hors ligne (gabarits)"
    disabled_reason = None

    def complete(self, system: str, prompt: str) -> str | None:
        return None


class GeminiLLM(_Breaker):
    def __init__(self):
        from google import genai
        from google.genai import types

        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise LLMError("GEMINI_API_KEY manquante dans .env")
        self.model = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
        self.name = f"Gemini ({self.model})"
        self.timeout = timeout_s()
        self._types = types
        # Délai en millisecondes, un seul essai : pas de réessai silencieux sur quota dépassé.
        self._client = genai.Client(
            api_key=key,
            http_options=types.HttpOptions(
                timeout=int(self.timeout * 1000),
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        # Réglage de la réflexion du modèle, détecté au premier appel :
        # niveau LOW (Gemini 3), sinon budget nul (Gemini 2.5), sinon réglage par défaut.
        self._thinking_modes = ["level_low", "budget_zero", "default"]

    def _thinking(self, mode):
        t = self._types
        if mode == "level_low":
            return t.ThinkingConfig(thinking_level=t.ThinkingLevel.LOW)
        if mode == "budget_zero":
            return t.ThinkingConfig(thinking_budget=0)
        return None

    def _complete(self, system: str, prompt: str) -> str | None:
        last_error = None
        while self._thinking_modes:
            mode = self._thinking_modes[0]
            config = self._types.GenerateContentConfig(
                system_instruction=system, temperature=0.2, thinking_config=self._thinking(mode)
            )
            try:
                resp = self._client.models.generate_content(model=self.model, contents=prompt, config=config)
                return (resp.text or "").strip()
            except Exception as exc:
                message = str(exc).lower()
                if "thinking" in message and len(self._thinking_modes) > 1:
                    self._thinking_modes.pop(0)  # réglage refusé par ce modèle : on essaie le suivant
                    last_error = exc
                    continue
                raise
        raise LLMError(f"aucun réglage de réflexion accepté : {last_error}")


class GroqLLM(_Breaker):
    URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self):
        self.key = os.getenv("GROQ_API_KEY")
        if not self.key:
            raise LLMError("GROQ_API_KEY manquante dans .env")
        self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        self.name = f"Groq ({self.model})"
        self.timeout = timeout_s()

    def list_models(self) -> list[str]:
        resp = requests.get("https://api.groq.com/openai/v1/models",
                            headers={"Authorization": f"Bearer {self.key}"}, timeout=self.timeout)
        if not resp.ok:
            raise LLMError(f"Groq {resp.status_code} : {resp.text[:200]}")
        return sorted(m["id"] for m in resp.json().get("data", []))

    def _complete(self, system: str, prompt: str) -> str | None:
        payload = {"model": self.model, "temperature": 0.2,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
        if self.model.startswith("openai/gpt-oss"):
            # Modèle à raisonnement : effort réduit pour une réponse rapide.
            payload["reasoning_effort"] = os.getenv("GROQ_REASONING_EFFORT", "low")
        resp = requests.post(
            self.URL,
            headers={"Authorization": f"Bearer {self.key}"},
            json=payload,
            timeout=self.timeout,
        )
        if not resp.ok:
            raise LLMError(f"Groq {resp.status_code} : {resp.text[:200]}")
        return resp.json()["choices"][0]["message"]["content"].strip()


class ChainLLM:
    """Chaîne de secours : essaie chaque fournisseur dans l'ordre, passe au suivant en cas de panne.

    Chaque maillon garde son propre disjoncteur : un fournisseur saturé n'est plus rappelé
    pendant le reste du dossier.
    """

    def __init__(self, providers: list):
        if not providers:
            raise LLMError("aucun fournisseur disponible dans la chaîne")
        self.providers = providers
        self.used: str | None = None
        self.timeout = max(getattr(p, "timeout", 0) for p in providers)

    @property
    def name(self) -> str:
        chain = " puis ".join(p.name for p in self.providers)
        return f"{chain} (dernier utilisé : {self.used})" if self.used else chain

    @property
    def disabled_reason(self):
        reasons = [getattr(p, "disabled_reason", None) for p in self.providers]
        return " / ".join(r for r in reasons if r) if all(reasons) else None

    def complete(self, system: str, prompt: str) -> str | None:
        errors = []
        for provider in self.providers:
            if getattr(provider, "disabled_reason", None):
                errors.append(f"{provider.name} coupé")
                continue
            try:
                text = provider.complete(system, prompt)
                self.used = provider.name
                return text
            except Exception as exc:
                errors.append(f"{provider.name} : {str(exc)[:80]}")
        raise LLMError(" ; ".join(errors))


def get_llm(name: str):
    name = (name or "offline").lower()
    if "," in name:
        providers = []
        for part in [n.strip() for n in name.split(",") if n.strip()]:
            try:
                providers.append(get_llm(part))
            except LLMError as exc:
                print(f"{part} ignoré : {exc}")
        return ChainLLM(providers)
    if name == "gemini":
        return GeminiLLM()
    if name == "groq":
        return GroqLLM()
    if name == "offline":
        return OfflineLLM()
    raise LLMError(f"Fournisseur inconnu : {name} (gemini, groq ou offline)")
