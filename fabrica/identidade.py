"""Identidade visual dos canais: foto de perfil (800x800) e banner (2560x1440) para o YouTube."""
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "identidade"
FORTE = "C:/Windows/Fonts/ariblk.ttf"
MEDIA = "C:/Windows/Fonts/arialbd.ttf"


def _hex(c, a=255):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def _mistura(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)


def _fundo(w, h, cor):
    """Fundo escuro com brilho radial da cor do canal e granulado leve."""
    base = Image.new("RGBA", (w, h), (14, 12, 10, 255))
    brilho = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(brilho)
    cx, cy, r = w * 0.5, h * 0.5, max(w, h) * 0.55
    for i in range(60, 0, -1):
        k = i / 60
        d.ellipse((cx - r * k, cy - r * k, cx + r * k, cy + r * k), fill=_hex(cor, int(70 * (1 - k) ** 1.6)))
    base = Image.alpha_composite(base, brilho.filter(ImageFilter.GaussianBlur(w // 30)))
    vinheta = Image.new("L", (w, h), 0)
    ImageDraw.Draw(vinheta).ellipse((-w * 0.25, -h * 0.25, w * 1.25, h * 1.25), fill=255)
    vinheta = vinheta.filter(ImageFilter.GaussianBlur(w // 8))
    escuro = Image.new("RGBA", (w, h), (0, 0, 0, 200))
    return Image.composite(base, Image.alpha_composite(base, escuro), vinheta)


def _icone(d, nome, cx, cy, s, cor, largura):
    """Desenha o ícone do canal (os mesmos do painel), centralizado em (cx, cy) com tamanho s."""
    p = lambda x, y: (cx + (x - 8) * s / 16, cy + (y - 8) * s / 16)
    lw = int(largura)
    if nome == "split":  # bifurcação
        d.line([p(8, 14.5), p(8, 9)], fill=cor, width=lw)
        d.line([p(8, 9), p(3.5, 4.5)], fill=cor, width=lw)
        d.line([p(8, 9), p(12.5, 4.5)], fill=cor, width=lw)
        d.line([p(2.5, 6.5), p(2.5, 2.5), p(6.5, 2.5)], fill=cor, width=lw, joint="curve")
        d.line([p(13.5, 6.5), p(13.5, 2.5), p(9.5, 2.5)], fill=cor, width=lw, joint="curve")
    elif nome == "skull":
        d.ellipse([p(2.5, 1.5), p(13.5, 12)], outline=cor, width=lw)
        d.rectangle([p(5, 10.5), p(11, 14.5)], outline=cor, width=lw)
        r = s / 16 * 1.4
        for x in (5.8, 10.2):
            c = p(x, 7.2)
            d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=cor)
        d.line([p(7, 14.5), p(7, 12.3)], fill=cor, width=max(2, lw // 2))
        d.line([p(9, 14.5), p(9, 12.3)], fill=cor, width=max(2, lw // 2))
    elif nome == "question":
        d.ellipse([p(1.5, 1.5), p(14.5, 14.5)], outline=cor, width=lw)
        d.arc([p(5.2, 3.6), p(10.8, 9.2)], 180, 400, fill=cor, width=lw)
        d.line([p(9.4, 8.6), p(8, 9.6), p(8, 10.6)], fill=cor, width=lw, joint="curve")
        r = s / 16 * 0.9
        c = p(8, 12.4)
        d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=cor)
    else:  # livro
        d.line([p(8, 3.5), p(8, 14)], fill=cor, width=lw)
        d.polygon([p(8, 3.5), p(2, 2.5), p(2, 13), p(8, 14)], outline=cor, width=lw)
        d.polygon([p(8, 3.5), p(14, 2.5), p(14, 13), p(8, 14)], outline=cor, width=lw)
        for y in (6, 8.5):
            d.line([p(3.8, y - 0.6), p(6.4, y)], fill=cor, width=max(2, lw // 2))
            d.line([p(9.6, y), p(12.2, y - 0.6)], fill=cor, width=max(2, lw // 2))


def avatar(canal, destino):
    w = 800
    img = _fundo(w, w, canal["cor"])
    d = ImageDraw.Draw(img)
    # placa central com degradê da cor do canal
    placa = Image.new("RGBA", (w, w), (0, 0, 0, 0))
    pd = ImageDraw.Draw(placa)
    claro, escuro = _hex(canal["cor"]), _mistura(_hex(canal["cor"]), (0, 0, 0), 0.55)
    for i in range(420):
        t = i / 419
        pd.line([(190, 190 + i), (610, 190 + i)], fill=_mistura(claro, escuro, t))
    mascara = Image.new("L", (w, w), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((190, 190, 610, 610), radius=110, fill=255)
    sombra = Image.new("RGBA", (w, w), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle((200, 230, 600, 640), radius=110, fill=_hex(canal["cor"], 150))
    img = Image.alpha_composite(img, sombra.filter(ImageFilter.GaussianBlur(40)))
    img.paste(placa, (0, 0), mascara)
    d = ImageDraw.Draw(img)
    _icone(d, canal["icone"], w / 2, w / 2, 250, (255, 255, 255, 255), 22)
    img.convert("RGB").save(destino, quality=95)


def banner(canal, slogan, destino):
    """2560x1440; o texto fica na área segura central (1546x423), que aparece em todos os aparelhos."""
    W, H = 2560, 1440
    img = _fundo(W, H, canal["cor"])
    d = ImageDraw.Draw(img)
    # linhas finas decorativas (ondas de radar) atrás do texto
    for i in range(1, 9):
        r = 180 * i
        d.ellipse((W / 2 - r * 1.8, H / 2 - r, W / 2 + r * 1.8, H / 2 + r), outline=_hex(canal["cor"], max(8, 60 - i * 6)), width=3)
    # ícone + nome
    nome = ((canal.get("youtube") or {}).get("nome") or canal["nome"]).upper()  # nome real no YouTube
    f = ImageFont.truetype(FORTE, 150)
    while d.textlength(nome, font=f) > 1150 and f.size > 70:
        f = ImageFont.truetype(FORTE, f.size - 6)
    larg_nome = d.textlength(nome, font=f)
    tam_icone = 190
    total = tam_icone + 50 + larg_nome
    x0 = (W - total) / 2
    cy = H / 2 - 40
    placa = (x0, cy - tam_icone / 2, x0 + tam_icone, cy + tam_icone / 2)
    d.rounded_rectangle(placa, radius=52, fill=_hex(canal["cor"]))
    _icone(d, canal["icone"], x0 + tam_icone / 2, cy, 120, (255, 255, 255, 255), 11)
    d.text((x0 + tam_icone + 50, cy - f.size * 0.62), nome, font=f, fill=(255, 255, 255, 255))
    fs = ImageFont.truetype(MEDIA, 54)
    ws = d.textlength(slogan, font=fs)
    d.text(((W - ws) / 2, cy + tam_icone / 2 + 40), slogan, font=fs, fill=_hex(canal["cor"]))
    img.convert("RGB").save(destino, quality=92)


SLOGANS = {
    "escolha_caminho": "Duas portas. Uma escolha. Qual seria a sua?",
    "fatos_sombrios": "Histórias reais que parecem mentira",
    "so_1_acerta": "Três perguntas. Três segundos. Você é do 1%?",
    "contos_60s": "Contos de terror originais em um minuto",
}


def gerar_todos():
    SAIDA.mkdir(exist_ok=True)
    feitos = []
    for arq in sorted((RAIZ / "canais").glob("*.json")):
        canal = json.loads(arq.read_text(encoding="utf-8"))
        avatar(canal, SAIDA / f"{canal['id']}_foto.jpg")
        banner(canal, SLOGANS.get(canal["id"], ""), SAIDA / f"{canal['id']}_banner.jpg")
        feitos.append(canal["id"])
    return feitos


if __name__ == "__main__":
    print(gerar_todos())
