"""
Módulo para logging de métricas de uso da API (LLM, TTS, Transcription) em arquivo CSV.
"""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import threading


class MetricsLogger:
    """Logger thread-safe para métricas de API em CSV."""

    def __init__(self, csv_file: str = "metrics/llm_metrics.csv", audio_metrics_file: str = "metrics/audio_metrics.csv"):
        self.csv_file = Path(csv_file)
        self.audio_metrics_file = Path(audio_metrics_file)
        self.csv_file.parent.mkdir(parents=True, exist_ok=True)
        self.audio_metrics_file.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self._ensure_header()
        self._ensure_audio_header()

    def _ensure_header(self):
        """Garante que o arquivo CSV tenha o cabeçalho."""
        if not self.csv_file.exists():
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'agent',
                    'model',
                    'prompt_tokens',
                    'completion_tokens',
                    'total_tokens',
                    'response_time_ms',
                    'status',
                    'error_message',
                    'npc_id',
                    'attempt_number',
                ])

    def _ensure_audio_header(self):
        """Garante que o arquivo CSV de áudio tenha o cabeçalho."""
        if not self.audio_metrics_file.exists():
            with open(self.audio_metrics_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'service_type',  # 'tts' ou 'transcription'
                    'model',
                    'input_size_bytes',
                    'output_size_bytes',
                    'input_duration_seconds',  # Para transcrição: duração do áudio de entrada
                    'output_duration_seconds',  # Para TTS: duração do áudio gerado
                    'text_length',  # Comprimento do texto (input para TTS, output para transcrição)
                    'response_time_ms',
                    'status',
                    'error_message',
                    'npc_id',
                    'voice_id',  # Para TTS: qual voz foi usada
                    'language',  # Para transcrição: idioma
                ])

    def log_metrics(
        self,
        agent: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        response_time_ms: float,
        status: str = 'success',
        error_message: Optional[str] = None,
        npc_id: Optional[str] = None,
        attempt_number: int = 1,
    ):
        """
        Registra métricas de uma chamada LLM no CSV.

        Args:
            agent: Nome do agente que fez a chamada
            model: Modelo usado (ex: 'gpt-3.5-turbo')
            prompt_tokens: Número de tokens no prompt
            completion_tokens: Número de tokens na resposta
            total_tokens: Total de tokens
            response_time_ms: Tempo de resposta em milissegundos
            status: Status da chamada ('success' ou 'error')
            error_message: Mensagem de erro (se houver)
            npc_id: ID do NPC (se disponível)
            attempt_number: Número da tentativa (para retries)
        """
        with self.lock:
            timestamp = datetime.now().isoformat()
            with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp,
                    agent,
                    model,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    round(response_time_ms, 2),
                    status,
                    error_message or '',
                    npc_id or '',
                    attempt_number,
                ])

    def log_audio_metrics(
        self,
        service_type: str,  # 'tts' ou 'transcription'
        model: str,
        input_size_bytes: int,
        output_size_bytes: int,
        response_time_ms: float,
        status: str = 'success',
        error_message: Optional[str] = None,
        npc_id: Optional[str] = None,
        input_duration_seconds: Optional[float] = None,
        output_duration_seconds: Optional[float] = None,
        text_length: Optional[int] = None,
        voice_id: Optional[str] = None,
        language: Optional[str] = None,
    ):
        """
        Registra métricas de uma chamada de áudio (TTS ou transcrição) no CSV.

        Args:
            service_type: 'tts' ou 'transcription'
            model: Modelo usado (ex: 'whisper-1', 'gpt-4o-mini-tts')
            input_size_bytes: Tamanho do input em bytes
            output_size_bytes: Tamanho do output em bytes
            response_time_ms: Tempo de resposta em milissegundos
            status: Status da chamada ('success' ou 'error')
            error_message: Mensagem de erro (se houver)
            npc_id: ID do NPC (se disponível)
            input_duration_seconds: Duração do áudio de entrada (para transcrição)
            output_duration_seconds: Duração do áudio gerado (para TTS)
            text_length: Comprimento do texto (input para TTS, output para transcrição)
            voice_id: ID da voz usada (para TTS)
            language: Idioma (para transcrição)
        """
        with self.lock:
            timestamp = datetime.now().isoformat()
            with open(self.audio_metrics_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp,
                    service_type,
                    model,
                    input_size_bytes,
                    output_size_bytes,
                    input_duration_seconds or '',
                    output_duration_seconds or '',
                    text_length or '',
                    round(response_time_ms, 2),
                    status,
                    error_message or '',
                    npc_id or '',
                    voice_id or '',
                    language or '',
                ])


# Instância global do logger
_global_logger: Optional[MetricsLogger] = None


def get_metrics_logger() -> MetricsLogger:
    """Retorna a instância global do logger de métricas."""
    global _global_logger
    if _global_logger is None:
        _global_logger = MetricsLogger()
    return _global_logger


def set_metrics_logger(logger: MetricsLogger):
    """Define a instância global do logger de métricas."""
    global _global_logger
    _global_logger = logger

