"""
Cog de Tickets — sistema completo com dropdown (select menu) e categorias customizáveis.

Funcionalidades:
  • Painel com select menu (estilo NoLimits)
  • Categorias customizáveis (admin cria com nome, emoji, descrição)
  • Lista de categorias visível no embed
  • Modal de motivo ao selecionar categoria
  • Criação de canal privado com permissões restrictiveas
  • Painel de controlo dentro do ticket (fechar, reivindicar, transcript)
  • Persistência do estado em JSON (survive a restarts no Railway)
  • Logs de todas as ações
"""
from __future__ import annotations

import asyncio
import io
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import Cores, Emojis, TICKETS_FILE, get_config
from utils import (
    carregar_json,
    embed_aviso,
    embed_erro,
    embed_sucesso,
    e_admin,
    e_staff,
    guardar_json,
    log_evento,
    mention_canal_regras,
)


# ─────────────────────────────────────────────────────────────────────────────
# Modal de motivo — gera campos dinamicamente com base na categoria
# ─────────────────────────────────────────────────────────────────────────────
class MotivoTicketModal(discord.ui.Modal):
    def __init__(self, categoria: dict, cog: "TicketsCog") -> None:
        titulo = f"{categoria.get('emoji', '🎫')} {categoria['nome']}"[:45]
        super().__init__(title=titulo, timeout=300)
        self.categoria = categoria
        self.cog = cog
        self._campos_inputs: list[tuple[str, discord.ui.TextInput]] = []

        # Campo 1: SEMPRE o nome do jogador (pedido em todas as categorias)
        nome_input = discord.ui.TextInput(
            label="👤 O teu nome no jogo",
            placeholder="Ex: RicardoPT, JoãoZão...",
            style=discord.TextStyle.short,
            min_length=2,
            max_length=100,
            required=True,
        )
        self.add_item(nome_input)
        self._campos_inputs.append(("nome_jogador", nome_input))

        # Campos customizados da categoria (máximo 4 extra — total 5 com o nome)
        campos_cat = categoria.get("campos", [])[:4]
        for campo in campos_cat:
            style = discord.TextStyle.paragraph if campo.get("style", "short") == "paragraph" else discord.TextStyle.short
            input_item = discord.ui.TextInput(
                label=campo["label"][:45],
                placeholder=campo.get("placeholder", "")[:100],
                style=style,
                min_length=2 if campo.get("required", True) else 0,
                max_length=campo.get("max_length", 1000),
                required=campo.get("required", True),
            )
            self.add_item(input_item)
            self._campos_inputs.append((campo.get("key", f"campo_{len(self._campos_inputs)}"), input_item))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Recolhe todos os valores num dict
        respostas: dict[str, str] = {}
        for key, input_item in self._campos_inputs:
            respostas[key] = input_item.value.strip()
        # Chama criar_ticket com o dict de respostas
        await self.cog.criar_ticket(interaction, self.categoria, respostas)


# ─────────────────────────────────────────────────────────────────────────────
# Painel principal de tickets — BOTÃO "Criar Ticket" (abre select menu)
# ─────────────────────────────────────────────────────────────────────────────
class PainelTicketsView(discord.ui.View):
    """View persistente com botão 'Criar Ticket'.

    Fluxo:
    1. Utilizador clica em "Criar Ticket"
    2. Botão responde efemeramente com uma nova view contendo o select menu
    3. Utilizador seleciona a categoria no select menu
    4. Modal abre com os campos específicos da categoria
    """

    def __init__(self, cog: "TicketsCog", categorias: list[dict] = None) -> None:
        super().__init__(timeout=None)
        self.cog = cog
        # Se não forem passadas categorias, usa defaults
        if categorias is None:
            from config import CATEGORIAS_TICKET_DEFAULT
            categorias = CATEGORIAS_TICKET_DEFAULT
        self.categorias = categorias

    @discord.ui.button(
        label="Criar Ticket",
        emoji="🎫",
        style=discord.ButtonStyle.success,
        custom_id="rede_tuga:ticket_criar",
    )
    async def btn_criar_ticket(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Abre o select menu com as categorias de ticket."""
        cfg = get_config(interaction.guild.id)

        # Verifica se o utilizador já tem ticket aberto (feedback rápido)
        estado = carregar_json(TICKETS_FILE, {"tickets": {}})
        for tid, t in estado.get("tickets", {}).items():
            if t.get("user_id") == interaction.user.id and t.get("aberto"):
                canal_existente = interaction.guild.get_channel(t.get("canal_id", 0))
                if canal_existente:
                    await interaction.response.send_message(
                        embed=embed_aviso(
                            "Já tens ticket aberto",
                            f"Já tens um ticket ativo: {canal_existente.mention}. "
                            f"Fecha-o antes de abrir outro.",
                            cfg.nome_servidor,
                        ),
                        ephemeral=True,
                    )
                    return

        # Cria view efémera com o select menu
        view = SelecaoCategoriaView(self.cog, self.categorias, interaction.user.id)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🎫 Escolhe a categoria",
                description=(
                    "Seleciona no menu abaixo o tipo de ticket que queres abrir.\n\n"
                    "⚠️ **Antes de abrir ticket:**\n"
                    "➡️ Lê as regras para garantir que a tua dúvida não é resolvida lá.\n"
                    "➡️ Não abras tickets por brincadeira.\n"
                    "➡️ Mantém o respeito com a staff."
                ),
                color=Cores.DOURADO,
            ),
            view=view,
            ephemeral=True,
        )


class SelecaoCategoriaView(discord.ui.View):
    """View efémera com o select menu de categorias (aparece após clicar em 'Criar Ticket')."""

    def __init__(self, cog: "TicketsCog", categorias: list[dict], user_id: int) -> None:
        super().__init__(timeout=300)  # 5 minutos para escolher
        self.cog = cog
        self.user_id = user_id
        self.categorias = categorias

        options = []
        for cat in categorias[:25]:
            options.append(
                discord.SelectOption(
                    label=cat["nome"][:100],
                    value=cat["id"],
                    description=cat.get("descricao", "")[:100],
                    emoji=cat.get("emoji"),
                )
            )

        select = discord.ui.Select(
            placeholder="🎫 Seleciona o tipo de ticket...",
            min_values=1,
            max_values=1,
            options=options,
        )
        select.callback = self._on_select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        # Apenas quem clicou em "Criar Ticket" pode selecionar
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ Esta seleção é apenas para quem clicou em 'Criar Ticket'.",
                ephemeral=True,
            )
            return

        cog = self.cog

        # Encontra a categoria selecionada
        cat_id = interaction.data["values"][0]
        cfg = get_config(interaction.guild.id)
        categoria = next(
            (c for c in cfg.get_categorias_ticket() if c["id"] == cat_id), None
        )
        if categoria is None:
            await interaction.response.send_message(
                embed=embed_erro(
                    "Categoria inválida",
                    "Essa categoria não existe. Contacta a staff.",
                    cfg.nome_servidor,
                ),
                ephemeral=True,
            )
            return

        # Verifica ticket aberto (com lock para evitar race condition)
        async with cog._ticket_lock:
            estado = carregar_json(TICKETS_FILE, {"tickets": {}})
            for tid, t in estado.get("tickets", {}).items():
                if t.get("user_id") == interaction.user.id and t.get("aberto"):
                    canal_existente = interaction.guild.get_channel(t.get("canal_id", 0))
                    if canal_existente:
                        await interaction.response.send_message(
                            embed=embed_aviso(
                                "Já tens ticket aberto",
                                f"Já tens um ticket ativo: {canal_existente.mention}. "
                                f"Fecha-o antes de abrir outro.",
                                cfg.nome_servidor,
                            ),
                            ephemeral=True,
                        )
                        return

        # Abre o modal com os campos da categoria
        await interaction.response.send_modal(MotivoTicketModal(categoria, cog))


# ─────────────────────────────────────────────────────────────────────────────
# Painel de controlo dentro do ticket
# ─────────────────────────────────────────────────────────────────────────────
class ControloTicketView(discord.ui.View):
    def __init__(self, cog: "TicketsCog", dono_id: int) -> None:
        super().__init__(timeout=None)
        self.cog = cog
        self.dono_id = dono_id

    @discord.ui.button(
        label="Fechar Ticket",
        emoji=Emojis.FECHAR,
        style=discord.ButtonStyle.danger,
        custom_id="rede_tuga:ticket_fechar",
    )
    async def fechar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Se dono_id == 0 (view persistente após restart), procura o dono real no JSON
        dono_real = self.dono_id
        if dono_real == 0 and isinstance(interaction.channel, discord.TextChannel):
            estado = carregar_json(TICKETS_FILE, {"tickets": {}})
            for tid, t in estado.get("tickets", {}).items():
                if t.get("canal_id") == interaction.channel.id and t.get("aberto"):
                    dono_real = t.get("user_id", 0)
                    break

        if interaction.user.id != dono_real and not e_staff(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro(
                    "🚫 Sem permissão",
                    "Apenas o dono do ticket ou a staff pode fechá-lo.",
                    get_config(interaction.guild.id).nome_servidor,
                ),
                ephemeral=True,
            )
            return
        await self.cog.fechar_ticket(interaction)

    @discord.ui.button(
        label="Reivindicar",
        emoji="🙋",
        style=discord.ButtonStyle.primary,
        custom_id="rede_tuga:ticket_reivindicar",
    )
    async def reivindicar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not e_staff(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro(
                    "Sem permissão",
                    "Apenas a staff pode reivindicar tickets.",
                    get_config(interaction.guild.id).nome_servidor,
                ),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=embed_sucesso(
                "Ticket reivindicado!",
                f"{interaction.user.mention} vai tratar deste ticket. Obrigado! 🙌",
                get_config(interaction.guild.id).nome_servidor,
            )
        )

    @discord.ui.button(
        label="Transcript",
        emoji=Emojis.TRANSCRIPT,
        style=discord.ButtonStyle.secondary,
        custom_id="rede_tuga:ticket_transcript",
    )
    async def transcript(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not e_staff(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro(
                    "Sem permissão",
                    "Apenas a staff pode gerar transcripts.",
                    get_config(interaction.guild.id).nome_servidor,
                ),
                ephemeral=True,
            )
            return
        await self.cog.gerar_transcript(interaction)


# ─────────────────────────────────────────────────────────────────────────────
# View de confirmação de fecho
# ─────────────────────────────────────────────────────────────────────────────
class ConfirmarFechoView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=30)
        self.confirmado: bool = False

    @discord.ui.button(label="Confirmar", emoji="✅", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.confirmado = True
        self.stop()
        await interaction.response.edit_message(view=None)

    @discord.ui.button(label="Cancelar", emoji="❌", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.confirmado = False
        self.stop()
        await interaction.response.edit_message(view=None)


# ─────────────────────────────────────────────────────────────────────────────
# View de feedback com estrelas (apenas visual — não guarda nada)
# ─────────────────────────────────────────────────────────────────────────────
class FeedbackStarsView(discord.ui.View):
    """View com 5 botões de estrelas para feedback pós-ticket (apenas visual)."""

    def __init__(self, user_id: int, nome_servidor: str) -> None:
        super().__init__(timeout=None)  # persistente enquanto o bot estiver online
        self.user_id = user_id
        self.nome_servidor = nome_servidor

    async def _handle_star(self, interaction: discord.Interaction, n_estrelas: int) -> None:
        # Apenas o dono do ticket pode interagir.
        # Se user_id == 0 (view persistente após restart), aceita qualquer um
        # (a avaliação é só visual e não é guardada, não há risco de abuso)
        if self.user_id != 0 and interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ Esta mensagem é apenas para quem abriu o ticket.",
                ephemeral=True,
            )
            return
        # Atualiza a embed com as estrelas selecionadas
        estrelas = "⭐" * n_estrelas + "🖤" * (5 - n_estrelas)
        mensagens = {
            1: "Obrigado pelo teu feedback. Lamentamos a má experiência — vamos melhorar! 💪",
            2: "Obrigado pelo feedback. Há coisas a melhorar, vamos trabalhar nisso! 🛠️",
            3: "Obrigado! Ficamos contentes que tenha sido razoável. 😊",
            4: "Muito obrigado! Estamos felizes que tiveste uma boa experiência! 🎉",
            5: "Obrigado pela avaliação máxima! Ficamos super felizes! 🥳🇵🇹",
        }
        embed = discord.Embed(
            title="⭐ Obrigado pelo teu feedback!",
            description=(
                f"Olá {interaction.user.mention}!\n\n"
                f"A tua avaliação do atendimento na **{self.nome_servidor}**:\n\n"
                f"# {estrelas}\n\n"
                f"{mensagens.get(n_estrelas, 'Obrigado!')}\n\n"
                f"*— Tuguinha 🇵🇹*"
            ),
            color=0xFFD700,  # dourado
        )
        embed.set_footer(text="Tuguinha • Rede Tuga 🇵🇹")
        # Desativa todos os botões
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="1", emoji="⭐", style=discord.ButtonStyle.secondary, custom_id="tuguinha:fb_1")
    async def star1(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._handle_star(interaction, 1)

    @discord.ui.button(label="2", emoji="⭐", style=discord.ButtonStyle.secondary, custom_id="tuguinha:fb_2")
    async def star2(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._handle_star(interaction, 2)

    @discord.ui.button(label="3", emoji="⭐", style=discord.ButtonStyle.secondary, custom_id="tuguinha:fb_3")
    async def star3(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._handle_star(interaction, 3)

    @discord.ui.button(label="4", emoji="⭐", style=discord.ButtonStyle.secondary, custom_id="tuguinha:fb_4")
    async def star4(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._handle_star(interaction, 4)

    @discord.ui.button(label="5", emoji="⭐", style=discord.ButtonStyle.secondary, custom_id="tuguinha:fb_5")
    async def star5(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._handle_star(interaction, 5)


# ─────────────────────────────────────────────────────────────────────────────
# Cog principal
# ─────────────────────────────────────────────────────────────────────────────
class TicketsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Lock para evitar race conditions na criação de tickets (contador + check de duplicados)
        self._ticket_lock = asyncio.Lock()
        # Regista views persistentes
        from config import CATEGORIAS_TICKET_DEFAULT
        self.bot.add_view(PainelTicketsView(self, CATEGORIAS_TICKET_DEFAULT))
        # Regista ControloTicketView para persistência (dono_id=0 placeholder)
        self.bot.add_view(ControloTicketView(self, 0))
        # Regista FeedbackStarsView para persistência (user_id=0 placeholder)
        self.bot.add_view(FeedbackStarsView(0, "Rede Tuga"))

    @app_commands.command(
        name="painel_tickets",
        description="🎫 Cria o painel de tickets com select menu (admin).",
    )
    @app_commands.default_permissions(administrator=True)
    async def painel_tickets(self, interaction: discord.Interaction) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro(
                    "🚫 Sem permissão",
                    "Apenas **administradores** podem usar este comando.",
                    get_config(interaction.guild.id).nome_servidor,
                ),
                ephemeral=True,
            )
            return

        cfg = get_config(interaction.guild.id)
        categorias = cfg.get_categorias_ticket()

        # Constrói a lista de categorias para o embed
        lista_categorias = "\n".join(
            f"• {c.get('emoji', '📌')} **{c['nome']}** — {c.get('descricao', '')}"
            for c in categorias
        )

        # Substitui placeholders na mensagem customizada do painel
        msg = cfg.get_msg_ticket_panel()
        msg = msg.replace("{regras}", mention_canal_regras(cfg))
        msg = msg.replace("{categorias}", lista_categorias)

        embed = discord.Embed(
            title=f"{Emojis.TICKET} {cfg.nome_servidor} — Ticket System",
            description=msg,
            color=Cores.VERMELHO,
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=f"{cfg.nome_servidor} • Sistema de Tickets")

        view = PainelTicketsView(self, categorias)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            embed=embed_sucesso(
                "Painel criado!",
                f"Painel de tickets publicado neste canal com **{len(categorias)}** categorias.",
                cfg.nome_servidor,
            ),
            ephemeral=True,
        )

        await log_evento(
            self.bot,
            f"{Emojis.TICKET} Painel de tickets criado",
            f"Criado por {interaction.user.mention} em {interaction.channel.mention}.\n"
            f"Categorias: {len(categorias)}",
            Cores.VERDE,
            interaction.user,
            interaction.guild,
        )

    async def criar_ticket(
        self, interaction: discord.Interaction, categoria: dict, respostas: dict
    ) -> None:
        """Cria um ticket com base nas respostas do modal.

        Args:
            interaction: Interação do modal
            categoria: Dict da categoria (com campos)
            respostas: Dict com as respostas {key: valor} — ex: {"nome_jogador": "Ricardo", "membro_acusado": "João"}
        """
        guild = interaction.guild
        if guild is None:
            return

        cfg = get_config(guild.id)
        parent = None
        if cfg.categoria_tickets:
            parent = guild.get_channel(cfg.categoria_tickets)

        # Sanitiza nome do canal: usa o nome do jogador se disponível, senão o username
        import re as _re
        nome_jogador = respostas.get("nome_jogador", "")
        if nome_jogador:
            nome_user = _re.sub(r"[^a-zA-Z0-9]", "", nome_jogador).lower()[:20] or "user"
        else:
            nome_user = _re.sub(r"[^a-zA-Z0-9]", "", interaction.user.name).lower()[:20] or "user"
        cat_id_safe = _re.sub(r"[^a-z0-9_]", "", categoria["id"])[:20]
        nome_canal = f"ticket-{cat_id_safe}-{nome_user}"[:50]

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_channels=True,
                read_message_history=True, attach_files=True, embed_links=True,
            ),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
                attach_files=True, embed_links=True,
            ),
        }

        for cargo_id in (cfg.cargo_ticket_staff, cfg.cargo_staff):
            if not cargo_id:
                continue
            cargo = guild.get_role(cargo_id)
            if cargo:
                overwrites[cargo] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True,
                    read_message_history=True, manage_messages=True,
                )

        try:
            canal = await guild.create_text_channel(
                name=nome_canal,
                topic=(
                    f"Ticket de {interaction.user.id} • "
                    f"Categoria: {categoria['nome']}"
                ),
                overwrites=overwrites,
                category=parent if isinstance(parent, discord.CategoryChannel) else None,
                reason=f"Ticket aberto — {categoria['nome']}",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=embed_erro(
                    "Sem permissões",
                    "O bot não tem permissão para criar canais. Verifica as permissões.",
                    cfg.nome_servidor,
                ),
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            await interaction.response.send_message(
                embed=embed_erro(
                    "Erro",
                    "Não foi possível criar o canal. Tenta novamente.",
                    cfg.nome_servidor,
                ),
                ephemeral=True,
            )
            return

        # Incrementa contador dentro do LOCK (evita race condition com IDs duplicados)
        save_ok = False
        async with self._ticket_lock:
            estado = carregar_json(TICKETS_FILE, {"tickets": {}, "contador": 0})
            contador = estado.get("contador", 0) + 1
            ticket_id = f"#{contador:04d}"
            estado["tickets"][ticket_id] = {
                "id": ticket_id,
                "canal_id": canal.id,
                "guild_id": guild.id,
                "user_id": interaction.user.id,
                "categoria": categoria["id"],
                "categoria_label": categoria["nome"],
                "respostas": respostas,  # dict com todas as respostas do modal
                "aberto": True,
                "criado_em": datetime.now(timezone.utc).isoformat(),
                "criado_por": str(interaction.user),
            }
            estado["contador"] = contador
            save_ok = guardar_json(TICKETS_FILE, estado)

        # Se o save falhou, apaga o canal criado (rollback) e avisa o utilizador
        if not save_ok:
            try:
                await canal.delete(reason="Rollback — falha ao guardar estado do ticket")
            except discord.HTTPException:
                pass
            await interaction.response.send_message(
                embed=embed_erro(
                    "Erro ao criar ticket",
                    "Não foi possível guardar o estado do ticket. Tenta novamente.",
                    cfg.nome_servidor,
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=embed_sucesso(
                f"{categoria.get('emoji', '🎫')} Ticket criado!",
                f"O teu ticket foi criado: {canal.mention}\n"
                f"**ID:** `{ticket_id}` • **Categoria:** {categoria['nome']}\n"
                f"A staff responderá o mais breve possível.",
                cfg.nome_servidor,
            ),
            ephemeral=True,
        )

        # Constrói a descrição do ticket com todas as respostas
        linhas_respostas = []
        for key, valor in respostas.items():
            # Tenta encontrar o label do campo na categoria
            label_amigavel = key.replace("_", " ").title()
            for campo in categoria.get("campos", []):
                if campo.get("key") == key:
                    label_amigavel = campo["label"]
                    break
            if key == "nome_jogador":
                label_amigavel = "👤 Nome do jogador"
            linhas_respostas.append(f"**{label_amigavel}:**\n```\n{valor[:1000]}\n```")

        descricao_ticket = (
            f"Bem-vindo {interaction.user.mention}! 🎫\n\n"
            + "\n\n".join(linhas_respostas)
            + f"\n\n📋 **Regras do ticket:**\n"
            f"➡️ Mantém o respeito com a staff.\n"
            f"➡️ Explica o teu problema com o máximo de detalhe.\n"
            f"➡️ Não marques a staff — serás atendido quando possível.\n"
            f"➡️ Para fechar, clica no botão **Fechar Ticket** abaixo."
        )

        cor = categoria.get("cor", Cores.VERMELHO)
        embed_ticket = discord.Embed(
            title=f"{categoria.get('emoji', '🎫')} {categoria['nome']} — Ticket {ticket_id}",
            description=descricao_ticket[:4096],  # limite do Discord
            color=cor,
            timestamp=datetime.now(timezone.utc),
        )
        embed_ticket.set_thumbnail(url=interaction.user.display_avatar.url)
        embed_ticket.set_footer(text=f"{cfg.nome_servidor} • Ticket {ticket_id}")

        conteudo = ""
        for cargo_id in (cfg.cargo_ticket_staff, cfg.cargo_staff):
            if not cargo_id:
                continue
            cargo = guild.get_role(cargo_id)
            if cargo:
                conteudo = f"{cargo.mention} — novo ticket!"
                break

        view = ControloTicketView(self, interaction.user.id)
        await canal.send(
            content=conteudo,
            embed=embed_ticket,
            view=view,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )

        await log_evento(
            self.bot,
            f"{Emojis.TICKET} Ticket aberto",
            f"**{ticket_id}** • {categoria['nome']}\n"
            f"Aberto por {interaction.user.mention} no canal {canal.mention}.\n"
            f"Nome do jogador: {respostas.get('nome_jogador', '—')}",
            cor,
            interaction.user,
            guild,
        )

    async def fechar_ticket(self, interaction: discord.Interaction) -> None:
        canal = interaction.channel
        if not isinstance(canal, discord.TextChannel):
            return

        cfg = get_config(interaction.guild.id)
        estado = carregar_json(TICKETS_FILE, {"tickets": {}})
        ticket_encontrado: Optional[dict] = None
        ticket_id_encontrado: Optional[str] = None
        for tid, t in estado.get("tickets", {}).items():
            if t.get("canal_id") == canal.id and t.get("aberto"):
                ticket_encontrado = t
                ticket_id_encontrado = tid
                break

        if ticket_encontrado is None:
            await interaction.response.send_message(
                embed=embed_erro(
                    "Não é ticket",
                    "Este canal não é um ticket ativo.",
                    cfg.nome_servidor,
                ),
                ephemeral=True,
            )
            return

        view_confirmar = ConfirmarFechoView()
        await interaction.response.send_message(
            embed=embed_aviso(
                f"{Emojis.FECHAR} Fechar ticket?",
                f"{interaction.user.mention}, tens a certeza que queres fechar este ticket?\n"
                f"Um transcript será gerado antes do fecho.\n\n"
                f"Clica em **Confirmar** para fechar nos próximos 30 segundos.",
                cfg.nome_servidor,
            ),
            view=view_confirmar,
        )

        timed_out = await view_confirmar.wait()
        if timed_out:
            try:
                await interaction.edit_original_response(
                    content="⏱️ Confirmação expirou — ticket não fechado.",
                    view=None,
                )
            except discord.HTTPException:
                pass
            return

        if not view_confirmar.confirmado:
            try:
                await interaction.edit_original_response(
                    content="❌ Fecho cancelado.",
                    view=None,
                )
            except discord.HTTPException:
                pass
            return

        await self._gerar_e_enviar_transcript(
            canal, interaction.user, ticket_encontrado, cfg.nome_servidor,
            interaction=interaction,
        )

        # ── Envia DM de feedback ao dono do ticket ──
        # (apenas visual — não guarda a avaliação)
        await self._enviar_feedback_dm(ticket_encontrado, cfg)

        # Apaga o canal PRIMEIRO (se falhar, o ticket continua aberto)
        canal_apagado = False
        try:
            await canal.send(
                embed=embed_aviso(
                    "🔒 A fechar...",
                    "Este canal será apagado em 3 segundos.",
                    cfg.nome_servidor,
                )
            )
            await asyncio.sleep(3)
            await canal.delete(reason=f"Ticket fechado por {interaction.user}")
            canal_apagado = True
        except discord.HTTPException:
            pass

        # Só marca como fechado se o canal foi apagado com sucesso
        if canal_apagado:
            async with self._ticket_lock:
                estado = carregar_json(TICKETS_FILE, {"tickets": {}})
                ticket_encontrado = estado["tickets"].get(ticket_id_encontrado, ticket_encontrado)
                ticket_encontrado["aberto"] = False
                ticket_encontrado["fechado_em"] = datetime.now(timezone.utc).isoformat()
                ticket_encontrado["fechado_por"] = str(interaction.user)
                estado["tickets"][ticket_id_encontrado] = ticket_encontrado

                # Limpa tickets fechados há mais de 30 dias (evita crescimento indefinido)
                agora = datetime.now(timezone.utc)
                tickets_limpos = {}
                for tid, t in estado["tickets"].items():
                    if t.get("aberto"):
                        tickets_limpos[tid] = t
                    else:
                        fechado_em = t.get("fechado_em", "")
                        if fechado_em:
                            try:
                                data_fecho = datetime.fromisoformat(fechado_em)
                                if (agora - data_fecho).days < 30:
                                    tickets_limpos[tid] = t
                            except (ValueError, TypeError):
                                tickets_limpos[tid] = t  # mantém se não conseguir parsear
                        else:
                            tickets_limpos[tid] = t
                estado["tickets"] = tickets_limpos
                guardar_json(TICKETS_FILE, estado)

            await log_evento(
                self.bot,
                f"{Emojis.FECHAR} Ticket fechado",
                f"**{ticket_id_encontrado}** • {ticket_encontrado['categoria_label']}\n"
                f"Fechado por {interaction.user.mention} no canal #{canal.name}.",
                Cores.ERRO,
                interaction.user,
                interaction.guild,
            )
        else:
            # Se o canal não foi apagado, avisa mas mantém o ticket aberto
            try:
                await canal.send(
                    embed=embed_erro(
                        "⚠️ Erro ao apagar canal",
                        "Não foi possível apagar o canal automaticamente. O ticket continua aberto — tenta fechá-lo novamente.",
                        cfg.nome_servidor,
                    )
                )
            except discord.HTTPException:
                pass

    async def _enviar_feedback_dm(self, ticket_info: dict, cfg) -> None:
        """Envia DM ao dono do ticket com botões de estrelas para avaliar o atendimento.

        Apenas visual — a avaliação não é guardada.
        """
        if not ticket_info or not ticket_info.get("user_id"):
            return
        user_id = ticket_info["user_id"]
        # Busca o utilizador
        try:
            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
        except (discord.NotFound, discord.HTTPException):
            return
        if user is None or user.bot:
            return

        embed = discord.Embed(
            title="⭐ Como foi o teu atendimento?",
            description=(
                f"Olá {user.mention}, sou o **Tuguinha** 🇵🇹\n\n"
                f"Gostava imenso de saber como foi o teu atendimento na **{cfg.nome_servidor}**.\n\n"
                f"**Ticket:** `{ticket_info.get('id', '?')}` • {ticket_info.get('categoria_label', '?')}\n\n"
                f"⬇️ **Clica nas estrelas abaixo para avaliar (1 a 5):**"
            ),
            color=0xFFD700,
        )
        embed.set_footer(text="Tuguinha • Rede Tuga 🇵🇹")
        view = FeedbackStarsView(user_id, cfg.nome_servidor)
        try:
            await user.send(embed=embed, view=view)
        except discord.Forbidden:
            # DM fechada — não é problema, simplesmente não envia
            pass
        except discord.HTTPException:
            pass

    async def gerar_transcript(self, interaction: discord.Interaction) -> None:
        canal = interaction.channel
        cfg = get_config(interaction.guild.id)
        await self._gerar_e_enviar_transcript(
            canal, interaction.user, None, cfg.nome_servidor, interaction=interaction
        )

    async def _gerar_e_enviar_transcript(
        self,
        canal: discord.TextChannel,
        quem_pediu: discord.abc.User,
        ticket_info: Optional[dict],
        nome_servidor: str = "Rede Tuga",
        interaction: Optional[discord.Interaction] = None,
    ) -> None:
        if interaction and not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        linhas: list[str] = []
        linhas.append("╔══════════════════════════════════════════════════════════════╗")
        linhas.append(f"║  TRANSCRIPT DE TICKET — {nome_servidor}")
        linhas.append("╚══════════════════════════════════════════════════════════════╝")
        linhas.append(f"Canal: #{canal.name}")
        linhas.append(f"Servidor: {canal.guild.name}")
        linhas.append(f"Gerado em: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        linhas.append(f"Por: {quem_pediu}")
        if ticket_info:
            linhas.append(f"Ticket ID: {ticket_info.get('id', '?')}")
            linhas.append(f"Categoria: {ticket_info.get('categoria_label', '?')}")
            linhas.append(f"Aberto por: {ticket_info.get('criado_por', '?')}")
            # Mostra todas as respostas do formulário
            respostas = ticket_info.get("respostas", {})
            if respostas:
                linhas.append("─" * 32)
                linhas.append("RESPOSTAS DO FORMULÁRIO:")
                for key, valor in respostas.items():
                    label = key.replace("_", " ").title()
                    linhas.append(f"  • {label}: {valor}")
            elif ticket_info.get("motivo"):
                # Retrocompatibilidade com tickets antigos
                linhas.append(f"Motivo: {ticket_info.get('motivo', '?')}")
        linhas.append("─" * 64)
        linhas.append("")

        contador = 0
        async for msg in canal.history(limit=500, oldest_first=True):
            contador += 1
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            autor = f"{msg.author} ({msg.author.id})"
            conteudo = msg.clean_content or "[sem texto]"
            anexos = "\n  ".join(f"[ANEXO] {a.url}" for a in msg.attachments)
            linhas.append(f"[{timestamp}] {autor}:")
            linhas.append(f"  {conteudo}")
            if anexos:
                linhas.append(f"  {anexos}")
            linhas.append("")

        linhas.append("─" * 64)
        linhas.append(f"Total de mensagens: {contador}")
        linhas.append("Fim do transcript.")

        conteudo_final = "\n".join(linhas)
        buffer = io.BytesIO(conteudo_final.encode("utf-8"))
        ficheiro = discord.File(buffer, filename=f"transcript-{canal.name}.txt")

        # Embed do transcript
        embed = discord.Embed(
            title=f"{Emojis.TRANSCRIPT} Transcript",
            description=f"**Ticket:** `{ticket_info.get('id', '?') if ticket_info else '?'}`\n"
            f"**Categoria:** {ticket_info.get('categoria_label', '?') if ticket_info else '?'}\n"
            f"**Aberto por:** {ticket_info.get('criado_por', '?') if ticket_info else '?'}\n"
            f"**Mensagens:** {contador}\n"
            f"**Fechado por:** {quem_pediu.mention}",
            color=Cores.CINZA,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=nome_servidor)

        # Envia ao utilizador que pediu (se houver interaction)
        if interaction and interaction.response.is_done():
            await interaction.followup.send(embed=embed, file=ficheiro, ephemeral=True)
        elif interaction:
            await interaction.response.send_message(embed=embed, file=ficheiro, ephemeral=True)

        # Envia ao canal de transcript (SEMPRE — usa fallback da Rede Tuga se não configurado)
        from utils import CANAL_TRANSCRIPT_FALLBACK_ID
        cfg = get_config(canal.guild.id)
        canal_destino_transcript = None

        # 1. Tenta o canal_transcript configurado
        if cfg.canal_transcript:
            canal_destino_transcript = canal.guild.get_channel(cfg.canal_transcript)
        # 2. Fallback: ID padrão da Rede Tuga
        if canal_destino_transcript is None:
            canal_destino_transcript = canal.guild.get_channel(CANAL_TRANSCRIPT_FALLBACK_ID)
        # 3. Último fallback: canal de logs
        if canal_destino_transcript is None and cfg.canal_logs:
            canal_destino_transcript = canal.guild.get_channel(cfg.canal_logs)

        if canal_destino_transcript:
            buffer2 = io.BytesIO(conteudo_final.encode("utf-8"))
            ficheiro2 = discord.File(buffer2, filename=f"transcript-{canal.name}.txt")
            try:
                await canal_destino_transcript.send(embed=embed, file=ficheiro2)
            except discord.HTTPException:
                pass


async def setup(bot: commands.Bot) -> None:
    cog = TicketsCog(bot)
    await bot.add_cog(cog)
    # Nota: As views persistentes (PainelTicketsView, ControloTicketView, FeedbackStarsView)
    # são registadas no __init__ da cog via bot.add_view(). Elas processam todos os
    # botões após restart automaticamente — não precisamos de listener fallback.
    # O listener anterior causava race conditions (processamento duplo).
