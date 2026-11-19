# Fábrica de Shorts — Guia passo a passo

A Fábrica de Shorts é um programa que roda **no seu computador** e produz YouTube Shorts sozinho:

- escreve o roteiro com uma IA local;
- grava a narração;
- busca os vídeos de fundo;
- monta tudo com legenda, trilha e efeitos;
- envia para o canal certo depois que você aprova.

Ela vem com 4 formatos de canal prontos:

| Canal | O que faz |
|---|---|
| **Escolha Seu Caminho** | história interativa com escolhas A/B |
| **Fatos Sombrios** | 3 fatos reais e verificados por vídeo |
| **Só 1% Acerta** | quiz com 3 alternativas e contagem regressiva |
| **Contos de 60s** | um conto curto narrado |

Não é preciso pagar mensalidade a nenhuma IA: tudo roda no seu PC. As únicas contas necessárias são gratuitas: Pixabay e Google.

> **Seja honesto consigo mesmo:** o programa produz os vídeos, mas audiência e monetização dependem do YouTube, do nicho e da sua constância. O YouTube pode recusar monetização de conteúdo repetitivo ou produzido em massa. Por isso existe a etapa de revisão: assista antes de aprovar.

---

## 1. Requisitos

- **Sistema:** Windows 10 ou 11, 64 bits.
- **Memória:** 16 GB de RAM recomendados. Com 8 GB funciona usando o modelo leve, que é mais simples.
- **Disco:** cerca de 15 GB livres.
- **Internet:** para a instalação (cerca de 10 GB de downloads) e para os vídeos de fundo.
- **Contas:** uma conta Google (a dona dos canais) e uma conta gratuita no Pixabay.
- **Placa de vídeo:** não é necessária. Com uma placa NVIDIA, a IA dos roteiros fica mais rápida.

## 2. Instalação (um clique)

1. Extraia o .zip numa pasta **sem acentos no caminho**, por exemplo `C:\FabricaShorts`.
2. Dê dois cliques em **`instalar.bat`**.
3. Se o Windows mostrar "O Windows protegeu o computador", clique em **Mais informações → Executar assim mesmo**.
4. Quando aparecer o pedido de permissão de administrador, clique em **Sim**. Isso acontece na instalação do Visual C++ e do Ollama.
5. Quando ele perguntar qual modelo de roteiro baixar, digite **1** (Gemma 3 12B, melhor) ou **2** (Qwen 2.5 7B, para PCs com 8 GB).
6. Espere aparecer **"Tudo pronto!"**.

O instalador baixa e configura sozinho:

- Python 3.12, FFmpeg, Ollama e o Microsoft Visual C++;
- as bibliotecas do programa;
- a voz (Kokoro);
- a IA dos roteiros.

Se der algum erro, pode rodar o `instalar.bat` de novo: ele pula o que já está pronto.

## 3. Abrir o painel e colocar a chave do Pixabay

1. Dê dois cliques em **`iniciar.bat`**. O painel abre no navegador em `http://localhost:5050`.
2. Mantenha a janela preta aberta enquanto usa o painel. Fechar a janela desliga o painel.
3. No topo aparece o cartão **Primeiros passos**, com o que ainda falta.

Os vídeos de fundo vêm do Pixabay, que é grátis:

1. Crie uma conta em <https://pixabay.com>.
2. Logado, abra <https://pixabay.com/api/docs/>.
3. Na seção **Parameters**, item `key`, aparece a sua chave (um código longo). Copie.
4. No painel, cole no campo **"Cole aqui a chave do Pixabay"** e clique em **Salvar**.

Sem a chave, o vídeo funciona, mas o fundo vira um degradê animado.

## 4. Liberar o envio para o YouTube (Google Cloud)

Esta é a parte mais longa, mas só é feita **uma vez**. Ela cria a "autorização" que deixa o programa enviar vídeos para os seus canais. É grátis.

**4.1 Criar o projeto**
1. Abra <https://console.cloud.google.com> com a conta Google dona dos canais e aceite os termos.
2. No topo, clique no seletor de projeto → **Novo projeto** → dê um nome (ex.: `fabrica-shorts`) → **Criar**.
3. Confirme que o projeto novo está selecionado no topo.

**4.2 Ativar a API do YouTube**
1. Abra <https://console.cloud.google.com/apis/library/youtube.googleapis.com>.
2. Clique em **Ativar** (YouTube Data API v3).

**4.3 Tela de consentimento**
1. Menu → **APIs e serviços → Tela de consentimento OAuth** (ou **Google Auth Platform**) → **Começar**.
2. **Nome do app:** `Fábrica de Shorts`. **E-mail de suporte:** o seu.
3. **Público:** **Externo**.
4. **Dados de contato:** o seu e-mail. Aceite a política e clique em **Criar**.
5. Em **Público**, na seção **Usuários de teste**, clique em **Adicionar usuários** e coloque o **seu Gmail** (o dono dos canais).
6. Ainda em **Público**, clique em **Publicar app** → **Confirmar**.
   - **Por que publicar:** em modo "Teste", o Google expira o acesso a cada 7 dias e você teria que reconectar os canais toda semana.
   - Publicar **não** deixa nada público: o app continua só seu.

**4.4 Criar a credencial e colocar na pasta**
1. Menu → **APIs e serviços → Credenciais** (ou **Clientes**) → **Criar credenciais → ID do cliente OAuth**.
2. **Tipo de aplicativo:** **App para computador**. Nome: `Fabrica`. Clique em **Criar**.
3. Clique em **Baixar JSON**.
4. Coloque o arquivo baixado **na pasta da Fábrica**, junto do `painel.py`. O nome dele começa com `client_secret_...json`; não precisa renomear.

> **Este arquivo é seu e é secreto.** Não compartilhe nem publique.

## 5. Criar os canais no YouTube

Cada formato vai para um canal próprio. Todos ficam na mesma conta Google.

1. Abra <https://www.youtube.com/account> → **Adicionar ou gerenciar canais** → **Criar um canal**.
2. Escolha o nome e crie. Repita para os 4 canais. Também dá para usar canais que você já tem.

Se aparecer **"Falha ao criar o canal"**, quase sempre o **nome** está bloqueado ou já é usado por muitos canais. Troque o nome; por exemplo, "Fatos Sombrios" foi recusado e "Arquivo Sombrio" passou. Os canais no painel podem ter nomes diferentes dos canais no YouTube.

**Foto e banner prontos:** o programa gera uma foto de perfil (800×800) e um banner (2560×1440) para cada canal, nas cores de cada um. Para isso:

1. Abra a pasta da Fábrica, clique na barra de endereço, digite `cmd` e tecle Enter.
2. Rode este comando:

```
.venv\Scripts\python -m fabrica.identidade
```

Os arquivos aparecem na pasta `identidade`. Envie pelo YouTube Studio → **Personalização → Branding**.

**Opcional, mas recomendado:** diga ao programa qual é o canal certo de cada formato. Assim ele recusa enviar para o canal errado por engano.

1. No YouTube Studio → **Personalização → Informações básicas**, copie o **ID do canal** (começa com `UC`) e o identificador (`@nome`).
2. Abra o arquivo do formato em `canais` (ex.: `canais\so_1_acerta.json`) no Bloco de Notas.
3. Logo depois da primeira `{`, acrescente a linha abaixo, trocando pelos seus dados:

```
"youtube": {"id": "UCxxxxxxxxxxxxxxxxxxxxxx", "handle": "@SeuCanal"},
```

## 6. Conectar cada canal

1. No painel, escolha o canal na barra lateral.
2. No cartão do YouTube, clique em **Conectar**. O login do Google abre no navegador.
3. Escolha sua conta e, em seguida, **o canal** daquele formato.
4. Vai aparecer **"O Google não verificou este app"**. Isso é normal, porque o app é seu e não passou pela verificação pública. Clique em **Avançado → Acessar Fábrica de Shorts (não seguro)**.
5. Marque as permissões e clique em **Continuar**. Quando o navegador mostrar que terminou, volte ao painel.
6. Repita para os outros 3 canais, sempre escolhendo o canal certo.

O acesso fica salvo na pasta `tokens`. Para trocar de canal, clique em **Desconectar** e conecte de novo.

## 7. Produzir e publicar

1. Escolha o canal, o **tema** (ou deixe sorteado), a **voz** e a **quantidade**.
2. **Revisar o roteiro antes de montar:** se ligado, o vídeo para no roteiro para você ler e editar antes de gastar tempo montando. Os roteiros esperam em **Roteiros para revisar**.
3. Clique em **Gerar Short**.
   - Os vídeos entram numa fila e são produzidos um de cada vez.
   - O tempo depende do PC: de alguns minutos a uns 15 por vídeo.
   - A barra de progresso mostra cada etapa.
4. O vídeo pronto aparece em **Para assistir**. Assista.
5. Se gostou, clique em **✓ Aprovar e enviar**. O vídeo é enviado **público** para o canal conectado, com:
   - título, descrição, tags e hashtags gerados;
   - o aviso de **conteúdo gerado por IA** que o YouTube exige.
6. Se não gostou, clique em **Descartar**. Também dá para **Baixar** o .mp4 e postar à mão (inclusive no TikTok e no Reels).

**Bancos verificados (quiz e fatos).** IA local inventa fatos com facilidade. Por isso, nesses dois canais, as perguntas e os fatos vêm de bancos conferidos:

- `bancos\quiz.json`: 96 perguntas;
- `bancos\fatos.json`: 297 fatos.

A IA escreve só o título, o gancho e a frase final. O programa evita repetir itens já usados.

- **Importar mais perguntas:** o botão **Importar mais** traz perguntas do Open Trivia Database e traduz.
- **Escrever as suas:** você pode acrescentar as suas no mesmo formato dos arquivos.

## 8. Insights

O link **Insights**, na barra lateral, mostra por canal:

- inscritos;
- views dos Shorts;
- ranking dos vídeos;
- gráficos do crescimento dia a dia.

Clique em **Atualizar** para buscar os números. Cada atualização guarda a "foto do dia" no histórico.

## 9. Limites que você precisa conhecer

- **Envios por dia:** a cota grátis da API do YouTube é de 10.000 unidades por dia, e cada envio gasta cerca de 1.600. Isso dá **uns 6 envios por dia somando todos os canais**. A cota zera à meia-noite do horário do Pacífico (umas 4h/5h da manhã no Brasil). Acima disso, use **Baixar** e envie pelo YouTube Studio.
- **Vídeos travados como privados:** o Google pode travar envios de projetos não auditados. Nos nossos testes os vídeos saíram públicos normalmente. Se aparecerem como "Privado (bloqueado)", é preciso pedir a auditoria da API ao Google. O formulário é o "YouTube API Services - Audit and Quota Extension Form".
- **Direitos:** os vídeos do Pixabay são livres para uso comercial. As perguntas importadas do Open Trivia Database são CC BY-SA, e o programa já põe o crédito na descrição. Veja `TERCEIROS.md`.

## 10. Personalizar

Cada canal é um arquivo em `canais\`. Dá para editar no Bloco de Notas:

- `nome`, `descricao` e `cor` (cor do canal no painel e nos vídeos);
- `voz`: `pm_alex` (grave), `pm_santa` (calorosa) ou `pf_dora` (feminina);
- `velocidade` (da narração);
- `categorias`: os temas que aparecem para sortear. Acrescente os seus.

Faça uma cópia do arquivo antes de mexer. Uma vírgula fora do lugar quebra o canal, e o painel não abre.

## 11. Solução de problemas

| Problema | O que fazer |
|---|---|
| "winget não foi encontrado" | Instale o **Instalador de Aplicativo** pela Microsoft Store e rode o `instalar.bat` de novo. |
| "DLL load failed" / a voz não carrega | Falta o Microsoft Visual C++. Rode o `instalar.bat` de novo ou instale em <https://aka.ms/vs/17/release/vc_redist.x64.exe>. |
| Cartão diz "IA dos roteiros" pendente | O Ollama não está aberto. Abra o **Ollama** pelo menu Iniciar e recarregue o painel. |
| A IA é muito lenta ou trava o PC | Use o modelo leve: no `cmd`, rode `ollama pull qwen2.5:7b` e apague o pesado com `ollama rm gemma3:12b`. |
| "FFmpeg não encontrado" | Rode o `instalar.bat` de novo e depois reinicie o computador. |
| Fundo virou degradê | Falta a chave do Pixabay, ou a busca não achou vídeo para o tema. |
| "Arquivo client_secret não encontrado" | O JSON do passo 4.4 não está na mesma pasta do `painel.py`. |
| "O acesso salvo é de outro canal" | Você escolheu o canal errado no login. Clique em **Desconectar** e conecte de novo escolhendo o certo. |
| "Token has been expired or revoked" / invalid_grant | O app ficou em modo Teste (passo 4.3, item 6). Publique o app e reconecte o canal. |
| "Limite diário de envios do YouTube atingido" | A cota acabou (seção 9). Tente amanhã ou envie à mão. |
| "Falha ao criar o canal" no YouTube | Nome bloqueado. Troque o nome (seção 5). |
| "Erro 403" no YouTube Studio | Você está em outro canal da conta. No Studio, clique na foto → **Mudar de conta** → escolha o canal certo. |
| A página do painel não abre | A janela preta do `iniciar.bat` precisa estar aberta. Se ela fechou com erro, tire um print e confira esta tabela. |

---

Bons vídeos!
