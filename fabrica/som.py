"""Som: trilha cinematográfica sombria e efeitos sonoros gerados na hora (sem direitos autorais).

Tudo é sintetizado com numpy: nada é baixado da internet.
"""
import numpy as np
import soundfile as sf

TAXA = 48000
rng = np.random.default_rng()


def _t(dur):
    return np.arange(int(dur * TAXA)) / TAXA


def _passa_baixa(x, janela):
    """Filtro passa-baixa simples (média móvel), rápido para sinais longos."""
    janela = max(1, int(janela))
    c = np.cumsum(np.concatenate([np.zeros(janela), x]))
    return (c[janela:] - c[:-janela]) / janela


def _env(n, ataque, queda):
    """Envelope: sobe em `ataque` segundos e cai exponencialmente com constante `queda`."""
    t = np.arange(n) / TAXA
    return np.minimum(1, t / max(ataque, 1e-4)) * np.exp(-t / queda)


def _nota(freq):
    return 440 * 2 ** ((freq - 69) / 12)


def _pad(freqs, dur, brilho=6):
    """Acorde 'de cordas': ondas dente-de-serra suaves, levemente desafinadas."""
    t = _t(dur)
    s = np.zeros_like(t)
    for f in freqs:
        for desaf in (-0.12, 0.0, 0.11):
            fase = rng.uniform(0, 2 * np.pi)
            for h in range(1, brilho + 1):
                s += np.sin(2 * np.pi * f * (1 + desaf / 100) * h * t + fase * h) / (h ** 1.3)
    return s / (len(freqs) * 3 * 2.2)


# ---------------------------------------------------------------- efeitos
def impacto(dur=1.8):
    """BOOM grave de trailer: queda de tom + ruído."""
    n = int(dur * TAXA)
    t = _t(dur)
    freq = 30 + 70 * np.exp(-t * 9)
    corpo = np.sin(2 * np.pi * np.cumsum(freq) / TAXA) * _env(n, 0.003, 0.55)
    ruido = _passa_baixa(rng.normal(0, 1, n), 18) * _env(n, 0.001, 0.12) * 1.6
    return np.tanh((corpo + ruido) * 1.8) * 0.9


def whoosh(dur=0.7):
    """Passagem de ar: ruído com filtro que abre e fecha."""
    n = int(dur * TAXA)
    t = np.linspace(0, 1, n)
    ruido = rng.normal(0, 1, n)
    grave = _passa_baixa(ruido, 40)
    agudo = ruido - _passa_baixa(ruido, 6)
    mistura = grave * (1 - t) + agudo * t * 0.5
    return mistura * np.sin(np.pi * t) ** 2 * 0.5


def subida(dur=2.5):
    """Riser: tensão crescente antes da contagem."""
    n = int(dur * TAXA)
    t = _t(dur)
    freq = 120 * (12 ** (t / dur))
    tom = np.sin(2 * np.pi * np.cumsum(freq) / TAXA) * 0.25
    ruido = (rng.normal(0, 1, n) - _passa_baixa(rng.normal(0, 1, n), 10)) * 0.2
    return (tom + ruido) * (t / dur) ** 2.2


def coracao(dur=3.0, bpm=90):
    """Batimento cardíaco (tum-tum) para a contagem."""
    s = np.zeros(int(dur * TAXA))
    batida = int(60 / bpm * TAXA)
    for ini in range(0, len(s), batida):
        for atraso, vol in ((0, 1.0), (0.17, 0.65)):
            k = ini + int(atraso * TAXA)
            n = min(int(0.25 * TAXA), len(s) - k)
            if n <= 0:
                continue
            tt = np.arange(n) / TAXA
            s[k:k + n] += np.sin(2 * np.pi * (45 + 25 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 18) * vol
    return s * 0.9


# ---------------------------------------------------------------- trilha
PROGRESSAO = [[57, 60, 64], [53, 57, 60], [50, 53, 57], [52, 56, 59]]  # Am, F, Dm, E (lá menor)


def trilha(duracao, marcos, bpm=80):
    """Trilha sombria que acompanha as cenas.

    marcos: lista de (início, tipo) das cenas, ex.: [(0, 'gancho'), (8.2, 'escolha'), ...]
    A intensidade sobe na escolha/contagem, explode na revelação e assenta no final.
    """
    n = int(duracao * TAXA)
    mix = np.zeros(n)
    compasso = 4 * 60 / bpm

    # 1. pad de acordes (troca a cada 2 compassos)
    dur_acorde = compasso * 2
    for i, ini in enumerate(np.arange(0, duracao, dur_acorde)):
        notas = [_nota(m) for m in PROGRESSAO[i % 4]]
        trecho = _pad(notas, dur_acorde + 1.0)
        trecho *= np.minimum(1, np.minimum(_t(dur_acorde + 1.0) / 0.8, (dur_acorde + 1.0 - _t(dur_acorde + 1.0)) / 1.0))
        a = int(ini * TAXA)
        b = min(n, a + len(trecho))
        mix[a:b] += _passa_baixa(trecho[:b - a], 6) * 0.22

    # 2. grave contínuo (lá) com respiração lenta
    t = _t(duracao)
    mix += np.sin(2 * np.pi * 55 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * t / 8)) * 0.18

    # intensidade por cena
    def intensidade(seg):
        tipo = "gancho"
        for ini, tp in marcos:
            if seg >= ini:
                tipo = tp
        return {"gancho": 0.35, "escolha": 0.7, "contagem": 0.9, "ruim": 1.0, "bom": 0.8, "final": 0.4,
                "fato": 0.7, "pergunta": 0.55, "resposta": 0.75, "inicio": 0.3, "meio": 0.6,
                "climax": 1.0}.get(tipo, 0.5)

    # 3. tambores de trailer no 1 e no 3 (e colcheias quando a tensão sobe)
    batida = 60 / bpm
    tambor = impacto(1.0) * 0.5
    for k, ini in enumerate(np.arange(0, duracao, batida)):
        forca = intensidade(ini)
        if forca < 0.5 or (k % 2 and forca < 0.9):
            continue
        a = int(ini * TAXA)
        b = min(n, a + len(tambor))
        mix[a:b] += tambor[:b - a] * forca * (1.0 if k % 4 == 0 else 0.6)

    # 4. pulso agudo (relógio) na tensão
    for ini in np.arange(0, duracao, batida / 2):
        if intensidade(ini) >= 0.7:
            a = int(ini * TAXA)
            m = min(int(0.05 * TAXA), n - a)
            if m > 0:
                tt = np.arange(m) / TAXA
                mix[a:a + m] += np.sin(2 * np.pi * 2200 * tt) * np.exp(-tt * 90) * 0.06

    # fade de entrada e saída
    mix *= np.minimum(1, np.minimum(t / 1.5, (duracao - t) / 2.0).clip(0))
    return mix


def efeitos(duracao, marcos):
    """Faixa de efeitos: whoosh nas trocas, BOOM nas revelações, subida + coração na contagem."""
    n = int(duracao * TAXA)
    fx = np.zeros(n)

    def por(sinal, em, vol=1.0):
        a = max(0, int(em * TAXA))
        b = min(n, a + len(sinal))
        if b > a:
            fx[a:b] += sinal[:b - a] * vol

    for i, (ini, tipo) in enumerate(marcos):
        if i > 0:
            por(whoosh(), ini - 0.35, 0.8)
        if tipo in ("escolha", "ruim", "bom", "fato", "resposta", "climax"):
            por(impacto(), ini, 1.0 if tipo != "resposta" else 0.7)
        if tipo == "contagem":
            por(subida(2.2), ini - 2.2, 0.9)
            por(coracao(3.0), ini, 1.0)
        if tipo == "final":
            por(impacto(2.4), ini, 0.6)
    return fx


def salvar(sinal, destino, pico=0.89):
    m = np.max(np.abs(sinal)) or 1
    sf.write(destino, (sinal / m * pico).astype(np.float32), TAXA)
