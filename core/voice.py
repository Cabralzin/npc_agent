# core/voice.py
import httpx
from openai import OpenAI
from core.persona import Persona

# Cliente HTTP com SSL verification desabilitado (para ambientes corporativos com proxy)
_http_client = httpx.Client(verify=False)

# Cliente global da OpenAI (pega OPENAI_API_KEY do ambiente)
_client = OpenAI(http_client=_http_client)

# Mapeando nossos voice_id internos -> vozes reais da API da OpenAI
# Ajuste como preferir, este é só um exemplo.
VOICE_MAP = {
    "lyra_01": "echo",
    "mira_01": "sage",
    "calem_01": "ballad",
    "raven_01": "onyx",
    "ezra_01": "nova",
    "kira_01": "coral",
}


def get_api_voice(persona: Persona) -> str:
    """
    Retorna o nome da voz da OpenAI a partir do voice_id da persona.
    Se não encontrar, usa uma default.
    """
    voice_id = getattr(persona, "voice_id", None)
    if voice_id is None:
        return "alloy"
    return VOICE_MAP.get(voice_id, "alloy")


def build_voice_instructions(persona: Persona) -> str:
    """
    Constrói uma instrução de estilo para o modelo de TTS
    usando os metadados de voz da persona.
    """
    parts = []

    voice_style = getattr(persona, "voice_style", None)
    voice_accent = getattr(persona, "voice_accent", None)
    voice_gender = getattr(persona, "voice_gender", None)
    voice_timbre = getattr(persona, "voice_timbre", None)
    voice_speed = getattr(persona, "voice_speed", None)
    voice_pitch = getattr(persona, "voice_pitch", None)
    speech_style = getattr(persona, "speech_style", None)

    if voice_style:
        parts.append(f"Estilo geral de voz: {voice_style}.")
    if voice_accent:
        parts.append(f"Sotaque: {voice_accent}.")
    if voice_gender:
        parts.append(f"Gênero percebido: {voice_gender}.")
    if voice_timbre:
        parts.append(f"Timbre: {voice_timbre}.")
    if voice_speed:
        parts.append(f"Velocidade de fala: {voice_speed}.")
    if voice_pitch:
        parts.append(f"Tom/Pitch: {voice_pitch}.")
    if speech_style:
        parts.append(f"Modo de falar do personagem: {speech_style}.")

    parts.append(f"Fale de forma coerente com a persona chamada {persona.name}.")

    return " ".join(parts)


def synthesize_npc_voice_bytes(text: str, persona: Persona) -> bytes:
    """
    Gera áudio em memória (bytes) para a fala do NPC usando a API de voz da OpenAI.
    Não salva nada em disco.
    """
    api_voice = get_api_voice(persona)
    instructions = build_voice_instructions(persona)

    # Modelo de TTS – pode trocar para "tts-1" ou "tts-1-hd" se quiser.
    model_name = "gpt-4o-mini-tts"

    # Usamos o streaming_response para receber os bytes aos poucos
    with _client.audio.speech.with_streaming_response.create(
        model=model_name,
        voice=api_voice,
        input=text,
        response_format="mp3",
        # instructions é opcional, mas aqui aproveitamos os metadados da persona
        instructions=instructions,
    ) as response:
        chunks = []
        for chunk in response.iter_bytes():
            chunks.append(chunk)
        return b"".join(chunks)
