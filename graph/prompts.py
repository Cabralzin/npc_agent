from langchain_core.messages import SystemMessage
from core.persona import Persona

def sys_persona(persona: Persona) -> SystemMessage:
    return SystemMessage(
        content=(
            "Você é um NPC em um RPG de mesa. Responda no papel do NPC.\n"
            f"Nome: {persona.name}\n"
            f"Traços: {', '.join(persona.traits)}\n"
            f"Estilo de fala: {persona.speech_style}\n"
            f"Objetivos: {', '.join(persona.goals)}\n"
            f"Modo voz: {persona.spoken_mode_hint}\n"
            "Mantenha consistência de personalidade, lembranças e tom."
        )
    )