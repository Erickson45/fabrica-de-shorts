"""Montagem: junta fundo, camadas, narração e trilha num MP4 vertical com o FFmpeg."""
import glob
import os
import shutil
import subprocess
from pathlib import Path


def ffmpeg():
    achado = shutil.which("ffmpeg")
    if achado:
        return achado
    padrao = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\*\bin\ffmpeg.exe")
    achados = glob.glob(padrao)
    if not achados:
        raise RuntimeError("FFmpeg não encontrado. Instale com: winget install Gyan.FFmpeg")
    return achados[0]


def _rodar(args):
    r = subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("FFmpeg falhou:\n" + r.stderr[-2000:])


SAIDA_VIDEO = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
               "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]


IMPACTO = ("escolha", "ruim", "bom", "final", "fato", "resposta", "climax", "pergunta")
# a abertura precisa ser visível: é ela que segura quem está rolando o feed
CLAREAR = {"gancho": 0.12, "inicio": 0.10, "final": 0.04, "pergunta": 0.06, "resposta": 0.06}
TONS = {  # cor por cena: o caminho ruim puxa pro vermelho, o bom pro azul-esverdeado
    "ruim": "colorbalance=rs=0.22:gs=-0.06:bs=-0.10:rm=0.12:bm=-0.05,",
    "bom": "colorbalance=rs=-0.08:gs=0.03:bs=0.14:bm=0.08,",
    "contagem": "colorbalance=rs=0.12:rm=0.06,",
    "climax": "colorbalance=rs=0.20:gs=-0.05:bs=-0.08:rm=0.10,",
}


def segmento(destino, duracao, camadas, visual, clipes=None, audio=None, tique=False,
             tipo="", inicio_global=0.0, total=0.0):
    """Uma cena: fundo (clipes ou gradiente) com zoom, tremida, flash, cor e cintilação,
    camadas PNG com tempo (legendas sobem ao entrar), barra de progresso e áudio."""
    args, filtros = [], []
    quadros = max(1, int(duracao * 30))
    tremida = "+if(lt(t,0.45),26*sin(t*95)*(0.45-t)/0.45,0)" if tipo in IMPACTO else ""
    if clipes:
        parte = duracao / len(clipes)
        for i, clipe in enumerate(clipes):
            args += ["-stream_loop", "-1", "-i", str(clipe)]
            filtros.append(
                f"[{i}:v]trim=duration={parte + 0.05:.3f},setpts=PTS-STARTPTS,"
                "scale=1188:2112:force_original_aspect_ratio=increase,"
                f"crop=1080:1920:x='(iw-ow)/2+sin(t*0.35)*30{tremida}':y='(ih-oh)/2+cos(t*0.27)*30{tremida}',"
                f"setsar=1,fps=30[c{i}]")
        entradas = "".join(f"[c{i}]" for i in range(len(clipes)))
        filtros.append(f"{entradas}concat=n={len(clipes)}:v=1:a=0[bg]")
        n_fundo = len(clipes)
    else:
        g = visual["gradiente"]
        args += ["-f", "lavfi", "-i",
                 f"gradients=s=1080x1920:c0={g[0]}:c1={g[1]}:c2={g[2]}:nb_colors=3:speed=0.006:r=30:d={duracao:.3f}"]
        filtros.append("[0:v]setsar=1,fps=30[bg]")
        n_fundo = 1
    flash = ("fade=t=in:st=0:d=0.28:color=white" if tipo in IMPACTO
             else "fade=t=in:st=0:d=0.18:color=black")
    filtros.append(
        # aproximação lenta da câmera (push-in) ao longo da cena
        f"[bg]zoompan=z='1+0.09*on/{quadros}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30,"
        # cintilação de luz, como lâmpada falhando
        f"eq=brightness='{visual['escurecer'] + CLAREAR.get(tipo, 0)}+0.022*sin(t*13)*sin(t*3.7)'"
        f":saturation={visual['saturacao']}:contrast=1.08:gamma={1.25 if tipo == 'gancho' else 1.0}"
        f":eval=frame,{visual.get('tom', '')}{TONS.get(tipo, '')}"
        f"vignette=PI/4,noise=alls=9:allf=t,{flash}[f0]")
    atual = "f0"
    for i, camada in enumerate(camadas, start=n_fundo):
        png, ini, fim = camada[:3]
        sobe = len(camada) > 3 and camada[3] == "sobe"
        args += ["-i", str(png)]
        y = f"if(lt(t-{ini:.3f},0.14),(1-(t-{ini:.3f})/0.14)*55,0)" if sobe else "0"
        filtros.append(f"[{atual}][{i}:v]overlay=x=0:y='{y}':enable='between(t,{ini:.3f},{fim:.3f})'[f{i}]")
        atual = f"f{i}"
    if total:  # barra de progresso no topo: segura a pessoa até o fim
        filtros.append(f"[{atual}]drawbox=x=0:y=0:w='iw*({inicio_global:.3f}+t)/{total:.3f}':h=9:"
                       f"color=0xFF3B30@0.95:t=fill[fp]")
        atual = "fp"
    n = n_fundo + len(camadas)
    if audio:
        args += ["-i", str(audio)]
    elif tique:  # contagem: um "tic" seco por segundo
        args += ["-f", "lavfi", "-i",
                 f"aevalsrc='0.55*sin(2*PI*1150*t)*exp(-60*mod(t,1))':s=48000:d={duracao:.3f}"]
    else:
        args += ["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={duracao:.3f}"]
    args += ["-filter_complex", ";".join(filtros), "-map", f"[{atual}]", "-map", f"{n}:a",
             "-t", f"{duracao:.3f}", *SAIDA_VIDEO, str(destino)]
    _rodar(args)


def juntar(segmentos, destino, pasta, trilha=None, efeitos=None):
    """Junta as cenas e mixa: voz + trilha (que abaixa quando a voz fala) + efeitos sonoros."""
    lista = Path(pasta) / "lista.txt"
    lista.write_text("".join(f"file '{Path(s).as_posix()}'\n" for s in segmentos), encoding="utf-8")
    bruto = Path(pasta) / "bruto.mp4"
    _rodar(["-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(bruto)])
    duracao = _duracao(bruto)
    if trilha and efeitos:
        mix = ("[0:a]asplit=2[voz][chave];"
               "[1:a]volume=0.62[mus];"
               # ducking: a música abaixa sozinha quando a voz fala
               "[mus][chave]sidechaincompress=threshold=0.025:ratio=7:attack=15:release=450:makeup=1[musd];"
               "[2:a]volume=0.85[fx];"
               "[voz][musd][fx]amix=inputs=3:duration=first:normalize=0,"
               "loudnorm=I=-14:TP=-1.5:LRA=11[a]")
        entradas = ["-i", str(bruto), "-i", str(trilha), "-i", str(efeitos)]
    else:
        mix = "[0:a]loudnorm=I=-14:TP=-1.5:LRA=11[a]"
        entradas = ["-i", str(bruto)]
    _rodar([*entradas, "-filter_complex", mix, "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(destino)])
    return duracao


def _duracao(arquivo):
    sonda = shutil.which("ffprobe") or str(Path(ffmpeg()).with_name("ffprobe.exe"))
    r = subprocess.run([sonda, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arquivo)],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)
