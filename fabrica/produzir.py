"""Produz um Short completo: roteiro -> voz -> visual -> trilha -> montagem.

Cada formato de canal (escolha, fatos, quiz, conto) tem seu próprio "planejador de cenas",
que decide o que é narrado e quais camadas aparecem por cima do vídeo.
"""
import json
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

from . import montagem, roteiro, som, visual, voz

RAIZ = Path(__file__).resolve().parent.parent
PASTA_SAIDA = RAIZ / "saida"
PASTA_CACHE = RAIZ / "cache" / "pexels"
ROMANOS = ["I", "II", "III", "IV", "V"]
NOMES_ATOS = {"inicio": "o começo", "meio": "algo errado", "climax": "o pior momento", "final": "a verdade"}


def carregar_canal(canal_id):
    return json.loads((RAIZ / "canais" / f"{canal_id}.json").read_text(encoding="utf-8"))


def config():
    arq = RAIZ / "config.json"
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}


class Cenas:
    """Monta a lista de cenas: narração + camadas (PNG com início/fim) + busca do fundo."""

    def __init__(self, tmp, canal, voz_id):
        self.tmp, self.canal, self.voz = tmp, canal, voz_id
        self.vis = canal["visual"]
        self.lista = []
        self._n = 0

    def png(self, nome):
        self._n += 1
        return self.tmp / f"{nome}_{self._n}.png"

    def narrada(self, tipo, texto, busca, extras=(), legenda=True, legenda_y=1180):
        audio = self.tmp / f"voz_{len(self.lista)}.wav"
        dur = voz.falar(texto, audio, self.voz, self.canal["velocidade"])
        camadas = []
        for png, ini, fim in extras:
            camadas.append((png, ini, dur if fim is None else fim, "sobe"))
        if legenda:
            for txt, ini, fim in visual.blocos_legenda(texto, dur):
                p = self.png("leg")
                visual.legenda(txt, p, self.vis["cor_destaque"], y=legenda_y)
                camadas.append((p, ini, fim, "sobe"))
        self.lista.append({"tipo": tipo, "dur": dur, "audio": audio, "camadas": camadas, "busca": busca})
        return dur

    def contagem(self, fundo_camadas=(), y=1250):
        camadas = [(p, 0, 3) for p in fundo_camadas]
        for k, n in enumerate((3, 2, 1)):
            p = self.png("num")
            visual.numero(n, p, self.vis["cor_destaque"], y=y)
            camadas.append((p, k, k + 1))
        self.lista.append({"tipo": "contagem", "dur": 3.0, "audio": None, "tique": True,
                           "camadas": camadas, "busca": self.lista[-1]["busca"] if self.lista else ""})

    def global_(self, png, de_tipo=None):
        """Camada que vale em todas as cenas (ex.: faixas de cinema)."""
        for c in self.lista:
            c["camadas"].insert(0, (png, 0, c["dur"]))


# ------------------------------------------------------------------ planejadores por formato
def plano_escolha(r, cs):
    vis = cs.vis
    ruim = r["ruim"]
    boa = "B" if ruim == "A" else "A"
    nome = {"A": r["opcao_a"], "B": r["opcao_b"]}
    cor = {"A": vis["cor_a"], "B": vis["cor_b"]}
    cart = cs.png("cartoes")
    visual.cartoes(r["opcao_a"], r["opcao_b"], vis["cor_a"], vis["cor_b"], cart)
    for c in r["cenas"]:
        extras = []
        if c["tipo"] == "gancho":
            p = cs.png("abertura")
            visual.chamada(r["titulo"], p, "#FFFFFF")
            extras.append((p, 0, 3.2))
        elif c["tipo"] == "escolha":
            extras.append((cart, 0, None))
        elif c["tipo"] in ("ruim", "bom"):
            letra = ruim if c["tipo"] == "ruim" else boa
            p = cs.png("faixa")
            visual.faixa(f"Caminho {letra} · {nome[letra]}", cor[letra], p)
            extras.append((p, 0, None))
        elif c["tipo"] == "final":
            p = cs.png("chamada")
            visual.chamada("Comenta: A ou B?", p, vis["cor_destaque"])
            extras.append((p, 0, None))
        cs.narrada(c["tipo"], c["texto"], c.get("busca", ""), extras)
        if c["tipo"] == "escolha":
            cs.contagem([cart])


def plano_fatos(r, cs):
    vis = cs.vis
    n = 0
    for c in r["cenas"]:
        extras = []
        if c["tipo"] == "gancho":
            p = cs.png("abertura")
            visual.chamada(r["titulo"], p, "#FFFFFF")
            extras.append((p, 0, 3.4))
        elif c["tipo"] == "fato":
            n += 1
            p = cs.png("faixa")
            visual.faixa(f"Fato {n} de 3 · {c.get('titulo', '')}", vis["cor_a"], p)
            extras.append((p, 0, None))
        elif c["tipo"] == "final":
            p = cs.png("chamada")
            visual.chamada("Qual foi o pior?", p, vis["cor_destaque"])
            extras.append((p, 0, None))
        cs.narrada(c["tipo"], c["texto"], c.get("busca", ""), extras)


def plano_quiz(r, cs):
    vis = cs.vis
    n = 0
    for c in r["cenas"]:
        if c["tipo"] != "pergunta":
            extras = []
            p = cs.png("chamada")
            visual.chamada(r["titulo"] if c["tipo"] == "gancho" else "Quantas você acertou?", p, vis["cor_destaque"])
            extras.append((p, 0, None))
            cs.narrada(c["tipo"], c["texto"], c.get("busca", ""), extras)
            continue
        n += 1
        ops = [str(o) for o in c["opcoes"]]
        certa = "ABC".index(c["correta"])
        faixa = cs.png("faixa")
        visual.faixa(f"Pergunta {n} de 3", vis["cores"][1], faixa, y=210)
        cart = cs.png("cartoes")
        visual.opcoes_cartoes(ops, vis["cores"], cart, y0=640)
        cart_ok = cs.png("certa")
        visual.opcoes_cartoes(ops, vis["cores"], cart_ok, y0=640, certa=certa, cor_certa=vis["cor_certa"])
        p_txt = cs.png("pergunta")
        visual.chamada(c["texto"], p_txt, "#FFFFFF", y=330, tam=60)
        fala = f"{c['texto']} A: {ops[0]}. B: {ops[1]}. Ou C: {ops[2]}?"
        cs.narrada("pergunta", fala, c.get("busca", ""), [(faixa, 0, None), (cart, 0, None)], legenda=False)
        cs.lista[-1]["camadas"].append((p_txt, 0, cs.lista[-1]["dur"], "sobe"))
        cs.contagem([faixa, cart], y=1500)
        resposta = f"Letra {c['correta']}: {ops[certa]}. {c['explicacao']}"
        cs.narrada("resposta", resposta, c.get("busca", ""), [(faixa, 0, None), (cart_ok, 0, None)], legenda_y=1360)


def plano_conto(r, cs):
    vis = cs.vis
    for i, c in enumerate(r["cenas"]):
        extras = []
        if i == 0:
            p = cs.png("abertura")
            visual.chamada(r["titulo"], p, "#FFFFFF")
            extras.append((p, 0, 3.4))
        else:
            p = cs.png("capitulo")
            visual.capitulo(ROMANOS[i], NOMES_ATOS.get(c["tipo"], ""), p, vis["cor_destaque"])
            extras.append((p, 0, None))
        cs.narrada(c["tipo"], c["texto"], c.get("busca", ""), extras)
    # chamada final por cima dos últimos segundos
    p = cs.png("chamada")
    visual.chamada("Segue pra mais contos", p, vis["cor_a"])
    ultima = cs.lista[-1]
    ultima["camadas"].append((p, max(0, ultima["dur"] - 2.6), ultima["dur"], "sobe"))
    faixas = cs.png("cinema")
    visual.faixas_cinema(faixas)
    cs.global_(faixas)


PLANOS = {"escolha": plano_escolha, "fatos": plano_fatos, "quiz": plano_quiz, "conto": plano_conto}


# ------------------------------------------------------------------ produção
def _nova_pasta(canal_id):
    pasta = PASTA_SAIDA / canal_id / datetime.now().strftime("%Y%m%d-%H%M%S")
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _salvar_info(pasta, info):
    (pasta / "info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")


def pacote_youtube(canal, r, log=print):
    """Título com gancho, descrição que puxa comentário, hashtags e tags, prontos para colar no YouTube."""
    resumo = "\n".join(f"- {c['tipo']}: {c['texto']}" for c in r["cenas"])
    prompt = (
        f"Você cuida do YouTube Shorts do canal \"{canal['nome']}\" ({canal['descricao']}).\n"
        f"Roteiro do vídeo:\n{resumo}\n\n"
        "Crie o pacote de publicação em português do Brasil:\n"
        "- titulo: até 60 caracteres, desperta curiosidade e faz a pessoa querer assistir até o fim, "
        "SEM mentir e SEM entregar o final; pode usar 1 emoji no fim;\n"
        "- descricao: 2 frases curtas que aumentam a curiosidade, e na linha seguinte uma pergunta que faz a "
        "pessoa comentar;\n"
        "- hashtags: 3 a 5 hashtags em português, sem o símbolo #, sem espaços (ex.: historiadeterror);\n"
        "- tags: 8 a 12 palavras-chave de busca em português.\n"
        "Responda SOMENTE com JSON: {\"titulo\": \"\", \"descricao\": \"\", \"hashtags\": [], \"tags\": []}"
    )
    try:
        p = roteiro._ler(roteiro._pedir(prompt, temperatura=0.8))
        if not (isinstance(p.get("titulo"), str) and 8 <= len(p["titulo"]) <= 100 and p.get("descricao")):
            raise ValueError("pacote fora do padrão")
    except Exception as e:
        log(f"  pacote YouTube: usando o básico ({e})")
        p = {"titulo": r["titulo"], "descricao": r.get("descricao", ""), "hashtags": r.get("tags", []),
             "tags": r.get("tags", [])}
    hashtags = [re.sub(r"[^\wÀ-ú]", "", str(h).lower()) for h in (p.get("hashtags") or [])][:5]
    hashtags = [h for h in hashtags if h] + ["shorts"]
    partes = [p["descricao"].strip()]
    if r.get("creditos"):
        partes.append(r["creditos"])
    partes.append("Narração gerada por inteligência artificial." +
                  (" Conteúdo de ficção." if canal["formato"] in ("escolha", "conto") else ""))
    partes.append(" ".join("#" + h for h in hashtags))
    yt = canal.get("youtube") or {}
    return {
        "titulo": p["titulo"].strip().strip('"')[:100],
        "descricao": "\n\n".join(partes),
        "tags": [str(t).strip() for t in (p.get("tags") or []) if str(t).strip()][:15],
        "canal_handle": yt.get("handle"),
        "upload_url": f"https://studio.youtube.com/channel/{yt['id']}/videos/upload?d=ud" if yt.get("id") else None,
    }


def escrever_roteiro(canal_id, tema=None, log=print):
    """Só o roteiro: fica salvo para você revisar e editar antes de montar."""
    canal = carregar_canal(canal_id)
    pasta = _nova_pasta(canal_id)
    log("1/4 Escrevendo o roteiro…")
    r = roteiro.gerar(canal, tema, log=log)
    (pasta / "roteiro.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    _salvar_info(pasta, {"canal": canal_id, "titulo": r["titulo"], "descricao": r.get("descricao", ""),
                         "tags": r.get("tags", []), "status": "roteiro",
                         "criado_em": datetime.now().isoformat(timespec="seconds")})
    log(f"Roteiro pronto para revisar: “{r['titulo']}”")
    return pasta


def produzir(canal_id, tema=None, roteiro_pronto=None, log=print, voz_id=None, pasta=None):
    inicio = time.time()
    canal = carregar_canal(canal_id)
    vis = canal["visual"]
    cfg = config()
    chave_pexels, chave_pixabay = cfg.get("pexels_chave"), cfg.get("pixabay_chave")
    pasta = Path(pasta) if pasta else _nova_pasta(canal_id)
    tmp = pasta / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)

    # 1. roteiro
    log("1/4 Escrevendo o roteiro…")
    if roteiro_pronto is None and (pasta / "roteiro.json").exists():
        roteiro_pronto = json.loads((pasta / "roteiro.json").read_text(encoding="utf-8"))
    r = roteiro_pronto or roteiro.gerar(canal, tema, log=log)
    erro = roteiro.validar(r, canal)
    if erro and not erro.startswith(("curto", "longo")):
        raise RuntimeError(f"Roteiro com problema: {erro}")
    (pasta / "roteiro.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"  “{r['titulo']}”")

    # 2. narração + camadas
    log("2/4 Gravando a narração…")
    cs = Cenas(tmp, canal, voz_id or canal["voz"])
    PLANOS[canal["formato"]](r, cs)
    cenas = cs.lista

    # 3. fundos
    tem_banco = chave_pexels or chave_pixabay
    log("3/4 Buscando vídeos de fundo…" if tem_banco else "3/4 Sem banco de vídeos: usando fundo animado…")
    usados, creditos, anteriores = set(), [], []
    for c in cenas:
        clipes = []
        if c["tipo"] in ("contagem", "resposta") and anteriores:
            clipes = anteriores[-1:]  # contagem e resposta continuam no fundo da pergunta/escolha
        elif tem_banco:
            busca = visual.com_clima(c["busca"]) if canal.get("clima_escuro", True) else c["busca"]
            quantos = 2 if c["dur"] > 7 else 1  # cenas longas ganham 2 clipes: mais cortes, mais vida
            for _ in range(quantos):
                achado = (visual.buscar_clipe(busca, PASTA_CACHE, chave_pexels, usados)
                          or visual.buscar_clipe_pixabay(busca, PASTA_CACHE, chave_pixabay, usados)
                          or visual.buscar_clipe_pixabay(c["busca"], PASTA_CACHE, chave_pixabay, usados))
                if achado:
                    clipe, vid, url = achado
                    usados.add(vid)
                    creditos.append(url)
                    clipes.append(clipe)
        c["clipes"] = clipes
        anteriores = clipes or anteriores

    # 4. trilha, efeitos e montagem
    log("4/4 Compondo a trilha e montando o vídeo…")
    total, marcos = 0.0, []
    for c in cenas:
        c["inicio"] = total
        marcos.append((total, c["tipo"]))
        total += c["dur"]
    trilha_wav, fx_wav = tmp / "trilha.wav", tmp / "efeitos.wav"
    som.salvar(som.trilha(total + 0.5, marcos), trilha_wav)
    som.salvar(som.efeitos(total + 0.5, marcos), fx_wav)
    segmentos = []
    for i, c in enumerate(cenas):
        seg = tmp / f"seg_{i}.mp4"
        montagem.segmento(seg, c["dur"], c["camadas"], vis, clipes=c["clipes"], audio=c["audio"],
                          tique=c.get("tique", False), tipo=c["tipo"], inicio_global=c["inicio"], total=total)
        segmentos.append(seg)
    video = pasta / "video.mp4"
    duracao = montagem.juntar(segmentos, video, tmp, trilha_wav, fx_wav)

    hashtags = " ".join("#" + re.sub(r"\W+", "", t.lower()) for t in (r.get("tags") or [])[:5] if t) + " #shorts"
    creditos_video = "Vídeos de fundo: Pixabay." if creditos else ""
    descricao_yt = "\n\n".join(p for p in (r.get("descricao", ""), r.get("creditos", ""), creditos_video, hashtags) if p)
    log("  preparando título e descrição para o YouTube…")
    yt = pacote_youtube(canal, r, log)
    _salvar_info(pasta, {
        "canal": canal_id, "titulo": r["titulo"], "descricao": r.get("descricao", ""), "descricao_yt": descricao_yt,
        "youtube": yt,
        "tags": r.get("tags", []), "duracao": round(duracao, 1), "creditos": creditos,
        "voz": voz_id or canal["voz"], "status": "rascunho",
        "criado_em": datetime.now().isoformat(timespec="seconds"),
        "segundos_para_gerar": round(time.time() - inicio),
    })
    shutil.rmtree(tmp, ignore_errors=True)
    log(f"Pronto! {duracao:.0f}s de vídeo em {round(time.time() - inicio)}s")
    return pasta
