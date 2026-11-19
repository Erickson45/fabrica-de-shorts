"""Painel da Fábrica de Shorts: gerar, revisar, assistir e aprovar.

Rodar:  .venv\\Scripts\\python painel.py   ->  http://localhost:5050
"""
import json
import random
import re
import shutil
import threading
import traceback
import unicodedata
import urllib.request
from collections import deque
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, url_for

from fabrica import importador, insights, youtube
from fabrica import roteiro as mod_roteiro
from fabrica.produzir import PASTA_SAIDA, RAIZ, carregar_canal, escrever_roteiro, pacote_youtube, produzir

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

ORDEM_CANAIS = ["escolha_caminho", "fatos_sombrios", "so_1_acerta", "contos_60s"]
VOZES = [
    {"id": "pm_alex", "nome": "Alex", "desc": "masculina, grave"},
    {"id": "pm_santa", "nome": "Santa", "desc": "masculina, calorosa"},
    {"id": "pf_dora", "nome": "Dora", "desc": "feminina"},
]

# ------------------------------------------------------------------ fila de produção
fila = deque()
estado = {"rodando": False, "atual": None, "log": [], "erro": None, "feitos": 0}
_tem_trabalho = threading.Event()


def _trabalhador():
    while True:
        _tem_trabalho.wait()
        while fila:
            job = fila.popleft()
            estado.update(rodando=True, atual=job, log=[], erro=None)
            log = estado["log"].append
            try:
                if job["tipo"] == "roteiro":
                    escrever_roteiro(job["canal"], job.get("tema"), log=log)
                elif job["tipo"] == "enviar":
                    pasta = Path(job["pasta"])
                    info = json.loads((pasta / "info.json").read_text(encoding="utf-8"))
                    canal = carregar_canal(job["canal"])
                    if not info.get("youtube"):  # sem pacote ainda: gera antes de enviar
                        r = json.loads((pasta / "roteiro.json").read_text(encoding="utf-8"))
                        log("Gerando pacote YouTube…")
                        info["youtube"] = pacote_youtube(canal, r, log)
                        (pasta / "info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
                    youtube.enviar(canal, pasta, log=log)
                elif job["tipo"] == "pacote":
                    pasta = Path(job["pasta"])
                    info = json.loads((pasta / "info.json").read_text(encoding="utf-8"))
                    r = json.loads((pasta / "roteiro.json").read_text(encoding="utf-8"))
                    log("Gerando pacote YouTube…")
                    info["youtube"] = pacote_youtube(carregar_canal(job["canal"]), r, log)
                    (pasta / "info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
                    log("Pacote pronto.")
                elif job["tipo"] == "montar":
                    produzir(job["canal"], log=log, voz_id=job.get("voz"), pasta=job["pasta"])
                else:
                    produzir(job["canal"], job.get("tema"), log=log, voz_id=job.get("voz"))
                estado["feitos"] += 1
            except Exception as e:
                estado["erro"] = str(e)
                log("ERRO: " + str(e))
                traceback.print_exc()
        estado.update(rodando=False, atual=None)
        _tem_trabalho.clear()


threading.Thread(target=_trabalhador, daemon=True).start()


def _enfileirar(job):
    fila.append(job)
    _tem_trabalho.set()


# ------------------------------------------------------------------ dados
def canais():
    lista = []
    for cid in ORDEM_CANAIS:
        if (RAIZ / "canais" / f"{cid}.json").exists():
            lista.append(carregar_canal(cid))
    return lista


def itens(canal_id=None):
    saida = []
    for info_arq in PASTA_SAIDA.glob("*/*/info.json"):
        info = json.loads(info_arq.read_text(encoding="utf-8"))
        if canal_id and info.get("canal") != canal_id:
            continue
        info["id"] = f"{info_arq.parent.parent.name}/{info_arq.parent.name}"
        info["tem_video"] = (info_arq.parent / "video.mp4").exists()
        r = info_arq.parent / "roteiro.json"
        info["roteiro"] = json.loads(r.read_text(encoding="utf-8")) if r.exists() else {}
        saida.append(info)
    return sorted(saida, key=lambda i: i["criado_em"], reverse=True)


def contagens():
    c = {}
    for i in itens():
        d = c.setdefault(i.get("canal"), {"total": 0, "aprovado": 0, "roteiro": 0})
        d["total"] += 1
        if i.get("status") in d:
            d[i["status"]] += 1
    return c


def checagens():
    cfg = json.loads((RAIZ / "config.json").read_text(encoding="utf-8")) if (RAIZ / "config.json").exists() else {}
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as r:
            modelos = [m["name"] for m in json.load(r).get("models", [])]
    except Exception:
        modelos = []
    voz = (RAIZ / "modelos" / "voices-v1.0.bin").exists() and (RAIZ / "modelos" / "kokoro-v1.0.onnx").exists()
    ia = any(m in modelos for m in ("gemma3:12b", "qwen2.5:14b", "qwen2.5:7b"))
    try:
        from fabrica.montagem import ffmpeg
        tem_ffmpeg = bool(ffmpeg())
    except Exception:
        tem_ffmpeg = False
    google = any(RAIZ.glob("client_secret*.json"))
    conectados = sum(1 for c in ORDEM_CANAIS if youtube.status(c)["conectado"])
    ch = {"ia": ia, "modelo": mod_roteiro.modelo() if ia else "", "voz": voz, "ffmpeg": tem_ffmpeg,
          "banco": bool(cfg.get("pexels_chave") or cfg.get("pixabay_chave")),
          "google": google, "conectados": conectados}
    ch["pronto"] = all((ia, voz, tem_ffmpeg, ch["banco"], google, conectados))
    return ch


# ------------------------------------------------------------------ páginas
@app.route("/")
def index():
    lista = canais()
    canal_id = request.args.get("canal") or lista[0]["id"]
    canal = next((c for c in lista if c["id"] == canal_id), lista[0])
    filtro = request.args.get("status", "todos")
    todos = itens(canal["id"])
    roteiros = [i for i in todos if i.get("status") == "roteiro"]
    videos = [i for i in todos if i.get("tem_video") and (filtro == "todos" or i.get("status") == filtro)]
    por_status = {s: sum(1 for i in todos if i.get("status") == s and i.get("tem_video"))
                  for s in ("rascunho", "aprovado", "enviado", "descartado")}
    banco = None
    if canal.get("banco"):
        total_banco = len(json.loads((RAIZ / "bancos" / f"{canal['banco']}.json").read_text(encoding="utf-8")))
        usados_arq = RAIZ / "bancos" / "usados.json"
        usados = json.loads(usados_arq.read_text(encoding="utf-8")).get(canal["banco"], []) if usados_arq.exists() else []
        banco = {"total": total_banco, "restantes": max(0, total_banco - len(usados)),
                 "nome": "perguntas" if canal["banco"] == "quiz" else "fatos",
                 "precisa_contato": canal["banco"] == "fatos" and importador.precisa_contato()}
    yt = youtube.status(canal["id"])
    return render_template("painel.html", canais=lista, canal=canal, videos=videos, roteiros=roteiros, banco=banco, yt=yt,
                           filtro=filtro, por_status=por_status, contagens=contagens(), ch=checagens(),
                           estado=estado, fila=list(fila), vozes=VOZES)


@app.post("/gerar")
def gerar():
    f = request.form
    canal_id = f.get("canal", ORDEM_CANAIS[0])
    canal = carregar_canal(canal_id)
    tema = f.get("tema", "").strip()
    categoria = f.get("categoria", "")
    quantidade = max(1, min(5, int(f.get("quantidade", "1") or 1)))
    revisar = f.get("revisar") == "on"
    voz = f.get("voz") or None
    opcoes = canal["categorias"].get(categoria) or [t for l in canal["categorias"].values() for t in l]
    sorteio = random.sample(opcoes, min(quantidade, len(opcoes)))
    for i in range(quantidade):
        t = tema or sorteio[i % len(sorteio)]
        _enfileirar({"tipo": "roteiro" if revisar else "completo", "canal": canal_id, "tema": t, "voz": voz,
                     "rotulo": t})
    return redirect(url_for("index", canal=canal_id))


@app.post("/cancelar")
def cancelar():
    fila.clear()
    return redirect(request.referrer or url_for("index"))


@app.get("/trabalho")
def ver_trabalho():
    return jsonify({**estado, "fila": len(fila)})


def _pasta(vid):
    pasta = (PASTA_SAIDA / vid).resolve()
    if PASTA_SAIDA.resolve() not in pasta.parents or not (pasta / "info.json").exists():
        abort(404)
    return pasta


def _info(pasta):
    return json.loads((pasta / "info.json").read_text(encoding="utf-8"))


def _gravar_info(pasta, info):
    (pasta / "info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")


@app.post("/roteiro/<path:vid>")
def salvar_roteiro(vid):
    """Salva as edições do roteiro e, se pedido, manda montar o vídeo."""
    pasta = _pasta(vid)
    r = json.loads((pasta / "roteiro.json").read_text(encoding="utf-8"))
    f = request.form
    r["titulo"] = f.get("titulo", r["titulo"]).strip() or r["titulo"]
    for k in ("opcao_a", "opcao_b", "ruim"):
        if f.get(k):
            r[k] = f[k].strip()
    for i, c in enumerate(r["cenas"]):
        for k in ("texto", "titulo", "explicacao", "correta"):
            if f.get(f"{k}_{i}") is not None and f.get(f"{k}_{i}").strip():
                c[k] = f[f"{k}_{i}"].strip()
        if c.get("opcoes") is not None:
            c["opcoes"] = [f.get(f"opcao_{i}_{j}", o).strip() or o for j, o in enumerate(c["opcoes"])]
    (pasta / "roteiro.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    info = _info(pasta)
    info["titulo"] = r["titulo"]
    if f.get("acao") == "descartar":
        info["status"] = "descartado"
    elif f.get("acao") == "montar":
        info["status"] = "montando"
        _enfileirar({"tipo": "montar", "canal": info["canal"], "pasta": str(pasta), "voz": f.get("voz") or None,
                     "rotulo": r["titulo"]})
    _gravar_info(pasta, info)
    return redirect(url_for("index", canal=info["canal"]))


@app.post("/pacote/<path:vid>")
def gerar_pacote(vid):
    pasta = _pasta(vid)
    info = _info(pasta)
    _enfileirar({"tipo": "pacote", "canal": info["canal"], "pasta": str(pasta), "rotulo": "Pacote: " + info["titulo"]})
    return redirect(request.referrer or url_for("index", canal=info["canal"]))


@app.get("/video/<path:vid>")
def ver_video(vid):
    return send_file(_pasta(vid) / "video.mp4", mimetype="video/mp4", conditional=True)


@app.get("/baixar/<path:vid>")
def baixar(vid):
    pasta = _pasta(vid)
    titulo = unicodedata.normalize("NFKD", _info(pasta)["titulo"]).encode("ascii", "ignore").decode()
    nome = re.sub(r"[^A-Za-z0-9]+", "-", titulo).strip("-").lower() or "short"
    return send_file(pasta / "video.mp4", as_attachment=True, download_name=f"{nome}.mp4")


@app.post("/status/<path:vid>")
def mudar_status(vid):
    pasta = _pasta(vid)
    info = _info(pasta)
    novo = request.form.get("status")
    if novo in ("rascunho", "aprovado", "descartado") and info.get("status") != "enviado":
        info["status"] = novo
    _gravar_info(pasta, info)
    # aprovou e o canal está conectado: já vai para a fila de envio do YouTube
    if novo == "aprovado" and youtube.status(info["canal"])["conectado"] and not info.get("enviado"):
        _enfileirar({"tipo": "enviar", "canal": info["canal"], "pasta": str(pasta), "rotulo": "Enviando: " + info["titulo"]})
    return redirect(request.referrer or url_for("index", canal=info["canal"]))


@app.post("/enviar/<path:vid>")
def enviar_video(vid):
    pasta = _pasta(vid)
    info = _info(pasta)
    if not info.get("enviado"):
        _enfileirar({"tipo": "enviar", "canal": info["canal"], "pasta": str(pasta), "rotulo": "Enviando: " + info["titulo"]})
    return redirect(request.referrer or url_for("index", canal=info["canal"]))


@app.post("/youtube/conectar/<canal_id>")
def conectar_youtube(canal_id):
    canal = carregar_canal(canal_id)
    youtube.conectar(canal_id, (canal.get("youtube") or {}).get("id"))
    return redirect(url_for("index", canal=canal_id))


@app.post("/youtube/desconectar/<canal_id>")
def desconectar_youtube(canal_id):
    youtube.desconectar(canal_id)
    return redirect(url_for("index", canal=canal_id))


@app.get("/youtube/conexao")
def ver_conexao():
    return jsonify(youtube.conexao)


@app.get("/insights")
def ver_insights():
    from datetime import date, datetime as dt
    dados = insights.ultimo()
    velho = not dados or (dt.now() - dt.fromisoformat(dados["atualizado_em"])).total_seconds() > 1800
    if velho:
        try:
            dados = insights.coletar()
        except Exception as e:
            dados = dados or {"atualizado_em": dt.now().isoformat(timespec="seconds"), "canais": [], "erros": [str(e)]}
    hist = insights.historico()
    hoje = date.today().isoformat()
    anteriores = sorted(d for d in hist if d < hoje)
    base = hist.get(anteriores[-1], {}) if anteriores else {}
    cores = {c["id"]: c for c in canais()}
    for c in dados["canais"]:
        info = cores.get(c["canal"], {})
        c["cor"], c["icone"], c["formato_nome"] = info.get("cor", "#888"), info.get("icone", ""), info.get("nome", "")
        antes = base.get(c["canal"])
        c["delta_inscritos"] = c["inscritos"] - antes["inscritos"] if antes else None
        c["delta_views"] = c["views_shorts"] - antes["views"] if antes else None
    tot = {k: sum(c[k] for c in dados["canais"]) for k in ("inscritos", "views_shorts", "shorts")}
    tot["media"] = round(tot["views_shorts"] / tot["shorts"]) if tot["shorts"] else 0
    tot["delta_inscritos"] = sum(c["delta_inscritos"] or 0 for c in dados["canais"]) if base else None
    tot["delta_views"] = sum(c["delta_views"] or 0 for c in dados["canais"]) if base else None
    videos = sorted(({**v, "canal": c["titulo"], "cor": c["cor"]} for c in dados["canais"] for v in c["videos"]),
                    key=lambda v: v["views"], reverse=True)
    serie = {"datas": sorted(hist), "canais": [{"id": c["canal"], "nome": c["titulo"], "cor": c["cor"],
                                                 "valores": [hist[d].get(c["canal"], {}).get("inscritos") for d in sorted(hist)]}
                                                for c in dados["canais"]]}
    return render_template("insights.html", dados=dados, tot=tot, videos=videos, serie=serie,
                           base_data=anteriores[-1] if anteriores else None)


@app.post("/insights/atualizar")
def atualizar_insights():
    try:
        insights.coletar()
    except Exception:
        traceback.print_exc()
    return redirect(url_for("ver_insights"))


@app.post("/importar")
def importar():
    fonte = request.form.get("fonte")
    if fonte in ("quiz", "fatos"):
        # pausa sozinho enquanto um vídeo estiver sendo produzido (os dois usam a IA e a CPU)
        importador.iniciar(fonte, meta=int(request.form.get("meta", 3000)),
                           ocupado=lambda: estado["rodando"] or bool(fila))
    return redirect(request.referrer or url_for("index"))


@app.post("/importar/parar")
def parar_importacao():
    importador.parar()
    return redirect(request.referrer or url_for("index"))


@app.get("/importacao")
def ver_importacao():
    return jsonify({**importador.estado, "contagem": importador.contagem()})


@app.post("/config")
def salvar_config():
    arq = RAIZ / "config.json"
    cfg = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}
    for campo in ("pexels_chave", "pixabay_chave", "contato_wikipedia"):
        chave = request.form.get(campo, "").strip()
        if chave:
            cfg[campo] = chave
    arq.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return redirect(request.referrer or url_for("index"))


if __name__ == "__main__":
    # roteiros que estavam "montando" quando o painel fechou voltam para revisão
    for arq in PASTA_SAIDA.glob("*/*/info.json"):
        info = json.loads(arq.read_text(encoding="utf-8"))
        if info.get("status") == "montando" and not (arq.parent / "video.mp4").exists():
            info["status"] = "roteiro"
            arq.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        shutil.rmtree(arq.parent / "tmp", ignore_errors=True)
    app.run(port=5050, debug=False, threaded=True)
