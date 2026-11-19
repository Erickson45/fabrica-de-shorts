"""Envio para o YouTube pela API oficial (YouTube Data API v3).

- Cada formato (canal do painel) é conectado uma vez: abre o login do Google no navegador,
  você escolhe o canal certo e clica em "Permitir". O acesso fica salvo em tokens/<canal>.json.
- Antes de enviar, confere se o token é mesmo do canal configurado (nunca posta no canal errado).
- Atenção: projetos do Google Cloud ainda não auditados têm os vídeos enviados pela API
  travados como PRIVADOS até a auditoria ser aprovada. Cota padrão: ~6 envios por dia.
"""
import glob
import json
import threading
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TOKENS = RAIZ / "tokens"
ESCOPOS = ["https://www.googleapis.com/auth/youtube.upload",
           "https://www.googleapis.com/auth/youtube.readonly"]
CATEGORIA = {"quiz": "27", "fatos": "27", "escolha": "24", "conto": "24"}  # 27 Educação, 24 Entretenimento

conexao = {"canal": None, "msg": "", "erro": None, "rodando": False}


def _cliente():
    arqs = glob.glob(str(RAIZ / "client_secret*.json"))
    if not arqs:
        raise RuntimeError("Arquivo client_secret*.json não encontrado na pasta da Fábrica.")
    return arqs[0]


def _creds(canal_id):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    arq = TOKENS / f"{canal_id}.json"
    if not arq.exists():
        return None, None
    dados = json.loads(arq.read_text(encoding="utf-8"))
    creds = Credentials.from_authorized_user_info(dados["token"], ESCOPOS)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        dados["token"] = json.loads(creds.to_json())
        arq.write_text(json.dumps(dados, indent=1), encoding="utf-8")
    return creds, dados.get("canal_youtube")


def status(canal_id):
    """{conectado, canal_youtube: {id, titulo}} sem chamar a internet."""
    arq = TOKENS / f"{canal_id}.json"
    if not arq.exists():
        return {"conectado": False}
    return {"conectado": True, "canal_youtube": json.loads(arq.read_text(encoding="utf-8")).get("canal_youtube")}


def conectar(canal_id, esperado_id=None):
    """Abre o login do Google no navegador padrão (em segundo plano) e salva o acesso do canal escolhido."""
    if conexao["rodando"]:
        return False

    def rodar():
        conexao.update(canal=canal_id, rodando=True, erro=None,
                       msg="Abri o login do Google no seu navegador: escolha o canal e clique em Permitir.")
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
            flow = InstalledAppFlow.from_client_secrets_file(_cliente(), ESCOPOS)
            creds = flow.run_local_server(port=0, open_browser=True, prompt="consent",
                                          authorization_prompt_message="", timeout_seconds=600)
            yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
            itens = yt.channels().list(part="snippet", mine=True).execute().get("items", [])
            if not itens:
                raise RuntimeError("Essa conta não tem canal no YouTube.")
            canal_yt = {"id": itens[0]["id"], "titulo": itens[0]["snippet"]["title"]}
            if esperado_id and canal_yt["id"] != esperado_id:
                raise RuntimeError(f"Você escolheu o canal \"{canal_yt['titulo']}\", mas este formato usa outro. "
                                   "Clique em Conectar de novo e escolha o canal certo na tela do Google.")
            TOKENS.mkdir(exist_ok=True)
            (TOKENS / f"{canal_id}.json").write_text(json.dumps(
                {"token": json.loads(creds.to_json()), "canal_youtube": canal_yt}, indent=1), encoding="utf-8")
            conexao["msg"] = f"Conectado a \"{canal_yt['titulo']}\"."
        except Exception as e:
            conexao["erro"] = str(e)
            conexao["msg"] = "A conexão não foi concluída."
        finally:
            conexao["rodando"] = False

    threading.Thread(target=rodar, daemon=True).start()
    return True


def desconectar(canal_id):
    (TOKENS / f"{canal_id}.json").unlink(missing_ok=True)


def enviar(canal, pasta, privacidade="public", log=print):
    """Envia o vídeo da pasta com o pacote YouTube (título, descrição, tags) e grava o link em info.json."""
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    pasta = Path(pasta)
    info = json.loads((pasta / "info.json").read_text(encoding="utf-8"))
    pacote = info.get("youtube")
    if not pacote:
        raise RuntimeError("Este vídeo ainda não tem pacote YouTube. Gere o pacote antes de enviar.")
    creds, canal_yt = _creds(canal["id"])
    if not creds:
        raise RuntimeError(f"O canal \"{canal['nome']}\" ainda não foi conectado ao YouTube no painel.")
    esperado = (canal.get("youtube") or {}).get("id")
    if esperado and canal_yt and canal_yt["id"] != esperado:
        raise RuntimeError("O acesso salvo é de outro canal. Conecte de novo escolhendo o canal certo.")

    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    corpo = {
        "snippet": {
            "title": pacote["titulo"][:100],
            "description": pacote["descricao"][:4900],
            "tags": pacote.get("tags", [])[:15],
            "categoryId": CATEGORIA.get(canal["formato"], "24"),
            "defaultLanguage": "pt-BR",
            "defaultAudioLanguage": "pt-BR",
        },
        "status": {
            "privacyStatus": privacidade,
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,  # aviso de conteúdo gerado/alterado por IA
        },
    }
    log(f"Enviando “{pacote['titulo']}” para {canal_yt['titulo'] if canal_yt else canal['nome']}…")
    midia = MediaFileUpload(str(pasta / "video.mp4"), mimetype="video/mp4", chunksize=4 * 1024 * 1024, resumable=True)
    pedido = yt.videos().insert(part="snippet,status", body=corpo, media_body=midia)
    resposta = None
    try:
        while resposta is None:
            andamento, resposta = pedido.next_chunk()
            if andamento:
                log(f"  enviado {int(andamento.progress() * 100)}%")
    except HttpError as e:
        motivo = str(e)
        if "quotaExceeded" in motivo or "uploadLimitExceeded" in motivo:
            raise RuntimeError("Limite diário de envios do YouTube atingido. Tente de novo amanhã.")
        raise RuntimeError(f"O YouTube recusou o envio: {motivo[:300]}")

    video_id = resposta["id"]
    status_final = resposta.get("status", {}).get("privacyStatus", privacidade)
    info["status"] = "enviado"
    info["enviado"] = {
        "video_id": video_id, "url": f"https://youtube.com/shorts/{video_id}",
        "studio": f"https://studio.youtube.com/video/{video_id}/edit",
        "canal": canal_yt["titulo"] if canal_yt else canal["nome"],
        "privacidade": status_final, "quando": datetime.now().isoformat(timespec="seconds"),
    }
    (pasta / "info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"No YouTube: https://youtube.com/shorts/{video_id} ({status_final})")
    return info["enviado"]
