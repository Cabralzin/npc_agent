# core/voice.py
import httpx
from openai import OpenAI
from core.persona import Persona

# Cliente HTTP com SSL verification desabilitado (para ambientes corporativos com proxy)
_http_client = httpx.Client(verify=False)

# Cliente global da OpenAI (pega OPENAI_API_KEY do ambiente)
_client = OpenAI(http_client=_http_client)

# Mapeia seus voice_id internos -> vozes da OpenAI
VOICE_MAP = {
    "lyra_01": "ember",
    "mira_01": "luna",
    "calem_01": "verse",
    "raven_01": "solace",
    "ezra_01": "nova",
    "kira_01": "alloy",
}


def get_api_voice(persona: Persona) -> str:
    voice_id = getattr(persona, "voice_id", None)
    if not voice_id:
        return "alloy"
    return VOICE_MAP.get(voice_id, "alloy")


def build_voice_instructions(persona: Persona) -> str:
    """
    Instruções mais ricas para o modelo de TTS, usando os metadados de voz e o estilo da persona.
    A ideia é deixar a fala mais interpretada, menos robótica.
    """
    parts = []

    voice_style = getattr(persona, "voice_style", None)
    voice_accent = getattr(persona, "voice_accent", None)
    voice_gender = getattr(persona, "voice_gender", None)
    voice_timbre = getattr(persona, "voice_timbre", None)
    voice_speed = getattr(persona, "voice_speed", None)
    voice_pitch = getattr(persona, "voice_pitch", None)
    speech_style = getattr(persona, "speech_style", None)

    parts.append(
        "Fale como um personagem em uma cena de RPG, com interpretação natural, "
        "respiração leve e ritmo orgânico, evitando soar robótico."
    )

    if voice_style:
        parts.append(f"Estilo geral de voz: {voice_style}.")
    if voice_accent:
        parts.append(f"Sotaque aproximado: {voice_accent}.")
    if voice_gender:
        parts.append(f"Gênero percebido da voz: {voice_gender}.")
    if voice_timbre:
        parts.append(f"Timbre desejado: {voice_timbre}.")
    if voice_speed:
        parts.append(f"Tendência de velocidade: {voice_speed}.")
    if voice_pitch:
        parts.append(f"Tendência de tom/pitch: {voice_pitch}.")
    if speech_style:
        parts.append(f"Modo de falar do personagem: {speech_style}.")

    parts.append(
        "Faça pequenas variações naturais de ritmo e ênfase, use pausas curtas "
        "onde houver vírgulas ou reticências, e insira micro hesitações sutis quando fizer sentido."
    )
    parts.append(f"A fala deve ser coerente com a personalidade e história de {persona.name}.")

    return " ".join(parts)


def transcribe_audio(audio_bytes: bytes, language: str = "pt") -> str:
    """
    Transcreve áudio para texto usando a API Whisper da OpenAI.
    
    Args:
        audio_bytes: Bytes do arquivo de áudio (formato: wav, mp3, m4a, etc.)
        language: Código do idioma (padrão: "pt" para português)
    
    Returns:
        Texto transcrito do áudio
    """
    import io
    import logging
    
    logger = logging.getLogger("npc.core.voice")
    
    if not audio_bytes:
        raise ValueError("audio_bytes está vazio")
    
    logger.info(f"Transcrevendo áudio: {len(audio_bytes)} bytes, idioma={language}")
    
    # Cria um arquivo temporário em memória
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "audio.wav"  # Whisper detecta o formato automaticamente
    
    try:
        # Usa a API de transcrição da OpenAI
        transcript = _client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=language,
        )
        text = transcript.text.strip()
        logger.info(f"Transcrição concluída: {text[:50]}...")
        return text
    except Exception as e:
        logger.error(f"Erro ao transcrever áudio: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise


def synthesize_npc_voice_bytes(text: str, persona: Persona) -> bytes:
    """
    Gera áudio em memória (bytes) para a fala do NPC usando a API de voz da OpenAI.
    Não salva em disco.
    """
    api_voice = get_api_voice(persona)
    instructions = build_voice_instructions(persona)

    # Modelo recomendado de TTS
    model_name = "gpt-4o-mini-tts"

    with _client.audio.speech.with_streaming_response.create(
        model=model_name,
        voice=api_voice,
        input=text,
        response_format="mp3",
        instructions=instructions,
    ) as response:
        chunks = []
        for chunk in response.iter_bytes():
            chunks.append(chunk)
        return b"".join(chunks)
