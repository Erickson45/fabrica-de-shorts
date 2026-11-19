"""Importador: enche os bancos verificados a partir de fontes abertas.

- Quiz: Open Trivia Database (opentdb.com, CC BY-SA 4.0). Perguntas já verificadas pela comunidade;
  a IA local só TRADUZ, e a resposta certa vem da fonte.
- Fatos: Wikipédia (CC BY-SA 4.0). A IA resume um fato usando SÓ o texto do artigo, e o link fica salvo.

Travas contra invenção:
- números do texto gerado precisam existir no texto de origem;
- a ordem das opções e os números de cada opção do quiz não podem mudar na tradução;
- artigos sobre pessoas vivas são ignorados;
- a IA dá uma nota de "interesse" e só entra o que for sombrio/intrigante o bastante.

Roda em segundo plano, devagar, e pausa sozinho enquanto um vídeo está sendo produzido.
"""
import hashlib
import html
import json
import random
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import roteiro

RAIZ = Path(__file__).resolve().parent.parent
BANCOS = RAIZ / "bancos"
BRUTOS = BANCOS / "brutos"
UA = "FabricaShorts/1.0 (personal project; slow single-thread importer)"

# Open Trivia DB: categoria -> tema do canal "Só 1% Acerta"
OTDB_CATEGORIAS = {
    9: "conhecimentos gerais", 17: "ciência e natureza", 19: "matemática", 20: "mitologia",
    22: "geografia e países", 23: "história mundial", 27: "animais", 30: "tecnologia",
}
NIVEL = {"easy": 1, "medium": 2, "hard": 3}

# Wikipédia (inglês, que tem muito mais artigos): categorias -> categoria do canal "Fatos Sombrios"
WIKI_CATEGORIAS = {
    "Mistérios sem solução": ["Unexplained disappearances", "Ghost ships", "Unidentified decedents",
                              "Undeciphered writing systems", "Unsolved murders", "Missing aircraft",
                              "Maritime incidents with unknown causes", "Fortean events"],
    "História macabra": ["Mass psychogenic illness", "Medical scandals", "Witch trials", "Body snatching",
                         "Mummies", "Plague (disease)", "Historical epidemics", "Massacres"],
    "Ciência sombria": ["Radiation accidents and incidents", "Unethical human experimentation",
                        "Limnic eruptions", "Extremophiles", "Parasites of humans", "Deep sea fish",
                        "Nuclear accidents", "Poisonings"],
    "Lugares proibidos": ["Ghost towns", "Catacombs", "Ossuaries", "Abandoned islands",
                          "Exclusion zones", "Abandoned buildings and structures", "Ruins",
                          "Underground cities"],
}

estado = {"rodando": False, "fonte": None, "msg": "", "aceitos": 0, "descartados": 0, "erro": None, "proximo": None}
_parar = threading.Event()


# ------------------------------------------------------------------ utilidades
def _json(arq, padrao):
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else padrao


def _gravar(arq, dados):
    arq.parent.mkdir(parents=True, exist_ok=True)
    tmp = arq.with_suffix(".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(arq)


def _ua():
    """A Wikipédia exige um contato (e-mail ou site) na identificação do programa; vem do config.json."""
    contato = _json(RAIZ / "config.json", {}).get("contato_wikipedia")
    return f"FabricaShorts/1.0 ({contato}; slow single-thread importer)" if contato else UA


def precisa_contato():
    return not _json(RAIZ / "config.json", {}).get("contato_wikipedia")


def _get(url, espera_429=120):
    """GET educado: repete com espera crescente quando o servidor pede calma (429)."""
    for tentativa in range(6):
        if _parar.is_set():
            raise InterruptedError
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _ua()})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                estado["msg"] = f"a fonte pediu calma; esperando {espera_429 * (tentativa + 1)}s antes de continuar"
                _dormir(espera_429 * (tentativa + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            _dormir(20)
    raise RuntimeError(f"não consegui acessar {url[:80]}")


def _dormir(seg):
    _parar.wait(seg)


def _numeros(txt):
    """Números de um texto, normalizados: '1.746' e '1,746' -> 1746; '300 mil' -> 300000; '2 milhões' -> 2000000."""
    t = (txt or "").lower()
    t = re.sub(r"(\d)[.,](\d{3})\b", r"\1\2", t)
    t = re.sub(r"(\d)[.,](\d{3})\b", r"\1\2", t)  # 2 vezes: 1.234.567
    # intervalos: "100 a 300 mil" -> "100 mil a 300 mil"
    t = re.sub(r"(\d+)\s*(a|e|-|até|to|and)\s*(\d+)\s*(mil|milhões|thousand|million|bilhões|billion)\b",
               r"\1 \4 \2 \3 \4", t)
    mult = {"mil": 1_000, "thousand": 1_000, "milhão": 1_000_000, "milhões": 1_000_000, "million": 1_000_000,
            "bilhão": 1_000_000_000, "bilhões": 1_000_000_000, "billion": 1_000_000_000}
    nums = set()
    for n, palavra in re.findall(r"(\d+(?:[.,]\d+)?)\s*(mil|milhão|milhões|thousand|million|bilhão|bilhões|billion)?\b", t):
        n = n.replace(",", ".")
        if palavra:
            nums.add(str(int(round(float(n) * mult[palavra]))))
        elif "." in n:  # decimal: 2.50 -> 2.5
            nums.add(n.rstrip("0").rstrip("."))
        else:
            nums.add(n)
    return nums


def contagem():
    return {"quiz": len(_json(BANCOS / "quiz.json", [])), "fatos": len(_json(BANCOS / "fatos.json", []))}


# ------------------------------------------------------------------ quiz (Open Trivia DB)
def _baixar_otdb():
    """Baixa (uma vez) todas as perguntas de múltipla escolha das categorias escolhidas."""
    arq = BRUTOS / "opentdb.json"
    salvo = _json(arq, {})
    if isinstance(salvo, list):  # formato antigo
        salvo = {"feitas": [], "perguntas": salvo}
    brutos, feitas = salvo.get("perguntas", []), set(salvo.get("feitas", []))
    vistas = {q["question"] for q in brutos}
    faltam = [c for c in OTDB_CATEGORIAS if c not in feitas]
    if not faltam:
        return brutos
    token = _get("https://opentdb.com/api_token.php?command=request", espera_429=8)["token"]
    for cat in faltam:
        while not _parar.is_set():
            estado["msg"] = f"baixando perguntas (categoria {cat}) · {len(brutos)} até agora"
            d = _get(f"https://opentdb.com/api.php?amount=50&category={cat}&type=multiple&encode=url3986&token={token}",
                     espera_429=8)
            if d.get("response_code") == 5:  # limite: 1 pedido a cada 5 s
                _dormir(6)
                continue
            if d.get("response_code") != 0 or not d.get("results"):
                break  # esta categoria acabou
            for q in d["results"]:
                q = {k: (urllib.parse.unquote(v) if isinstance(v, str) else [urllib.parse.unquote(x) for x in v])
                     for k, v in q.items()}
                if q["question"] not in vistas:
                    q["cat_id"] = cat
                    brutos.append(q)
                    vistas.add(q["question"])
            _dormir(6)
        if _parar.is_set():
            break
        feitas.add(cat)
        _gravar(arq, {"feitas": sorted(feitas), "perguntas": brutos})
    return brutos


FORA_DO_CONTEXTO = ("united states", "u.s.", "american", "u.s. state", "us state", "nfl", "nba", "mlb", "nhl",
                    "super bowl", "london underground", "uk ", "british tv", "congress", "senator", "governor",
                    "canadian province", "australian state")


def _traduzir_pergunta(q):
    texto_en = (q["question"] + " " + " ".join(q["incorrect_answers"] + [q["correct_answer"]])).lower()
    if any(p in texto_en for p in FORA_DO_CONTEXTO):  # filtro rápido, sem gastar a IA
        return None
    erradas = random.sample(q["incorrect_answers"], 2)
    opcoes = erradas + [q["correct_answer"]]
    random.shuffle(opcoes)
    certa = opcoes.index(q["correct_answer"])
    prompt = (
        "Traduza esta pergunta de quiz do inglês para o português do Brasil, de forma natural e curta.\n"
        "NÃO mude o sentido, NÃO mude a resposta e mantenha as opções NA MESMA ORDEM. Escreva números com algarismos.\n"
        "Traduza TAMBÉM as opções: nomes de países, cidades e animais em português (ex.: Indonesia -> Indonésia, "
        "Iran -> Irã). Obras e pessoas: use o nome conhecido no Brasil, ou mantenha o original.\n"
        "Depois escreva \"explicacao\": 10 a 18 palavras que apenas confirmam a resposta certa, "
        "sem acrescentar nenhum fato novo que não esteja na pergunta ou na resposta.\n\n"
        f"Pergunta: {q['question']}\n"
        + "".join(f"Opção {i + 1}: {o}\n" for i, o in enumerate(opcoes))
        + f"Resposta certa: opção {certa + 1} ({q['correct_answer']})\n\n"
        "\"nota\" = de 1 a 5, quão boa essa pergunta é para um quiz viral no Brasil: 5 = curiosa e que um "
        "brasileiro comum consegue tentar responder; 1 = muito obscura, muito técnica ou muito específica de outro "
        "país (ex.: número de estações de um metrô estrangeiro, estados americanos, esportes americanos).\n"
        "\"busca\" = 2 a 4 palavras em inglês para um vídeo de fundo (sem nomes próprios).\n"
        "Responda SOMENTE com JSON: {\"pergunta\": \"\", \"opcoes\": [\"\", \"\", \"\"], \"explicacao\": \"\", "
        "\"busca\": \"\", \"nota\": 3}"
    )
    t = roteiro._ler(roteiro._pedir(prompt, temperatura=0.2))
    ops = t.get("opcoes")
    try:
        nota = int(t.get("nota", 0))
    except (TypeError, ValueError):
        nota = 0
    if nota < 3 or not isinstance(ops, list) or len(ops) != 3:
        return None
    # trava: os números de cada opção têm que ser os mesmos do original
    if any(_numeros(a) != _numeros(b) for a, b in zip(opcoes, ops)):
        return None
    if _numeros(t.get("pergunta")) - _numeros(q["question"]):
        return None
    if not t.get("pergunta") or len(t["pergunta"]) > 150 or any(not o or len(str(o)) > 45 for o in ops):
        return None
    return {
        "id": "otdb_" + hashlib.md5(q["question"].encode()).hexdigest()[:10],
        "tema": OTDB_CATEGORIAS[q["cat_id"]], "nivel": NIVEL.get(q["difficulty"], 2),
        "pergunta": t["pergunta"].strip(), "opcoes": [str(o).strip() for o in ops], "correta": "ABC"[certa],
        "explicacao": (t.get("explicacao") or f"A resposta certa é {ops[certa]}.").strip(),
        "busca": (t.get("busca") or "question mark").strip(),
        "fonte": "Open Trivia Database (opentdb.com), CC BY-SA 4.0", "original": q["question"],
    }


def importar_quiz(meta=3000, ocupado=lambda: False):
    brutos = _baixar_otdb()
    random.shuffle(brutos)
    processados = set(_json(BRUTOS / "processados_quiz.json", []))
    banco = _json(BANCOS / "quiz.json", [])
    ids = {q["id"] for q in banco}
    for q in brutos:
        if _parar.is_set() or len(banco) >= meta:
            break
        chave = hashlib.md5(q["question"].encode()).hexdigest()[:10]
        if chave in processados:
            continue
        while ocupado() and not _parar.is_set():  # deixa a máquina livre para a produção de vídeos
            estado["msg"] = "pausado: um vídeo está sendo produzido"
            _dormir(10)
        estado["msg"] = f"traduzindo: {q['question'][:70]}"
        try:
            item = _traduzir_pergunta(q)
        except Exception as e:
            estado["erro"] = str(e)
            _dormir(15)
            continue
        processados.add(chave)
        if item and item["id"] not in ids:
            banco.append(item)
            ids.add(item["id"])
            estado["aceitos"] += 1
            _gravar(BANCOS / "quiz.json", banco)
        else:
            estado["descartados"] += 1
        _gravar(BRUTOS / "processados_quiz.json", sorted(processados))


# ------------------------------------------------------------------ fatos (Wikipédia)
API = "https://en.wikipedia.org/w/api.php?"


def _membros(categoria, profundidade=2, vistos=None):
    """Artigos de uma categoria e das subcategorias (até `profundidade`)."""
    vistos = vistos if vistos is not None else set()
    if categoria in vistos or _parar.is_set():
        return []
    vistos.add(categoria)
    paginas, cont = [], {}
    while True:
        p = {"action": "query", "list": "categorymembers", "cmtitle": f"Category:{categoria}",
             "cmlimit": "500", "cmtype": "page|subcat", "format": "json", "maxlag": "5", **cont}
        d = _get(API + urllib.parse.urlencode(p))
        _dormir(1.5)
        for m in d.get("query", {}).get("categorymembers", []):
            if m["ns"] == 0:
                paginas.append(m["title"])
            elif m["ns"] == 14 and profundidade > 0:
                paginas += _membros(m["title"].split(":", 1)[1], profundidade - 1, vistos)
        if "continue" not in d:
            return paginas
        cont = {"cmcontinue": d["continue"]["cmcontinue"]}


def _candidatos():
    arq = BRUTOS / "wiki_candidatos.json"
    cand = _json(arq, [])
    if cand:
        return cand
    vistos_titulos = set()
    for cat_canal, cats in WIKI_CATEGORIAS.items():
        for c in cats:
            estado["msg"] = f"listando artigos: {c} · {len(cand)} até agora"
            try:
                titulos = _membros(c, profundidade=2 if c != "Ghost towns" else 3)
            except InterruptedError:
                raise
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    raise RuntimeError("a Wikipédia está bloqueando; confira o contato e tente mais tarde")
                continue  # categoria não existe: segue
            except Exception:
                continue
            for t in titulos:
                if t not in vistos_titulos and not t.startswith("List of"):
                    vistos_titulos.add(t)
                    cand.append({"titulo": t, "categoria": cat_canal})
        _gravar(arq, cand)
    return cand


def _resumos(titulos):
    """Resumo (introdução em texto puro) de até 20 artigos numa chamada só; ignora pessoas vivas."""
    p = {"action": "query", "prop": "extracts|categories", "exintro": "1", "explaintext": "1", "exlimit": "20",
         "clcategories": "Category:Living people", "titles": "|".join(titulos), "format": "json",
         "redirects": "1", "maxlag": "5"}
    d = _get(API + urllib.parse.urlencode(p))
    saida = {}
    for pg in d.get("query", {}).get("pages", {}).values():
        if pg.get("categories"):  # pessoa viva: fora
            continue
        txt = (pg.get("extract") or "").strip()
        if len(txt) >= 300:
            saida[pg["title"]] = txt
    return saida


def _resumir_fato(titulo, texto):
    prompt = (
        f"Texto da Wikipédia sobre \"{titulo}\":\n\"\"\"\n{texto[:2200]}\n\"\"\"\n\n"
        "Escreva UM fato sombrio e intrigante para um YouTube Short, em português do Brasil, usando SOMENTE "
        "informações que estão no texto acima. Regras:\n"
        "- não invente nada, não acrescente detalhes que não estejam no texto;\n"
        "- escreva números com algarismos (ex.: 1872, 9 pessoas);\n"
        "- não acuse pessoas: só fale de culpa se o texto disser que foi comprovada;\n"
        "- tom de documentário misterioso, frases curtas.\n"
        "Responda SOMENTE com JSON: {\"titulo\": \"2 a 5 palavras\", \"texto\": \"26 a 38 palavras\", "
        "\"busca\": \"2 a 4 palavras em inglês para vídeo de fundo, sem nomes próprios\", "
        "\"nota\": 1 a 5 (quão sombrio e intrigante isso é para o público geral; 1 = sem graça)}"
    )
    f = roteiro._ler(roteiro._pedir(prompt, temperatura=0.3))
    txt = (f.get("texto") or "").strip()
    try:
        nota = int(f.get("nota", 0))
    except (TypeError, ValueError):
        nota = 0
    if nota < 3 or not 20 <= len(txt.split()) <= 44 or not f.get("titulo"):
        return None
    if _numeros(txt) - _numeros(texto):  # trava: nenhum número inventado
        return None
    return {"titulo": f["titulo"].strip()[:40], "texto": txt, "busca": (f.get("busca") or "dark fog").strip(),
            "nota": nota}


def importar_fatos(meta=3000, ocupado=lambda: False):
    if precisa_contato():
        raise RuntimeError("a Wikipédia exige um contato: preencha 'contato_wikipedia' no painel")
    cand = _candidatos()
    random.shuffle(cand)
    processados = set(_json(BRUTOS / "processados_fatos.json", []))
    banco = _json(BANCOS / "fatos.json", [])
    ids = {f["id"] for f in banco}
    pendentes = [c for c in cand if c["titulo"] not in processados]
    for i in range(0, len(pendentes), 20):
        if _parar.is_set() or len(banco) >= meta:
            break
        lote = pendentes[i:i + 20]
        estado["msg"] = "lendo artigos da Wikipédia…"
        try:
            textos = _resumos([c["titulo"] for c in lote])
        except InterruptedError:
            break
        except Exception as e:
            estado["erro"] = str(e)
            _dormir(30)
            continue
        _dormir(2)
        for c in lote:
            if _parar.is_set():
                break
            processados.add(c["titulo"])
            texto = textos.get(c["titulo"])
            if not texto:
                estado["descartados"] += 1
                continue
            while ocupado() and not _parar.is_set():
                estado["msg"] = "pausado: um vídeo está sendo produzido"
                _dormir(10)
            estado["msg"] = f"resumindo: {c['titulo']}"
            try:
                fato = _resumir_fato(c["titulo"], texto)
            except Exception as e:
                estado["erro"] = str(e)
                _dormir(15)
                continue
            fid = "wp_" + hashlib.md5(c["titulo"].encode()).hexdigest()[:10]
            if fato and fid not in ids:
                banco.append({"id": fid, "categoria": c["categoria"], **fato,
                              "fonte": "Wikipédia, CC BY-SA 4.0",
                              "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(c["titulo"].replace(" ", "_"))})
                ids.add(fid)
                estado["aceitos"] += 1
                _gravar(BANCOS / "fatos.json", banco)
            else:
                estado["descartados"] += 1
        _gravar(BRUTOS / "processados_fatos.json", sorted(processados))


# ------------------------------------------------------------------ controle
def iniciar(fonte, meta=3000, ocupado=lambda: False):
    """Começa a importar. Se já estiver importando o outro banco, este entra como 'próximo da vez'."""
    if estado["rodando"]:
        if estado["fonte"] != fonte:
            estado["proximo"] = fonte
        return False
    _parar.clear()
    estado.update(rodando=True, fonte=fonte, msg="começando…", aceitos=0, descartados=0, erro=None, proximo=None)

    def rodar():
        try:
            (importar_quiz if fonte == "quiz" else importar_fatos)(meta, ocupado)
            estado["msg"] = "parado" if _parar.is_set() else "concluído"
        except InterruptedError:
            estado["msg"] = "parado"
        except Exception as e:
            estado["erro"] = str(e)
            estado["msg"] = "parou com erro"
        finally:
            estado["rodando"] = False
            proximo = estado.get("proximo")
            if proximo and not _parar.is_set():
                iniciar(proximo, meta, ocupado)

    threading.Thread(target=rodar, daemon=True).start()
    return True


def parar():
    estado["proximo"] = None
    _parar.set()
