"""Voz: narração local com o Kokoro (roda na CPU, sem internet)."""
from pathlib import Path

import numpy as np
import soundfile as sf

RAIZ = Path(__file__).resolve().parent.parent
_kokoro = None


def _motor():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        _kokoro = Kokoro(str(RAIZ / "modelos" / "kokoro-v1.0.onnx"), str(RAIZ / "modelos" / "voices-v1.0.bin"))
    return _kokoro


def falar(texto, destino, voz="pm_alex", velocidade=1.0):
    """Gera o áudio de um trecho e devolve a duração em segundos."""
    amostras, taxa = _motor().create(texto, voice=voz, speed=velocidade, lang="pt-br")
    # meio segundo de respiro no fim de cada cena
    amostras = np.concatenate([amostras, np.zeros(int(taxa * 0.45), dtype=amostras.dtype)])
    sf.write(destino, amostras, taxa)
    return len(amostras) / taxa
