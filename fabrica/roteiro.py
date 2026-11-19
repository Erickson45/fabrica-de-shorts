"""Roteiro: pede à IA local (Ollama) um roteiro em JSON seguindo o molde do canal."""
import json
import random
import re
import urllib.request
from pathlib import Path

OLLAMA = "http://127.0.0.1:11434/api/generate"
MODELO_PADRAO = "qwen2.5:7b"


def modelo():
    """Usa o melhor modelo instalado (gemma3:12b escreve português melhor, se estiver baixado)."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as r:
            nomes = [m["name"] for m in json.load(r).get("models", [])]
    except Exception:
        return MODELO_PADRAO
    for preferido in ("gemma3:12b", "qwen2.5:14b", "qwen2.5:7b"):
        if preferido in nomes:
            return preferido
    return MODELO_PADRAO


def _pedir(prompt, temperatura=0.9):
    corpo = json.dumps({
        "model": modelo(), "prompt": prompt, "format": "json", "stream": False,
        "keep_alive": "45s",  # libera a RAM logo depois, para a montagem do vídeo ter a máquina livre
        "options": {"temperature": temperatura, "num_ctx": 4096},
    }).encode()
    req = urllib.request.Request(OLLAMA, data=corpo, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1200) as r:  # na CPU pode levar alguns minutos
        return json.load(r)["response"]


def contar(r):
    total = 0
    for c in r.get("cenas") or []:
        total += len((c.get("texto") or "").split()) + len((c.get("explicacao") or "").split())
    return total


def _normalizar(r):
    """Conserta pequenos desvios comuns de modelos pequenos (opções como dicionário, letras minúsculas…)."""
    for c in r.get("cenas") or []:
        if isinstance(c.get("opcoes"), dict):
            c["opcoes"] = list(c["opcoes"].values())
        if isinstance(c.get("correta"), str):
            c["correta"] = c["correta"].strip().upper()[:1]
        for k in ("texto", "explicacao", "titulo", "busca"):
            if isinstance(c.get(k), str):
                c[k] = c[k].strip()
    if isinstance(r.get("ruim"), str):
        r["ruim"] = r["ruim"].strip().upper()[:1]
    return r


def validar(r, canal):
    cenas = r.get("cenas") or []
    tipos = [c.get("tipo") for c in cenas]
    if tipos != canal["estrutura"]:
        return "as cenas precisam ser exatamente, nesta ordem: " + ", ".join(canal["estrutura"])
    if any(not (c.get("texto") or "").strip() for c in cenas):
        return "toda cena precisa de texto"
    if not (r.get("titulo") or "").strip():
        return "faltou o titulo"
    f = canal["formato"]
    if f == "escolha" and (not r.get("opcao_a") or not r.get("opcao_b") or r.get("ruim") not in ("A", "B")):
        return "faltou opcao_a, opcao_b ou ruim (A/B)"
    if f == "fatos" and any(not c.get("titulo") for c in cenas if c["tipo"] == "fato"):
        return "todo fato precisa de titulo"
    if f == "quiz":
        for c in cenas:
            if c["tipo"] != "pergunta":
                continue
            if not isinstance(c.get("opcoes"), list) or len(c["opcoes"]) != 3 or not all(c["opcoes"]):
                return "toda pergunta precisa de exatamente 3 opcoes"
            if c.get("correta") not in ("A", "B", "C"):
                return "toda pergunta precisa de correta = A, B ou C"
            if not c.get("explicacao"):
                return "toda pergunta precisa de explicacao"
    minimo, maximo = canal["palavras"]
    palavras = contar(r)
    if palavras < minimo:
        return f"curto: {palavras} palavras"
    if palavras > maximo:
        return f"longo: {palavras} palavras"
    return None


def _ler(texto):
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", texto, re.S)
        try:
            return json.loads(m.group(0)) if m else {}
        except json.JSONDecodeError:
            return {}


def _ajustar(r, canal, erro):
    """Modelos pequenos erram o tamanho: pede para ajustar o MESMO roteiro, em vez de recomeçar."""
    direcao = "CURTO DEMAIS: deixe cada cena mais longa e cheia de detalhes" if erro.startswith("curto") \
        else "LONGO DEMAIS: enxugue as frases, sem perder a história"
    return (
        f"Este roteiro de YouTube Shorts está {direcao} ({contar(r)} palavras).\n"
        "Reescreva o MESMO roteiro, mantendo o tema, a ordem das cenas e o formato JSON, respeitando estes tamanhos:\n"
        f"{canal['tamanhos']}\n\nRoteiro atual:\n{json.dumps(r, ensure_ascii=False, indent=1)}\n\n"
        "Responda SOMENTE com o JSON completo."
    )


# ------------------------------------------------------------------ bancos verificados (quiz e fatos)
BANCOS = Path(__file__).resolve().parent.parent / "bancos"


def _banco(nome):
    return json.loads((BANCOS / f"{nome}.json").read_text(encoding="utf-8"))


def _usados():
    arq = BANCOS / "usados.json"
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {}


def _marcar_usados(nome, ids):
    u = _usados()
    u[nome] = list(dict.fromkeys(u.get(nome, []) + list(ids)))
    (BANCOS / "usados.json").write_text(json.dumps(u, indent=1), encoding="utf-8")


def _categoria_do_tema(canal, tema):
    for cat, temas in canal["categorias"].items():
        if tema == cat or tema in temas:
            return cat, temas
    return None, []


def _sortear(itens, nome, quantos, chave_nivel=None):
    """Prefere itens ainda não usados; quando acabarem, recomeça o ciclo."""
    usados = set(_usados().get(nome, []))
    novos = [i for i in itens if i["id"] not in usados]
    if len(novos) < quantos:
        novos = list(itens)
    random.shuffle(novos)
    if chave_nivel:  # um fácil, um médio, um difícil, quando der
        escolha = []
        for nivel in (1, 2, 3):
            cand = [i for i in novos if i.get(chave_nivel) == nivel and i not in escolha]
            if cand:
                escolha.append(cand[0])
        for i in novos:
            if len(escolha) >= quantos:
                break
            if i not in escolha:
                escolha.append(i)
        return sorted(escolha[:quantos], key=lambda i: i.get(chave_nivel, 0))
    return novos[:quantos]


def _moldura(canal, itens_txt, tipo, log):
    """A IA escreve só título, gancho e final (sem acrescentar fatos). Se falhar, usa um modelo pronto."""
    if tipo == "quiz":
        pedido = ("gancho: 10 a 16 palavras desafiando a pessoa a acertar as três perguntas;\n"
                  "final: 8 a 12 palavras perguntando quantas a pessoa acertou e pedindo pra comentar.")
    else:
        pedido = ("gancho: 14 a 22 palavras prometendo fatos reais e perturbadores, SEM citar nenhum detalhe;\n"
                  "final: 10 a 14 palavras perguntando qual fato foi o mais assustador e pedindo pra seguir o canal.")
    prompt = (f"Você escreve para o canal de YouTube Shorts \"{canal['nome']}\", em português do Brasil.\n"
              f"O vídeo já tem este conteúdo (NÃO altere, NÃO acrescente fatos, números ou respostas):\n{itens_txt}\n\n"
              f"Escreva só:\ntitulo: chamativo, até 50 caracteres, sem revelar respostas;\n{pedido}\n"
              "descricao: 1 frase curta; tags: 5 tags em português.\n"
              "Responda SOMENTE com JSON: {\"titulo\": \"\", \"gancho\": \"\", \"final\": \"\", \"descricao\": \"\", \"tags\": []}")
    try:
        m = _ler(_pedir(prompt, temperatura=0.8))
        ok = all(isinstance(m.get(k), str) and m[k].strip() for k in ("titulo", "gancho", "final")) \
            and len(m["gancho"].split()) <= 30 and len(m["final"].split()) <= 20 and len(m["titulo"]) <= 70
        if ok:
            return m
        log("  moldura da IA fora do padrão; usando modelo pronto")
    except Exception as e:
        log(f"  IA indisponível para a moldura ({e}); usando modelo pronto")
    if tipo == "quiz":
        return {"titulo": random.choice(["Só 1% acerta as 3. E você?", "Duvido você acertar as três", "Teste rápido: acerta as 3?"]),
                "gancho": random.choice(["Três perguntas, três segundos cada. Só um por cento acerta todas. Bora?",
                                         "Você tem três segundos pra cada pergunta. Será que acerta as três?"]),
                "final": "Quantas você acertou? Fala a verdade nos comentários.",
                "descricao": "Três perguntas, três segundos cada.", "tags": ["quiz", "perguntas", "desafio", "curiosidades", "shorts"]}
    return {"titulo": random.choice(["3 fatos reais que parecem mentira", "Isso aconteceu de verdade", "3 fatos sombrios que ninguém te contou"]),
            "gancho": "Esses três fatos aconteceram de verdade. E o último é o mais perturbador de todos.",
            "final": "Qual desses fatos te deu mais arrepio? Comenta e segue pra mais.",
            "descricao": "Fatos reais, sombrios e históricos.", "tags": ["fatos", "historia", "misterio", "curiosidades", "shorts"]}


def do_banco(canal, tema, log=print):
    nome = canal["banco"]
    cat, temas_cat = _categoria_do_tema(canal, tema)
    if nome == "quiz":
        todos = _banco("quiz")
        pool = [q for q in todos if q["tema"] == tema] or [q for q in todos if q["tema"] in temas_cat]
        if len(pool) < 3:  # tema livre: procura por palavras parecidas, senão mistura tudo
            palavras = [p for p in re.findall(r"\w{4,}", tema.lower())]
            pool = [q for q in todos if any(p in (q["tema"] + " " + q["pergunta"]).lower() for p in palavras)]
            if len(pool) < 3:
                pool = todos
        itens = _sortear(pool, "quiz", 3, chave_nivel="nivel")
        txt = "\n".join(f"- {q['pergunta']} (resposta: {q['opcoes']['ABC'.index(q['correta'])]})" for q in itens)
        m = _moldura(canal, txt, "quiz", log)
        cenas = [{"tipo": "gancho", "texto": m["gancho"], "busca": "question mark neon"}]
        cenas += [{"tipo": "pergunta", "texto": q["pergunta"], "opcoes": q["opcoes"], "correta": q["correta"],
                   "explicacao": q["explicacao"], "busca": q["busca"], "banco_id": q["id"]} for q in itens]
        cenas.append({"tipo": "final", "texto": m["final"], "busca": "trophy light"})
    else:
        todos = _banco("fatos")
        if not cat:
            cat = random.choice(sorted({f["categoria"] for f in todos}))
        itens = _sortear([f for f in todos if f["categoria"] == cat], "fatos", 3)
        txt = "\n".join(f"- {f['titulo']}: {f['texto']}" for f in itens)
        m = _moldura(canal, txt, "fatos", log)
        cenas = [{"tipo": "gancho", "texto": m["gancho"], "busca": itens[0]["busca"]}]
        cenas += [{"tipo": "fato", "titulo": f["titulo"], "texto": f["texto"], "busca": f["busca"], "banco_id": f["id"]}
                  for f in itens]
        cenas.append({"tipo": "final", "texto": m["final"], "busca": "dark library candle"})
    _marcar_usados(nome, [i["id"] for i in itens])
    log(f"  banco verificado: {', '.join(i['id'] for i in itens)}")
    # créditos exigidos pela licença (CC BY-SA) das fontes abertas
    creditos = []
    if any("opentdb" in (i.get("fonte") or "") for i in itens):
        creditos.append("Perguntas adaptadas do Open Trivia Database (opentdb.com), licença CC BY-SA 4.0.")
    urls = [i["url"] for i in itens if i.get("url")]
    if urls:
        creditos.append("Fontes: Wikipédia, licença CC BY-SA 4.0:\n" + "\n".join(urls))
    return {"titulo": m["titulo"].strip().strip('"')[:90], "descricao": m.get("descricao", ""),
            "tags": m.get("tags") or [], "cenas": cenas, "tema": tema, "fonte": "banco verificado",
            "creditos": "\n".join(creditos)}


def gerar(canal, tema=None, tentativas=4, log=print):
    tema = tema or random.choice([t for lista in canal["categorias"].values() for t in lista])
    if canal.get("banco"):
        log(f"  modelo: {modelo()} (só título e chamadas) · tema: {tema}")
        return do_banco(canal, tema, log)
    prompt = canal["prompt"].replace("{tema}", tema)
    r, erro = {}, None
    log(f"  modelo: {modelo()} · tema: {tema}")
    for i in range(tentativas):
        if erro and (erro.startswith("curto") or erro.startswith("longo")):  # estrutura ok, só falta tamanho
            log(f"  roteiro {erro}; pedindo para a IA ajustar (tentativa {i + 1})…")
            r = _normalizar(_ler(_pedir(_ajustar(r, canal, erro), temperatura=0.7)))
        else:
            log(f"  roteiro: pedindo à IA (tentativa {i + 1})…")
            r = _normalizar(_ler(_pedir(prompt + (f"\n\nATENÇÃO, corrija: {erro}" if erro else ""))))
        erro = validar(r, canal)
        if not erro:
            r["tema"] = tema
            r["titulo"] = r["titulo"].strip().strip('"')[:90]
            log(f"  roteiro ok: {contar(r)} palavras")
            return r
        log(f"  roteiro inválido: {erro}")
    raise RuntimeError(f"A IA não gerou um roteiro válido: {erro}")
