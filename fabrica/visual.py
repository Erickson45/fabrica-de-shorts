"""Visual: camadas transparentes (legendas, cartões A/B, contagem, faixas) e clipes de fundo do Pexels."""
import json
import random
import textwrap
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

L, A = 1080, 1920  # vertical 9:16
FONTE_FORTE = "C:/Windows/Fonts/ariblk.ttf"
FONTE_MEDIA = "C:/Windows/Fonts/arialbd.ttf"


def _fonte(tam, forte=True):
    try:
        return ImageFont.truetype(FONTE_FORTE if forte else FONTE_MEDIA, tam)
    except OSError:
        return ImageFont.load_default(tam)


def _tela():
    return Image.new("RGBA", (L, A), (0, 0, 0, 0))


def _hex(cor, alfa=255):
    cor = cor.lstrip("#")
    return tuple(int(cor[i:i + 2], 16) for i in (0, 2, 4)) + (alfa,)


def _texto_central(d, y, texto, fonte, cor=(255, 255, 255, 255), contorno=10, largura=22):
    linhas = textwrap.wrap(texto, largura) or [""]
    alt = fonte.size * 1.12
    for i, linha in enumerate(linhas):
        w = d.textlength(linha, font=fonte)
        d.text(((L - w) / 2, y + i * alt), linha, font=fonte, fill=cor,
               stroke_width=contorno, stroke_fill=(0, 0, 0, 255))
    return y + len(linhas) * alt


# ---------------------------------------------------------------- camadas
def legenda(texto, destino, destaque=None, y=1180):
    """Legenda estilo Shorts: caixa alta, contorno grosso, palavra-chave colorida."""
    img = _tela()
    d = ImageDraw.Draw(img)
    f = _fonte(84)
    palavras = texto.upper().split()
    linhas, atual = [], []
    for p in palavras:  # quebra manual para colorir palavra por palavra
        teste = " ".join(atual + [p])
        if atual and d.textlength(teste, font=f) > 900:
            linhas.append(atual)
            atual = [p]
        else:
            atual.append(p)
    linhas.append(atual)
    espaco = d.textlength(" ", font=f)
    for linha in linhas:
        larg = sum(d.textlength(p, font=f) for p in linha) + espaco * (len(linha) - 1)
        x = (L - larg) / 2
        for p in linha:
            # destaca a última palavra do bloco, só se for uma palavra "forte" (4+ letras)
            forte = len(p.strip(".,!?…:;\"'")) >= 4
            cor = _hex(destaque) if destaque and forte and p == linha[-1] and linha is linhas[-1] else (255, 255, 255, 255)
            d.text((x, y), p, font=f, fill=cor, stroke_width=11, stroke_fill=(0, 0, 0, 255))
            x += d.textlength(p, font=f) + espaco
        y += 96
    img.save(destino)


def cartoes(opcao_a, opcao_b, cor_a, cor_b, destino, y0=430):
    """Os dois caminhos, em cartões coloridos."""
    opcoes_cartoes([opcao_a, opcao_b], [cor_a, cor_b], destino, y0=y0)


def opcoes_cartoes(opcoes, cores, destino, y0=430, certa=None, cor_certa="#16A34A"):
    """Cartões A/B/C. Com `certa` (índice), a resposta certa acende em verde e as outras apagam."""
    img = _tela()
    d = ImageDraw.Draw(img)
    altura = 220 if len(opcoes) <= 2 else 180
    passo = altura + (50 if len(opcoes) <= 2 else 36)
    for i, nome in enumerate(opcoes):
        letra = "ABC"[i]
        y = y0 + i * passo
        apagado = certa is not None and i != certa
        cor = cor_certa if certa == i else cores[i % len(cores)]
        alfa = 90 if apagado else 235
        d.rounded_rectangle((90, y, L - 90, y + altura), radius=34, fill=_hex(cor, alfa),
                            outline=(255, 255, 255, 120 if apagado else 235), width=8 if certa == i else 5)
        cy = y + altura / 2
        d.ellipse((130, cy - 62, 254, cy + 62), fill=(0, 0, 0, 90 if apagado else 120))
        if certa == i:  # "certo" desenhado à mão
            d.line(((162, cy + 2), (184, cy + 26), (226, cy - 26)), fill=(255, 255, 255, 255), width=16, joint="curve")
        else:
            fl = _fonte(80)
            d.text((192 - d.textlength(letra, font=fl) / 2, cy - 52), letra, font=fl,
                   fill=(255, 255, 255, 140 if apagado else 255))
        fn = _fonte(56)
        nome = str(nome).upper()
        while d.textlength(nome, font=fn) > 620 and fn.size > 32:
            fn = _fonte(fn.size - 4)
        d.text((290, cy - fn.size * 0.62), nome, font=fn, fill=(255, 255, 255, 130 if apagado else 255),
               stroke_width=4, stroke_fill=(0, 0, 0, 160))
    img.save(destino)


def faixas_cinema(destino, altura=210):
    """Faixas pretas em cima e embaixo (cara de filme)."""
    img = _tela()
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, L, altura), fill=(0, 0, 0, 255))
    d.rectangle((0, A - altura, L, A), fill=(0, 0, 0, 255))
    img.save(destino)


def capitulo(numero_romano, nome, destino, cor="#F8FAFC"):
    """Marca de capítulo discreta no topo: 'I · O INÍCIO'."""
    img = _tela()
    d = ImageDraw.Draw(img)
    f = _fonte(40, forte=False)
    texto = f"{numero_romano}  ·  {nome.upper()}"
    w = d.textlength(texto, font=f)
    d.text(((L - w) / 2, 240), texto, font=f, fill=_hex(cor, 230))
    d.line(((L - w) / 2, 300, (L + w) / 2, 300), fill=_hex(cor, 120), width=2)
    img.save(destino)


def numero(n, destino, cor="#FFD60A", y=1250):
    img = _tela()
    d = ImageDraw.Draw(img)
    d.ellipse((L / 2 - 210, y - 210, L / 2 + 210, y + 210), fill=(0, 0, 0, 150),
              outline=_hex(cor), width=12)
    f = _fonte(300)
    t = str(n)
    d.text((L / 2 - d.textlength(t, font=f) / 2, y - 190), t, font=f, fill=_hex(cor))
    img.save(destino)


def faixa(texto, cor, destino, y=300):
    """Faixa no topo: 'CAMINHO A · PORTA VERMELHA'."""
    img = _tela()
    d = ImageDraw.Draw(img)
    f = _fonte(50)
    texto = texto.upper()
    while d.textlength(texto, font=f) > 860 and f.size > 30:
        f = _fonte(f.size - 3)
    w = d.textlength(texto, font=f)
    d.rounded_rectangle(((L - w) / 2 - 44, y, (L + w) / 2 + 44, y + f.size + 50), radius=60,
                        fill=_hex(cor, 240))
    d.text(((L - w) / 2, y + 22), texto, font=f, fill=(255, 255, 255, 255))
    img.save(destino)


def chamada(texto, destino, cor="#FFD60A", y=300, tam=70):
    img = _tela()
    d = ImageDraw.Draw(img)
    _texto_central(d, y, texto.upper(), _fonte(tam), _hex(cor), contorno=10, largura=int(20 * 70 / tam))
    img.save(destino)


# ---------------------------------------------------------------- legendas no tempo
def blocos_legenda(texto, duracao, por_bloco=3):
    """Divide o texto em blocos de até ~3 palavras, sem misturar frases diferentes,
    e distribui o tempo pelo tamanho de cada bloco."""
    import re
    blocos = []
    for frase in re.split(r"(?<=[.!?…])\s+", texto.strip()):
        palavras = frase.split()
        partes = [palavras[i:i + por_bloco] for i in range(0, len(palavras), por_bloco)]
        if len(partes) > 1 and len(partes[-1]) == 1:  # nada de palavra sozinha no fim
            sobra = partes.pop()
            partes[-1] = partes[-1] + sobra
        blocos += [" ".join(p) for p in partes]
    util = max(0.5, duracao - 0.45)  # o fim de cada cena é respiro
    total = sum(len(b) + 4 for b in blocos)
    t, saida = 0.0, []
    for b in blocos:
        dur = util * (len(b) + 4) / total
        saida.append((b, t, t + dur))
        t += dur
    return saida


# ---------------------------------------------------------------- bancos de vídeo (uso livre)
# clipes "alegres" quebram o clima sombrio do canal
EVITAR = ("sunny", "summer", "beach", "happy", "tropical", "colorful", "sunshine", "vacation",
          "turquoise", "holiday", "smile", "party", "celebration", "flower", "spring", "kids")
CLIMA = ("dark", "night", "fog", "storm", "shadow", "creepy", "horror", "abandoned", "mist", "rain")


def com_clima(busca):
    """Garante que a busca peça um clima escuro (ex.: 'island exit' -> 'island exit dark')."""
    return busca if any(p in busca.lower() for p in CLIMA) else f"{busca} dark"

def _baixar(url, destino):
    if not destino.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "fabrica-shorts"})
        with urllib.request.urlopen(req, timeout=180) as r, open(destino, "wb") as f:
            f.write(r.read())
    return destino


def buscar_clipe_pixabay(busca, pasta_cache, chave, usados=()):
    """Baixa um clipe do Pixabay (licença livre, uso comercial). Devolve (caminho, id, página) ou None."""
    if not chave:
        return None
    pasta_cache = Path(pasta_cache).parent / "pixabay"
    pasta_cache.mkdir(parents=True, exist_ok=True)
    url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode(
        {"key": chave, "q": busca[:100], "per_page": 20, "safesearch": "true"})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "fabrica-shorts"}),
                                    timeout=30) as r:
            hits = json.load(r).get("hits", [])
    except Exception:
        return None
    candidatos = [h for h in hits if h["id"] not in usados and h.get("duration", 0) >= 5
                  and not any(e in (h.get("tags") or "").lower() for e in EVITAR)]
    # vídeos em pé primeiro (cortam melhor para 9:16), depois os deitados
    random.shuffle(candidatos)
    candidatos.sort(key=lambda h: not (h["videos"].get("large", {}).get("height", 0)
                                       > h["videos"].get("large", {}).get("width", 1)))
    for h in candidatos:
        opcoes = [v for k, v in h["videos"].items() if v.get("url") and v.get("height", 0) >= 720]
        if not opcoes:
            continue
        arq = min(opcoes, key=lambda v: abs(v["height"] - 1920) if v["height"] > v["width"] else abs(v["height"] - 1080))
        return _baixar(arq["url"], pasta_cache / f"pixabay_{h['id']}.mp4"), h["id"], h.get("pageURL")
    return None


def buscar_clipe(busca, pasta_cache, chave, usados=()):
    """Baixa um clipe vertical do Pexels (uso livre). Devolve o caminho ou None."""
    if not chave:
        return None
    pasta_cache = Path(pasta_cache)
    pasta_cache.mkdir(parents=True, exist_ok=True)
    url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
        {"query": busca, "orientation": "portrait", "size": "medium", "per_page": 15})
    req = urllib.request.Request(url, headers={"Authorization": chave, "User-Agent": "fabrica-shorts"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            videos = json.load(r).get("videos", [])
    except Exception:
        return None
    candidatos = [v for v in videos if v["id"] not in usados and v.get("duration", 0) >= 5]
    random.shuffle(candidatos)
    for v in candidatos:
        arquivos = [f for f in v["video_files"] if f.get("height") and f.get("width")
                    and f["height"] > f["width"] and 1280 <= f["height"] <= 2160]
        if not arquivos:
            continue
        arq = min(arquivos, key=lambda f: abs(f["height"] - 1920))
        destino = pasta_cache / f"pexels_{v['id']}.mp4"
        if not destino.exists():
            req = urllib.request.Request(arq["link"], headers={"User-Agent": "fabrica-shorts"})
            with urllib.request.urlopen(req, timeout=120) as r, open(destino, "wb") as f:
                f.write(r.read())
        return destino, v["id"], v.get("url")
    return None
