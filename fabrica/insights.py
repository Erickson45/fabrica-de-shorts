"""Insights: números dos canais no YouTube (inscritos, views, Shorts) e histórico diário.

Usa os mesmos acessos do envio (escopo de leitura). Gasta pouquíssima cota (~3 unidades por canal).
Cada coleta grava a "foto do dia" em insights/historico.json, para mostrar o crescimento com o tempo.
"""
import json
import re
from datetime import date, datetime
from pathlib import Path

from . import youtube

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "insights"
ORDEM = ["escolha_caminho", "fatos_sombrios", "so_1_acerta", "contos_60s"]


def _duracao_seg(iso):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def _canal(canal_id):
    from googleapiclient.discovery import build
    creds, _ = youtube._creds(canal_id)
    if not creds:
        return None
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    c = yt.channels().list(part="snippet,statistics,contentDetails", mine=True).execute()["items"][0]
    uploads = c["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while len(ids) < 200:
        r = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50, pageToken=token).execute()
        ids += [i["contentDetails"]["videoId"] for i in r.get("items", [])]
        token = r.get("nextPageToken")
        if not token:
            break
    videos = []
    for i in range(0, len(ids), 50):
        r = yt.videos().list(part="snippet,statistics,status,contentDetails", id=",".join(ids[i:i + 50])).execute()
        for v in r.get("items", []):
            if v["status"].get("privacyStatus") != "public":
                continue  # só o que o público vê (os vídeos antigos privados ficam de fora)
            st = v.get("statistics", {})
            publicado = v["snippet"]["publishedAt"]
            dias = max(1, (datetime.now().astimezone() - datetime.fromisoformat(publicado.replace("Z", "+00:00"))).days)
            views = int(st.get("viewCount", 0))
            videos.append({
                "id": v["id"], "titulo": v["snippet"]["title"], "publicado": publicado,
                "views": views, "likes": int(st.get("likeCount", 0)), "comentarios": int(st.get("commentCount", 0)),
                "duracao": _duracao_seg(v["contentDetails"].get("duration")),
                "thumb": v["snippet"]["thumbnails"].get("medium", v["snippet"]["thumbnails"].get("default", {})).get("url"),
                "views_dia": round(views / dias, 1),
            })
    s = c["statistics"]
    return {
        "canal": canal_id, "youtube_id": c["id"], "titulo": c["snippet"]["title"],
        "handle": c["snippet"].get("customUrl", ""),
        "inscritos": int(s.get("subscriberCount", 0)), "inscritos_ocultos": s.get("hiddenSubscriberCount", False),
        "views_canal": int(s.get("viewCount", 0)),
        "views_shorts": sum(v["views"] for v in videos), "shorts": len(videos),
        "videos": sorted(videos, key=lambda v: v["views"], reverse=True),
    }


def coletar():
    PASTA.mkdir(exist_ok=True)
    canais, erros = [], []
    for cid in ORDEM:
        try:
            dados = _canal(cid)
            if dados:
                canais.append(dados)
        except Exception as e:
            erros.append(f"{cid}: {e}")
    hoje = date.today().isoformat()
    historico = _ler("historico.json", {})
    historico[hoje] = {c["canal"]: {"inscritos": c["inscritos"], "views": c["views_shorts"], "shorts": c["shorts"]}
                       for c in canais}
    _gravar("historico.json", historico)
    resultado = {"atualizado_em": datetime.now().isoformat(timespec="seconds"), "canais": canais, "erros": erros}
    _gravar("ultimo.json", resultado)
    return resultado


def ultimo():
    return _ler("ultimo.json", None)


def historico():
    return _ler("historico.json", {})


def _ler(nome, padrao):
    arq = PASTA / nome
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else padrao


def _gravar(nome, dados):
    (PASTA / nome).write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
