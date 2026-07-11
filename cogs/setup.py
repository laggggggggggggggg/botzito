"""
Cog de Setup — assistente interativo multi-passos.

Fluxo:
  Passo 1: Modal pede nome do servidor + mensagens customizáveis
  Passo 2: View com 4 select menus + botão confirmar (ativa quando tudo selecionado)
  Passo 3: Executa o setup

O utilizador escolhe:
  • Canal de regras (existente ou criar novo)
  • Canal de boas-vindas (existente, criar novo, ou desativar)
  • Canal de tickets (existente ou criar novo)
  • Categoria onde criar canais de ticket (existente ou criar nova)
  • Mensagem de boas-vindas (customizável)
  • Mensagem do painel de tickets (customizável)
  • Mensagem dentro de cada ticket (customizável)
  • Mensagem do painel de verificação (customizável)
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import (
    Cores,
    Emojis,
    get_config,
    save_config,
)
from utils import embed_aviso, embed_erro, embed_sucesso, log_evento


# Opções especiais para os select menus
CRIAR_NOVO = "novo"
DESATIVAR = "off"


# ─────────────────────────────────────────────────────────────────────────────
# Passo 1 — Modal inicial (nome + mensagens customizáveis)
# ─────────────────────────────────────────────────────────────────────────────
class SetupModal(discord.ui.Modal):
    """Modal inicial — pede nome + 4 mensagens customizáveis."""

    def __init__(self, cog: "SetupCog", guild: discord.Guild) -> None:
        super().__init__(title="🇵🇹 Configurar Bot — Passo 1 de 2", timeout=600)
        self.cog = cog
        self.guild = guild

        cfg = get_config(guild.id)

        # 1. Nome do servidor
        default_nome = (cfg.nome_servidor if cfg.setup_completo else guild.name)[:80]
        self.nome = discord.ui.TextInput(
            label="Nome do servidor no bot",
            placeholder="Ex: Rede Tuga, Comunidade Tuga...",
            default=default_nome,
            max_length=80,
            required=True,
        )
        self.add_item(self.nome)

        # 2. Mensagem de boas-vindas
        self.msg_bem_vindo = discord.ui.TextInput(
            label="👋 Mensagem boas-vindas",
            placeholder="Placeholders: {user} {count} {regras} {tickets}. Deixa vazio = padrão.",
            style=discord.TextStyle.paragraph,
            default=cfg.msg_bem_vindo if cfg.setup_completo and cfg.msg_bem_vindo else "",
            max_length=1000,
            required=False,
        )
        self.add_item(self.msg_bem_vindo)

        # 3. Mensagem do painel de tickets
        self.msg_ticket_panel = discord.ui.TextInput(
            label="🎫 Mensagem painel tickets",
            placeholder="Placeholders: {regras} {categorias}. Deixa vazio = padrão.",
            style=discord.TextStyle.paragraph,
            default=cfg.msg_ticket_panel if cfg.setup_completo and cfg.msg_ticket_panel else "",
            max_length=1000,
            required=False,
        )
        self.add_item(self.msg_ticket_panel)

        # 4. Mensagem dentro de cada ticket criado
        self.msg_ticket_criado = discord.ui.TextInput(
            label="📝 Mensagem dentro do ticket",
            placeholder="Placeholders: {user} {motivo}. Deixa vazio = padrão.",
            style=discord.TextStyle.paragraph,
            default=cfg.msg_ticket_criado if cfg.setup_completo and cfg.msg_ticket_criado else "",
            max_length=1000,
            required=False,
        )
        self.add_item(self.msg_ticket_criado)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Guarda as escolhas temporariamente no cog
        self.cog._wizard_data[interaction.user.id] = {
            "nome_servidor": self.nome.value.strip() or self.guild.name,
            "msg_bem_vindo": self.msg_bem_vindo.value.strip(),
            "msg_ticket_panel": self.msg_ticket_panel.value.strip(),
            "msg_ticket_criado": self.msg_ticket_criado.value.strip(),
        }
        await self.cog.mostrar_selecao_canais(interaction)


# ─────────────────────────────────────────────────────────────────────────────
# Passo 2 — View única com 4 selects + botão confirmar
# ─────────────────────────────────────────────────────────────────────────────
class SelecaoCanaisView(discord.ui.View):
    """View com 4 select menus + botão confirmar (ativa dinamicamente)."""

    def __init__(self, cog: "SetupCog", guild: discord.Guild, user_id: int) -> None:
        super().__init__(timeout=600)
        self.cog = cog
        self.guild = guild
        self.user_id = user_id
        self.escolhas: dict[str, str] = {}

        # Lista canais de texto existentes (até 24)
        canais_texto = list(guild.text_channels[:22])

        # ── 1. Canal de regras ────────────────────────────────────────────
        options_regras = [
            discord.SelectOption(
                label=f"#{c.name}"[:100],
                value=str(c.id),
                description="Canal existente",
                emoji=Emojis.REGRAS,
            )
            for c in canais_texto
        ] + [
            discord.SelectOption(
                label="➕ Criar novo canal",
                value=CRIAR_NOVO,
                description="O bot cria o canal 'regras' automaticamente",
                emoji="➕",
            )
        ]
        self.select_regras = discord.ui.Select(
            placeholder="📜 Canal para o painel de REGRAS",
            options=options_regras,
            min_values=1, max_values=1,
            custom_id="setup:regras",
        )
        self.select_regras.callback = self._on_regras
        self.add_item(self.select_regras)

        # ── 2. Canal de boas-vindas ───────────────────────────────────────
        options_bv = [
            discord.SelectOption(
                label=f"#{c.name}"[:100],
                value=str(c.id),
                description="Canal existente",
                emoji=Emojis.BEM_VINDO,
            )
            for c in canais_texto
        ] + [
            discord.SelectOption(
                label="➕ Criar novo canal",
                value=CRIAR_NOVO,
                description="O bot cria o canal 'boas-vindas' automaticamente",
                emoji="➕",
            ),
            discord.SelectOption(
                label="🚫 Desativar boas-vindas",
                value=DESATIVAR,
                description="Não ativar sistema de boas-vindas",
                emoji="🚫",
            ),
        ]
        self.select_bv = discord.ui.Select(
            placeholder="👋 Canal de BOAS-VINDAS (ou desativar)",
            options=options_bv,
            min_values=1, max_values=1,
            custom_id="setup:bv",
        )
        self.select_bv.callback = self._on_bv
        self.add_item(self.select_bv)

        # ── 3. Canal de tickets ───────────────────────────────────────────
        options_tickets = [
            discord.SelectOption(
                label=f"#{c.name}"[:100],
                value=str(c.id),
                description="Canal existente",
                emoji=Emojis.TICKET,
            )
            for c in canais_texto
        ] + [
            discord.SelectOption(
                label="➕ Criar novo canal",
                value=CRIAR_NOVO,
                description="O bot cria o canal 'tickets' automaticamente",
                emoji="➕",
            )
        ]
        self.select_tickets = discord.ui.Select(
            placeholder="🎫 Canal para o painel de TICKETS",
            options=options_tickets,
            min_values=1, max_values=1,
            custom_id="setup:tickets",
        )
        self.select_tickets.callback = self._on_tickets
        self.add_item(self.select_tickets)

        # ── 4. Categoria para os tickets ──────────────────────────────────
        categorias = list(guild.categories[:24])
        options_cat = [
            discord.SelectOption(
                label=f"📂 {c.name}"[:100],
                value=str(c.id),
                description="Categoria existente",
                emoji="📂",
            )
            for c in categorias
        ] + [
            discord.SelectOption(
                label="➕ Criar nova categoria",
                value=CRIAR_NOVO,
                description="O bot cria a categoria '🎫 Suporte' automaticamente",
                emoji="➕",
            )
        ]
        self.select_cat = discord.ui.Select(
            placeholder="📂 Categoria onde criar canais de ticket",
            options=options_cat,
            min_values=1, max_values=1,
            custom_id="setup:cat",
        )
        self.select_cat.callback = self._on_cat
        self.add_item(self.select_cat)

        # ── Botão confirmar (desativado inicialmente) ─────────────────────
        self.btn_confirmar = discord.ui.Button(
            label="🚀 Confirmar e Executar Setup",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            emoji="🚀",
            row=4,
        )
        self.btn_confirmar.callback = self._on_confirmar
        self.add_item(self.btn_confirmar)

        self.btn_cancelar = discord.ui.Button(
            label="Cancelar",
            style=discord.ButtonStyle.danger,
            emoji="❌",
            row=4,
        )
        self.btn_cancelar.callback = self._on_cancelar
        self.add_item(self.btn_cancelar)

    # ─────────────────────────────────────────────────────────────────────
    # Callbacks dos selects
    # ─────────────────────────────────────────────────────────────────────
    async def _check_user(self, interaction: discord.Interaction) -> bool:
        """Verifica se quem clicou é o utilizador que iniciou o setup E ainda é admin."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ Apenas quem iniciou o `/setup` pode interagir com esta mensagem.",
                ephemeral=True,
            )
            return False
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Precisas de permissão de administrador para continuar.",
                ephemeral=True,
            )
            return False
        return True

    async def _on_regras(self, interaction: discord.Interaction) -> None:
        if not await self._check_user(interaction):
            return
        self.escolhas["regras"] = self.select_regras.values[0]
        await self._atualizar(interaction)

    async def _on_bv(self, interaction: discord.Interaction) -> None:
        if not await self._check_user(interaction):
            return
        self.escolhas["bv"] = self.select_bv.values[0]
        await self._atualizar(interaction)

    async def _on_tickets(self, interaction: discord.Interaction) -> None:
        if not await self._check_user(interaction):
            return
        self.escolhas["tickets"] = self.select_tickets.values[0]
        await self._atualizar(interaction)

    async def _on_cat(self, interaction: discord.Interaction) -> None:
        if not await self._check_user(interaction):
            return
        self.escolhas["cat"] = self.select_cat.values[0]
        await self._atualizar(interaction)

    async def _on_confirmar(self, interaction: discord.Interaction) -> None:
        if not await self._check_user(interaction):
            return
        if len(self.escolhas) < 4:
            await interaction.response.send_message(
                "❌ Precisas de selecionar todos os 4 canais primeiro!",
                ephemeral=True,
            )
            return
        # Desativa a view
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        dados = self.cog._wizard_data.get(self.user_id, {})
        await self.cog.executar_setup(interaction, dados, self.escolhas)

    async def _on_cancelar(self, interaction: discord.Interaction) -> None:
        if not await self._check_user(interaction):
            return
        self.cog._wizard_data.pop(self.user_id, None)
        self.cog._views_ativas.pop(self.user_id, None)
        await interaction.response.edit_message(
            content="❌ Setup cancelado. Executa `/setup` outra vez quando quiseres.",
            embed=None, view=None,
        )

    # ─────────────────────────────────────────────────────────────────────
    # Atualiza preview + estado do botão
    # ─────────────────────────────────────────────────────────────────────
    async def _atualizar(self, interaction: discord.Interaction) -> None:
        dados = self.cog._wizard_data.get(self.user_id, {})

        def status(chave: str, label: str) -> str:
            v = self.escolhas.get(chave)
            if v is None:
                return f"⏳ {label}: *a aguardar seleção...*"
            if v == CRIAR_NOVO:
                return f"✅ {label}: **➕ Criar novo**"
            if v == DESATIVAR:
                return f"✅ {label}: **🚫 Desativado**"
            try:
                canal = self.guild.get_channel(int(v))
                return f"✅ {label}: **{canal.mention if canal else v}**"
            except (ValueError, discord.NotFound):
                return f"✅ {label}: {v}"

        tem_tudo = len(self.escolhas) == 4

        embed = discord.Embed(
            title=f"{Emojis.COROA} Seleção de Canais — Passo 2 de 2",
            description=(
                f"Olá {interaction.user.mention}! Escolhe os canais onde os painéis serão publicados.\n\n"
                f"📊 **Estado das seleções:**\n"
                f"{status('regras', '📜 Regras')}\n"
                f"{status('bv', '👋 Boas-vindas')}\n"
                f"{status('tickets', '🎫 Tickets')}\n"
                f"{status('cat', '📂 Categoria dos tickets')}\n\n"
                + (
                    "✅ **Tudo selecionado!** Clica em **🚀 Confirmar e Executar Setup** abaixo."
                    if tem_tudo
                    else "⏳ Ainda faltam seleções. Continua a escolher nos menus acima."
                )
            ),
            color=Cores.SUCESSO if tem_tudo else Cores.DOURADO,
        )
        embed.set_footer(text=f"{dados.get('nome_servidor', 'Rede Tuga')} • Configuração")

        # Atualiza o estado do botão confirmar
        self.btn_confirmar.disabled = not tem_tudo
        self.btn_confirmar.style = (
            discord.ButtonStyle.success if tem_tudo else discord.ButtonStyle.secondary
        )

        await interaction.response.edit_message(embed=embed, view=self)


# ─────────────────────────────────────────────────────────────────────────────
# Cog principal
# ─────────────────────────────────────────────────────────────────────────────
class SetupCog(commands.Cog):
    """Assistente de configuração do bot — multi-passos."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._wizard_data: dict[int, dict] = {}
        self._views_ativas: dict[int, SelecaoCanaisView] = {}

    @app_commands.command(
        name="setup",
        description="🚀 Configura o Tuguinha — escolhe canais e customiza mensagens (admin).",
    )
    @app_commands.default_permissions(administrator=True)
    async def cmd_setup(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=embed_erro(
                    "Sem permissão",
                    "Precisas de ser **administrador** do servidor para executar o setup.",
                ),
                ephemeral=True,
            )
            return

        if not interaction.guild.me.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=embed_erro(
                    "Bot sem permissões",
                    "O bot precisa de permissão de **Administrador** para fazer o setup.\n"
                    "Vai a `Definições do Servidor > Cargos > [Bot] > Ativar Administrador`.",
                ),
                ephemeral=True,
            )
            return

        cfg = get_config(interaction.guild.id)
        if cfg.setup_completo:
            view = ConfirmarReconfigurarView(self, interaction.guild)
            await interaction.response.send_message(
                embed=embed_aviso(
                    "⚠️ Setup já foi feito",
                    f"O bot já está configurado para **{cfg.nome_servidor}**.\n\n"
                    f"Se quiseres **reconfigurar tudo**, clica em **Reconfigurar**.\n"
                    f"Vai usar canais/cargos existentes quando possível.",
                ),
                view=view,
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(SetupModal(self, interaction.guild))

    async def mostrar_selecao_canais(self, interaction: discord.Interaction) -> None:
        """Passo 2 — mostra view com select menus."""
        dados = self._wizard_data.get(interaction.user.id, {})
        guild = interaction.guild

        view = SelecaoCanaisView(self, guild, interaction.user.id)
        self._views_ativas[interaction.user.id] = view

        embed = discord.Embed(
            title=f"{Emojis.COROA} Seleção de Canais — Passo 2 de 2",
            description=(
                f"Olá {interaction.user.mention}! Escolhe os canais onde os painéis serão publicados.\n\n"
                f"📊 **Estado das seleções:**\n"
                f"⏳ 📜 Regras: *a aguardar seleção...*\n"
                f"⏳ 👋 Boas-vindas: *a aguardar seleção...*\n"
                f"⏳ 🎫 Tickets: *a aguardar seleção...*\n"
                f"⏳ 📂 Categoria dos tickets: *a aguardar seleção...*\n\n"
                f"💡 Quando tiveres escolhido tudo, clica em **🚀 Confirmar e Executar Setup** abaixo."
            ),
            color=Cores.DOURADO,
        )
        embed.set_footer(text=f"{dados.get('nome_servidor', 'Rede Tuga')} • Configuração")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Execução do setup
    # ─────────────────────────────────────────────────────────────────────────
    async def executar_setup(
        self,
        interaction: discord.Interaction,
        dados: dict,
        escolhas: dict,
    ) -> None:
        guild = interaction.guild
        cfg = get_config(guild.id)
        cfg.nome_servidor = dados.get("nome_servidor", guild.name) or guild.name
        cfg.msg_bem_vindo = dados.get("msg_bem_vindo", "")
        cfg.msg_ticket_panel = dados.get("msg_ticket_panel", "")
        cfg.msg_ticket_criado = dados.get("msg_ticket_criado", "")

        bv_escolha = escolhas.get("bv", CRIAR_NOVO)
        cfg.boas_vindas_ativas = bv_escolha != DESATIVAR

        # Mensagem de progresso
        msg = await interaction.followup.send(
            embed=discord.Embed(
                title=f"{Emojis.COROA} Setup em curso...",
                description=f"Olá {interaction.user.mention}! Acompanha o progresso 👇",
                color=Cores.DOURADO,
            ).add_field(name="📋 Tarefas", value="A iniciar...", inline=False),
            wait=True,
        )

        log_passos: list[str] = []

        async def atualizar(passo: str) -> None:
            log_passos.append(passo)
            embed = discord.Embed(
                title=f"{Emojis.COROA} Setup em curso...",
                description=f"Olá {interaction.user.mention}! Acompanha o progresso 👇",
                color=Cores.DOURADO,
            )
            embed.add_field(
                name="📋 Progresso",
                value="\n".join(
                    f"{'✅' if i < len(log_passos) - 1 else '⏳'} {p}"
                    for i, p in enumerate(log_passos)
                ),
                inline=False,
            )
            try:
                await msg.edit(embed=embed)
            except discord.HTTPException:
                pass

        try:
            # 1. Categoria de tickets
            await atualizar("A configurar categoria de tickets...")
            cat_id = escolhas.get("cat", CRIAR_NOVO)
            if cat_id == CRIAR_NOVO:
                categoria = discord.utils.get(guild.categories, name="🎫 Suporte")
                if categoria is None:
                    categoria = await guild.create_category(
                        "🎫 Suporte",
                        reason=f"Setup — {cfg.nome_servidor}",
                    )
                cfg.categoria_tickets = categoria.id
            else:
                cfg.categoria_tickets = int(cat_id)

            # 2. Cargos — NÃO criamos cargos automaticamente.
            # O utilizador decide quais cargos usar para cada função via /editar → Cargos.
            # Por defeito, o bot só responde a admins do Discord (guild_permissions.administrator).
            await atualizar("A configurar permissões (cargos não são criados)...")
            save_config(cfg)

            # 3. Canal de regras
            await atualizar("A configurar canal de regras...")
            regras_id = escolhas.get("regras", CRIAR_NOVO)
            if regras_id == CRIAR_NOVO:
                canal_regras = await self._criar_canal(guild, cfg, "regras", "📜 Regras")
                cfg.canal_regras = canal_regras.id
            else:
                cfg.canal_regras = int(regras_id)

            # 4. Canal de boas-vindas
            if cfg.boas_vindas_ativas:
                await atualizar("A configurar canal de boas-vindas...")
                bv_id = escolhas.get("bv", CRIAR_NOVO)
                if bv_id == CRIAR_NOVO:
                    canal_bv = await self._criar_canal(guild, cfg, "boas-vindas", "👋 Boas-vindas")
                    cfg.canal_bem_vindas = canal_bv.id
                else:
                    cfg.canal_bem_vindas = int(bv_id)

            # 5. Canal de tickets
            await atualizar("A configurar canal de tickets...")
            tickets_id = escolhas.get("tickets", CRIAR_NOVO)
            if tickets_id == CRIAR_NOVO:
                canal_tickets = await self._criar_canal(guild, cfg, "tickets", "🎫 Abrir Ticket")
                cfg.canal_tickets = canal_tickets.id
            else:
                cfg.canal_tickets = int(tickets_id)

            # 6. Canal de logs
            await atualizar("A criar canal de logs...")
            canal_logs = discord.utils.get(guild.text_channels, name="logs")
            if canal_logs is None:
                cat_obj = guild.get_channel(cfg.categoria_tickets) if cfg.categoria_tickets else None
                canal_logs = await guild.create_text_channel(
                    name="logs",
                    topic=f"📋 Logs do servidor • {cfg.nome_servidor}",
                    category=cat_obj if isinstance(cat_obj, discord.CategoryChannel) else None,
                    reason=f"Setup — {cfg.nome_servidor}",
                )
            cfg.canal_logs = canal_logs.id

            # 7. Permissões
            await atualizar("A configurar permissões dos canais...")
            await self._configurar_permissoes(guild, cfg)

            # 8. Painel de regras
            await atualizar("A publicar painel de regras...")
            await self._publicar_regras(guild, cfg)

            # 9. Painel de boas-vindas
            if cfg.boas_vindas_ativas:
                await atualizar("A publicar painel de boas-vindas...")
                await self._publicar_boas_vindas(guild, cfg)
            else:
                await atualizar("Boas-vindas desativadas (a saltar)...")

            # 10. Painel de tickets
            await atualizar("A publicar painel de tickets...")
            await self._publicar_tickets(guild, cfg)

            # 11. Marca como completo
            cfg.setup_completo = True
            save_config(cfg)
            await atualizar("Setup concluído! 🎉")

            # Mensagem final
            embed_final = discord.Embed(
                title=f"{Emojis.VERIFICAR} Setup concluído!",
                description=(
                    f"O bot **{cfg.nome_servidor}** está pronto a usar! 🇵🇹\n\n"
                    f"✅ **Canais configurados:**\n"
                    f"   • 📜 Regras: <#{cfg.canal_regras}>\n"
                    + (f"   • 👋 Boas-vindas: <#{cfg.canal_bem_vindas}>\n" if cfg.boas_vindas_ativas else "   • 👋 Boas-vindas: *desativadas*\n")
                    + f"   • 🎫 Tickets: <#{cfg.canal_tickets}>\n"
                    + f"   • 📋 Logs: <#{cfg.canal_logs}>\n\n"
                    f"ℹ️ **Cargos:** Nenhum cargo foi criado automaticamente.\n"
                    f"Se quiseres que membros da staff (não-admins do Discord) possam responder a tickets,\n"
                    f"usa `/editar` → **Cargos** para configurar quais cargos existentes servem de Staff/Ticket Staff.\n\n"
                    f"🎯 **Próximos passos:**\n"
                    f"• Personaliza as regras em `data/regras.json` se quiseres\n"
                    f"• Configura cargos de staff com `/editar` → **Cargos**\n"
                    f"• Personaliza categorias de tickets com `/editar` → **Categorias de tickets**\n\n"
                    f"Para ver todos os comandos: `/ajuda`"
                ),
                color=Cores.SUCESSO,
            )
            await interaction.channel.send(
                embed=embed_final, content=interaction.user.mention
            )

            await log_evento(
                self.bot,
                f"{Emojis.VERIFICAR} Setup concluído",
                f"Servidor **{guild.name}** configurado com sucesso.",
                Cores.SUCESSO,
                interaction.user,
                guild,
            )

        except discord.Forbidden as e:
            await interaction.channel.send(
                embed=embed_erro(
                    "Sem permissões",
                    f"O bot não tem permissões suficientes. Verifica que tem **Administrador**.",
                    cfg.nome_servidor,
                )
            )
        except Exception as e:
            import uuid as _uuid
            import logging as _logging
            _log = _logging.getLogger("rede_tuga.setup")
            err_id = _uuid.uuid4().hex[:8]
            _log.exception("Erro no setup do guild %s — ID %s", interaction.guild.id, err_id)
            await interaction.channel.send(
                embed=embed_erro(
                    "Erro no setup",
                    f"Algo correu mal. **ID do erro:** `{err_id}`\n\n"
                    f"O que já foi configurado ficou guardado. Podes executar `/setup` novamente.\n\n"
                    f"Se o problema persistir, contacta a staff com o ID do erro.",
                    cfg.nome_servidor,
                )
            )
        finally:
            # Limpa sempre o estado temporário do wizard (evita memory leak/stale)
            self._wizard_data.pop(interaction.user.id, None)
            self._views_ativas.pop(interaction.user.id, None)

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────
    async def _criar_canal(
        self, guild: discord.Guild, cfg, slug: str, nome_amigavel: str
    ) -> discord.TextChannel:
        """Cria um canal de texto na categoria configurada."""
        existente = discord.utils.get(guild.text_channels, name=slug)
        if existente:
            return existente

        cat_obj = guild.get_channel(cfg.categoria_tickets) if cfg.categoria_tickets else None
        return await guild.create_text_channel(
            name=slug,
            topic=f"{nome_amigavel} • {cfg.nome_servidor}",
            category=cat_obj if isinstance(cat_obj, discord.CategoryChannel) else None,
            reason=f"Setup — {cfg.nome_servidor}",
        )

    async def _configurar_permissoes(self, guild: discord.Guild, cfg) -> None:
        """Configura permissões dos canais. Não cria cargos — usa apenas os que o utilizador configurou."""
        # Cargo de staff é opcional — se não estiver configurado, os canais ficam read-only para todos
        cargo_staff = guild.get_role(cfg.cargo_staff) if cfg.cargo_staff else None

        # Canal de regras: read-only para @everyone
        if cfg.canal_regras:
            canal = guild.get_channel(cfg.canal_regras)
            if canal:
                await canal.set_permissions(
                    guild.default_role,
                    send_messages=False, add_reactions=False,
                    view_channel=True, read_message_history=True,
                )
                # Se houver cargo de staff configurado, dá permissão de escrita
                if cargo_staff:
                    await canal.set_permissions(
                        cargo_staff, send_messages=True, manage_messages=True,
                    )

        # Canal de tickets: read-only para @everyone
        if cfg.canal_tickets:
            canal = guild.get_channel(cfg.canal_tickets)
            if canal:
                await canal.set_permissions(
                    guild.default_role,
                    send_messages=False, add_reactions=False,
                    view_channel=True, read_message_history=True,
                )

        # Canal de boas-vindas: read-only para @everyone
        if cfg.canal_bem_vindas:
            canal = guild.get_channel(cfg.canal_bem_vindas)
            if canal:
                await canal.set_permissions(
                    guild.default_role,
                    send_messages=False, add_reactions=False,
                    view_channel=True, read_message_history=True,
                )

        # Canal de logs: privado — só acessível se houver cargo de staff configurado
        if cfg.canal_logs:
            canal = guild.get_channel(cfg.canal_logs)
            if canal:
                await canal.set_permissions(guild.default_role, view_channel=False)
                if cargo_staff:
                    await canal.set_permissions(
                        cargo_staff,
                        view_channel=True, send_messages=True, read_message_history=True,
                    )
                # Caso não haja cargo_staff, o canal fica só acessível a admins do Discord
                # (que têm manage_channels implicitamente)

    # ─────────────────────────────────────────────────────────────────────────
    # Publicação dos painéis
    # ─────────────────────────────────────────────────────────────────────────
    async def _publicar_regras(self, guild: discord.Guild, cfg) -> None:
        canal = guild.get_channel(cfg.canal_regras)
        if canal is None:
            return
        from cogs.regras import construir_embeds_regras
        guild_icon = guild.icon.url if guild.icon else None
        embeds = construir_embeds_regras(guild_icon, cfg.nome_servidor)
        try:
            async for m in canal.history(limit=20):
                if m.author == guild.me:
                    await m.delete()
        except discord.HTTPException:
            pass
        for i in range(0, len(embeds), 10):
            await canal.send(embeds=embeds[i:i + 10])

    async def _publicar_boas_vindas(self, guild: discord.Guild, cfg) -> None:
        """Publica uma mensagem de boas-vindas no canal (sem botão de verificação)."""
        canal = guild.get_channel(cfg.canal_bem_vindas)
        if canal is None:
            return
        # Apaga mensagens anteriores do bot (evita duplicação em re-setup)
        try:
            async for m in canal.history(limit=20):
                if m.author == guild.me:
                    await m.delete()
        except discord.HTTPException:
            pass
        # Apenas envia uma embed informativa — sem botão de verificação
        embed = discord.Embed(
            title=f"{Emojis.BEM_VINDO} Bem-vindo à {cfg.nome_servidor}! 🇵🇹",
            description=(
                f"Este é o canal de boas-vindas! Quando um novo membro entrar no servidor, "
                f"receberá aqui uma mensagem personalizada.\n\n"
                f"📋 **Para começar:**\n"
                f"➡️ Lê as regras em <#{cfg.canal_regras}>\n"
                f"➡️ Se precisares de ajuda, abre um ticket em <#{cfg.canal_tickets}>\n\n"
                f"💡 *A staff pode personalizar a mensagem de boas-vindas com `/editar`.*"
            ),
            color=Cores.VERMELHO,
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=f"{cfg.nome_servidor} • Canal de Boas-vindas")
        await canal.send(embed=embed)

    async def _publicar_tickets(self, guild: discord.Guild, cfg) -> None:
        canal = guild.get_channel(cfg.canal_tickets)
        if canal is None:
            return
        from cogs.tickets import PainelTicketsView
        from config import CATEGORIAS_TICKET_DEFAULT
        cog_tickets = self.bot.get_cog("TicketsCog")
        if cog_tickets is None:
            # TicketsCog não carregou — usa instância temporária só para a view
            # (não interfere com a cog real porque a view só guarda referência ao cog)
            from cogs.tickets import TicketsCog
            cog_tickets = TicketsCog.__new__(TicketsCog)
            cog_tickets.bot = self.bot

        categorias = cfg.get_categorias_ticket()

        # Constrói a lista de categorias para o embed
        lista_categorias = "\n".join(
            f"• {c.get('emoji', '📌')} **{c['nome']}** — {c.get('descricao', '')}"
            for c in categorias
        )

        msg = cfg.get_msg_ticket_panel()
        msg = msg.replace("{regras}", f"<#{cfg.canal_regras}>")
        msg = msg.replace("{categorias}", lista_categorias)

        embed = discord.Embed(
            title=f"{Emojis.TICKET} {cfg.nome_servidor} — Ticket System",
            description=msg,
            color=Cores.VERMELHO,
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=f"{cfg.nome_servidor} • Sistema de Tickets")
        await canal.send(embed=embed, view=PainelTicketsView(cog_tickets, categorias))


# ─────────────────────────────────────────────────────────────────────────────
# View para reconfigurar
# ─────────────────────────────────────────────────────────────────────────────
class ConfirmarReconfigurarView(discord.ui.View):
    def __init__(self, cog: "SetupCog", guild: discord.Guild) -> None:
        super().__init__(timeout=120)
        self.cog = cog
        self.guild = guild

    @discord.ui.button(label="Reconfigurar", emoji="🔄", style=discord.ButtonStyle.danger)
    async def reconfigurar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(SetupModal(self.cog, self.guild))

    @discord.ui.button(label="Cancelar", emoji="❌", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="❌ Cancelado.", embed=None, view=None)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SetupCog(bot))
