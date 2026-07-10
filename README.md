# 🇵🇹 Bot Rede Tuga

Bot profissional de Discord para a comunidade **Rede Tuga**.

## 🎯 Setup em 3 passos

> **Apenas 1 Secret obrigatório no Railway: `DISCORD_TOKEN`**

### 1. Criar o bot no Discord Developer Portal
1. Vai a <https://discord.com/developers/applications> → **New Application**
2. Vai a **Bot** → **Reset Token** e copia o token
3. Liga os **3 Privileged Intents** (Presence, Server Members, Message Content)
4. Vai a **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Administrator` (recomendado)
   - Abre o URL para convidar o bot

### 2. Deploy no Railway
1. Sobe o código para o GitHub (este repositório — **ficheiros na raiz**, sem subpasta!)
2. Cria projeto no Railway → **Deploy from GitHub repo**
3. Vai a **Variables** e adiciona apenas:
   ```
   DISCORD_TOKEN=coloca_aqui_o_teu_token
   ```
4. **Pronto!** O Railway detecta Python automaticamente.

> ⚠️ **Importante:** Os ficheiros `main.py`, `requirements.txt`, etc. devem estar **na raiz do repositório** — não dentro de uma subpasta. Caso contrário o Railway não consegue encontrar o `main.py`.

### 3. Configurar no Discord — `/setup` wizard interativo
No Discord, executa `/setup` e segue o wizard:

**Passo 1 — Modal pede:**
- Nome do servidor no bot
- Mensagem de boas-vindas customizada (com placeholders `{user}`, `{count}`, `{regras}`, `{tickets}`)
- Mensagem do painel de tickets (`{regras}`)
- Mensagem dentro de cada ticket criado (`{user}`, `{motivo}`)
- Mensagem do painel de verificação (`{server}`, `{tickets}`)
- *(deixa vazio qualquer campo para usar o template padrão)*

**Passo 2 — Seleção de canais com menus:**
- 📜 **Canal de regras** → escolhe um existente ou "➕ Criar novo"
- 👋 **Canal de boas-vindas** → escolhe existente, "➕ Criar novo", ou "🚫 Desativar"
- 🎫 **Canal de tickets** → escolhe um existente ou "➕ Criar novo"
- 📂 **Categoria dos tickets** → escolhe uma existente ou "➕ Criar nova"

**Passo 3 — Confirmar:**
- Quando os 4 selects estão preenchidos, o botão **🚀 Confirmar e Executar Setup** fica verde
- O bot executa o setup com progresso em tempo real (✅/⏳)

---

## 📋 O que o `/setup` cria automaticamente

**Canais (se escolheres "Criar novo"):**
- 📜 `regras` — Painel de regras (read-only)
- 👋 `boas-vindas` — Painel de verificação (read-only)
- 🎫 `tickets` — Painel de tickets com 7 categorias (read-only)
- 📋 `logs` — Logs do servidor (privado para staff)
- 📂 `🎫 Suporte` — Categoria para os tickets

**Cargos:**
- 👑 Admin (administrator)
- 🛡️ Staff (kick, ban, mute, manage messages)
- 🎫 Ticket Staff (manage channels for tickets)
- ✅ Verificado
- 🇵🇹 Membro

**Painéis publicados:**
- 📜 Painel de regras (10 embeds com 8 secções)
- 👋 Painel de boas-vindas + botão de verificação
- 🎫 Painel de tickets (7 categorias)
- 🎭 Painel de auto-roles (opcional)

---

## 🎮 Comandos disponíveis

### Globais
| Comando | Descrição |
|---|---|
| `/ajuda` | Lista de comandos |
| `/ping` | Latência do bot |
| `/info` | Informações técnicas |

### Staff
| Comando | Descrição |
|---|---|
| `/setup` | **🚀 Wizard de configuração completo** |
| `/regras` | Reenvia painel de regras |
| `/painel_tickets` | Recria painel de tickets |
| `/painel_boas_vindas` | Recria painel de verificação |
| `/painel_cargos` | Recria painel de auto-roles |
| `/config_autoroles` | Configura cargos do auto-roles |
| `/embed` | Construtor de anúncios |
| `/recarregar_regras` | Recarrega regras do JSON |

---

## 🎫 Sistema de tickets — 7 categorias

| Categoria | Emoji | Descrição |
|---|---|---|
| Suporte Geral | 🆘 | Dúvidas gerais |
| Reportar Player | ⚠️ | Denúncias |
| Reclamações Staff | 📢 | Queixas sobre staff |
| Parcerias | 🤝 | Propostas de parceria |
| Apelar Ban | 🔨 | Recursos de bans |
| Doações / VIP | 💎 | Questões de doações |
| Bugs / Sugestões | 🐛 | Bugs e sugestões |

Funcionalidades: modal de motivo, canal privado, painel de controlo (🔒 Fechar, 🙋 Reivindicar, 📝 Transcript), transcript automático, anti-duplicados.

---

## 🎨 Personalização

### Placeholders nas mensagens customizadas

Quando executares `/setup`, podes usar estes placeholders:

| Placeholder | Onde | É substituído por |
|---|---|---|
| `{user}` | Boas-vindas, Ticket criado | Menção do utilizador |
| `{count}` | Boas-vindas | Nº de membros do servidor |
| `{regras}` | Boas-vindas, Ticket panel | Menção do canal de regras |
| `{tickets}` | Boas-vindas, Verificação | Menção do canal de tickets |
| `{motivo}` | Ticket criado | Motivo que o utilizador deu |
| `{server}` | Verificação | Nome do servidor |

### Regras
Edita `data/regras.json` e corre `/recarregar_regras`.

### Auto-roles
Após o `/setup`, configura cargos com:
```
/config_autoroles opcao_id:gaming cargo:@Gamer
```
Depois recria o painel com `/painel_cargos`.

---

## 🔧 Resolução de problemas

### `python: can't open file '/app/main.py'`
Os ficheiros estão dentro de uma subpasta. Solução:
- **OU** move os ficheiros para a raiz do repositório
- **OU** no Railway → Settings → **Root Directory** = `rede-tuga-bot`

### Slash commands não aparecem
- Pode demorar até 1h para comandos globais
- Para sync instantâneo, define `GUILD_ID` com o ID do servidor

### `/setup` falha com "Sem permissões"
- O bot precisa de **Administrador** (Definições > Cargos > Bot)
- O cargo do bot deve estar no topo da lista

### `overwrites parameter expects a dict`
Já corrigido nesta versão. Atualiza o código.

---

**🇵🇹 Rede Tuga — Bot de Gestão de Comunidade**
