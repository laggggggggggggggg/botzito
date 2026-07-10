# 🇵🇹 Bot Rede Tuga

Bot profissional de Discord para a comunidade **Rede Tuga**.

## 🎯 Setup em 3 passos (simplificado!)

> **Apenas precisas de configurar 1 Secret no Railway: `DISCORD_TOKEN`**
> Todo o resto é configurado conversando com o bot.

### 1. Criar o bot no Discord Developer Portal
1. Vai a <https://discord.com/developers/applications> → **New Application**
2. Vai a **Bot** → **Reset Token** e copia o token
3. Liga os **3 Privileged Intents** (Presence, Server Members, Message Content)
4. Vai a **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Permissions: `Administrator` (recomendado para o setup)
   - Abre o URL gerado para convidar o bot

### 2. Deploy no Railway
1. Sobe o código para o GitHub (este repositório)
2. Cria projeto no Railway → **Deploy from GitHub repo** → seleciona o repo
3. Vai a **Variables** e adiciona:
   ```
   DISCORD_TOKEN=coloca_aqui_o_teu_token
   ```
4. **Pronto!** Não precisas de mais nenhum Secret.
5. Define **Root Directory** como `rede-tuga-bot` (se o projeto estiver dentro de subpasta)

### 3. Configurar no Discord
1. No Discord, vai ao teu servidor
2. Executa o comando:
   ```
   /setup
   ```
3. O bot vai:
   - 📂 Criar **4 categorias** com canais (Informações, Comunidade, Suporte, Staff)
   - 🎭 Criar **5 cargos** (Admin, Staff, Ticket Staff, Verificado, Membro)
   - 📜 Publicar painel de regras no #regras
   - 👋 Publicar painel de boas-vindas com botão de verificação
   - 🎫 Publicar painel de tickets no #tickets (7 categorias)
   - 🎭 Publicar painel de auto-roles no #auto-roles
4. Atribui o cargo **👑 Admin** a ti próprio e está pronto!

---

## 📂 Estrutura criada automaticamente

```
📡 Informações (categoria)
├── 📜 regras            ← Painel de regras
├── 📢 anuncios
└── 👋 boas-vindas       ← Painel de verificação

💬 Comunidade (categoria)
├── 💬 geral
├── 🌀 off-topic
├── 💡 sugestoes
└── 🖼️ media

🎫 Suporte (categoria)
├── 🎫 tickets           ← Painel de tickets (7 categorias)
└── 📋 logs              ← Logs (privado)

🛡️ Staff (categoria)
└── 🔒 staff-chat        ← Privado para staff
```

**Cargos criados:**
- 👑 Admin (administrator)
- 🛡️ Staff (kick, ban, mute, manage messages)
- 🎫 Ticket Staff (manage channels for tickets)
- ✅ Verificado
- 🇵🇹 Membro

---

## 🎮 Comandos disponíveis

### Globais (todos os membros)
| Comando | Descrição |
|---|---|
| `/ajuda` | Lista de comandos disponíveis |
| `/ping` | Latência do bot |
| `/info` | Informações técnicas do bot |
| `/sugerir` | Envia sugestão para o canal de sugestões |

### Staff
| Comando | Descrição |
|---|---|
| `/setup` | **🚀 Configura tudo automaticamente** (admin) |
| `/regras` | Reenvia painel de regras |
| `/painel_tickets` | Recria painel de tickets |
| `/painel_boas_vindas` | Recria painel de verificação |
| `/painel_cargos` | Recria painel de auto-roles |
| `/config_autoroles` | Configura cargos do auto-roles (admin) |
| `/embed` | Construtor de anúncios personalizados |
| `/recarregar_regras` | Recarrega regras do JSON |

---

## 🎫 Sistema de tickets — 7 categorias

| Categoria | Emoji | Descrição |
|---|---|---|
| Suporte Geral | 🆘 | Dúvidas gerais sobre o servidor |
| Reportar Player | ⚠️ | Denúncias de jogadores |
| Reclamações Staff | 📢 | Queixas sobre a equipa de moderação |
| Parcerias | 🤝 | Propostas de parceria |
| Apelar Ban | 🔨 | Recursos de bans/mutes |
| Doações / VIP | 💎 | Questões sobre doações |
| Bugs / Sugestões | 🐛 | Reportar bugs ou sugerir melhorias |

### Funcionalidades dos tickets
- ✅ Modal de motivo (mínimo 10 caracteres)
- ✅ Canal privado com permissões restrictiveas
- ✅ Painel de controlo: 🔒 Fechar, 🙋 Reivindicar, 📝 Transcript
- ✅ Transcript automático antes do fecho
- ✅ Anti-duplicados (1 ticket por utilizador)
- ✅ Persistência em JSON (sobrevive a restarts)

---

## 🎨 Personalização

### Regras
Edita `data/regras.json` e depois corre `/recarregar_regras` no Discord.

### Nome do servidor
O bot pergunta o nome durante o `/setup`. Podes reconfigurar executando `/setup` novamente.

### Auto-roles
Após o `/setup`, o painel tem 8 opções (Notificações, Gaming, Música, Arte, Norte, Centro, Sul, Ilhas).
Para atribuir cargos reais a cada opção:
```
/config_autoroles opcao_id:gaming cargo:@Gamer
```
Depois recria o painel com `/painel_cargos`.

### Tema visual (cores)
Edita `config.py` → classe `Cores` para mudar a paleta (default: vermelho/verde/dourado de Portugal).

---

## 🔧 Resolução de problemas

### O bot não fica online
- Verifica que `DISCORD_TOKEN` está correto
- Confirma os 3 Privileged Intents ativos no Discord Developer Portal

### Slash commands não aparecem
- Pode demorar até 1h para comandos globais aparecerem
- Para sync instantâneo, define `GUILD_ID` com o ID do teu servidor nos Secrets

### `/setup` falha com erro de permissões
- Verifica que o bot tem **Administrador** ativo (Definições do servidor > Cargos > Bot)
- O cargo do bot deve estar **no topo** da lista de cargos

### Auto-roles não funcionam
- Usa `/config_autoroles` para configurar cargos para cada opção
- O cargo do bot tem de estar acima dos cargos que vai atribuir

---

## 🚂 Notas sobre Railway Free Tier

- 500 horas/mês grátis
- Auto-restart configurado (10 retries)
- O estado do bot é persistido em `data/config.json` (mas o Railway pode resetar o volume em deploys novos)
- Para persistência real entre deploys, liga um **Volume** ao Railway e monta em `/app/data`

---

**Bom divertimento e boa comunidade! 🇵🇹**
