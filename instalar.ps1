# Instalador da Fábrica de Shorts (Windows 10/11)
# Instala o que falta, prepara o Python e baixa os modelos. Pode rodar de novo sem problema:
# cada etapa verifica antes se já está feita.
$ErrorActionPreference = "Stop"
$Raiz = $PSScriptRoot
Set-Location $Raiz

function Titulo($t) { Write-Host ""; Write-Host "== $t ==" -ForegroundColor Cyan }
function Ok($t) { Write-Host "  [ok] $t" -ForegroundColor Green }
function Aviso($t) { Write-Host "  [!] $t" -ForegroundColor Yellow }
function Falha($t) { Write-Host ""; Write-Host "ERRO: $t" -ForegroundColor Red; Write-Host "Consulte a seção 'Solução de problemas' do GUIA.md."; exit 1 }

function Instalar-Winget($id, $nome, $escopo) {
    $parametros = @("install", "--id", $id, "-e", "--silent", "--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity")
    if ($escopo) { $parametros += @("--scope", $escopo) }
    Write-Host "  instalando $nome (pode aparecer uma janela pedindo permissão de administrador: clique em Sim)..."
    & winget @parametros | Out-Null
}

Write-Host "Fábrica de Shorts - instalador" -ForegroundColor White
Write-Host "Isso pode levar de 15 a 40 minutos, dependendo da sua internet (são cerca de 10 GB)."

# ---------------------------------------------------------------- 0. verificações
Titulo "Verificando o computador"
$ramGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
$livreGB = [math]::Round((Get-PSDrive ($Raiz.Substring(0, 1))).Free / 1GB)
Write-Host "  memória RAM: $ramGB GB | espaço livre: $livreGB GB"
if ($livreGB -lt 15) { Falha "São necessários pelo menos 15 GB livres no disco." }
if ($ramGB -lt 15) { Aviso "Com menos de 16 GB de RAM, use o modelo leve de roteiro (opção 2 mais abaixo)." }
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Falha "O winget não foi encontrado. Instale o 'Instalador de Aplicativo' pela Microsoft Store e rode de novo."
}
Ok "winget disponível"

# ---------------------------------------------------------------- 1. programas
Titulo "Programas necessários"
$py = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
if (-not (Test-Path $py)) { Instalar-Winget "Python.Python.3.12" "Python 3.12" "user" }
if (-not (Test-Path $py)) { Falha "O Python 3.12 não foi instalado." }
Ok "Python 3.12"

$ffmpeg = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg*" -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $ffmpeg -and -not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { Instalar-Winget "Gyan.FFmpeg" "FFmpeg" $null }
Ok "FFmpeg"

$ollama = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"
if (-not (Test-Path $ollama)) { Instalar-Winget "Ollama.Ollama" "Ollama (IA local)" $null }
if (-not (Test-Path $ollama)) { Falha "O Ollama não foi instalado." }
Ok "Ollama"

# o componente Visual C++ da Microsoft é exigido pela biblioteca de voz (sem ele aparece 'DLL load failed')
$vc = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" -ErrorAction SilentlyContinue
if (-not $vc -or $vc.Bld -lt 33000) { Instalar-Winget "Microsoft.VCRedist.2015+.x64" "Microsoft Visual C++" $null }
Ok "Microsoft Visual C++"

# ---------------------------------------------------------------- 2. ambiente Python
Titulo "Ambiente Python"
if (-not (Test-Path "$Raiz\.venv\Scripts\python.exe")) { & $py -m venv "$Raiz\.venv" }
$vpy = "$Raiz\.venv\Scripts\python.exe"
& $vpy -m pip install --upgrade pip -q
& $vpy -m pip install -r "$Raiz\requirements.txt" -q
if ($LASTEXITCODE -ne 0) { Falha "Não consegui instalar as bibliotecas Python." }
& $vpy -c "import onnxruntime, kokoro_onnx, flask, googleapiclient; print('bibliotecas ok')"
if ($LASTEXITCODE -ne 0) { Falha "As bibliotecas foram instaladas, mas não carregaram (veja 'DLL load failed' no guia)." }
Ok "bibliotecas Python"

# ---------------------------------------------------------------- 3. modelos de voz
Titulo "Voz (Kokoro)"
New-Item -ItemType Directory -Force "$Raiz\modelos" | Out-Null
$base = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
foreach ($arq in @("kokoro-v1.0.onnx", "voices-v1.0.bin")) {
    $dest = "$Raiz\modelos\$arq"
    if (-not (Test-Path $dest) -or (Get-Item $dest).Length -lt 1MB) {
        Write-Host "  baixando $arq..."
        $ProgressPreference = "SilentlyContinue"
        Invoke-WebRequest "$base/$arq" -OutFile $dest -UseBasicParsing
    }
}
Ok "modelos de voz"

# ---------------------------------------------------------------- 4. IA dos roteiros
Titulo "IA dos roteiros (Ollama)"
try { Invoke-RestMethod "http://127.0.0.1:11434/api/version" -TimeoutSec 3 | Out-Null }
catch { Start-Process $ollama -ArgumentList "serve" -WindowStyle Hidden; Start-Sleep 5 }
$modelos = (Invoke-RestMethod "http://127.0.0.1:11434/api/tags").models.name
if (-not ($modelos -contains "gemma3:12b" -or $modelos -contains "qwen2.5:7b")) {
    Write-Host "  Qual modelo de roteiro você quer baixar?"
    Write-Host "    1) Gemma 3 12B - escreve melhor (8 GB, recomendado com 16 GB de RAM)"
    Write-Host "    2) Qwen 2.5 7B - mais leve e mais rápido (4,7 GB)"
    $op = Read-Host "  Digite 1 ou 2 (Enter = 1)"
    $modelo = if ($op -eq "2") { "qwen2.5:7b" } else { "gemma3:12b" }
    Write-Host "  baixando $modelo (pode demorar bastante)..."
    & $ollama pull $modelo
    if ($LASTEXITCODE -ne 0) { Falha "Não consegui baixar o modelo $modelo." }
}
Ok "modelo de roteiro"

# ---------------------------------------------------------------- 5. configuração
Titulo "Configuração"
if (-not (Test-Path "$Raiz\config.json")) { Copy-Item "$Raiz\config.example.json" "$Raiz\config.json"; Ok "config.json criado" } else { Ok "config.json já existe" }

Write-Host ""
Write-Host "Tudo pronto!" -ForegroundColor Green
Write-Host "Agora:"
Write-Host "  1. Dê dois cliques em iniciar.bat (o painel abre no navegador)."
Write-Host "  2. Siga o cartão 'Primeiros passos' do painel (chave do Pixabay e YouTube)."
Write-Host "  3. O passo a passo completo está no GUIA.md."
