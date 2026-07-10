"""
Cog de Edição — permite reconfigurar TUDO após o /setup.

Comandos:
  /editar                → Menu interativo com todas as opções
  /config_status         → Ver configuração atual
  /editar_mensagens      → Editar as 4 mensagens customizáveis
  /editar_canais         → Trocar canal de regras/boas-vindas/tickets/logs
  /editar_cargos         → Trocar cargos (admin, staff, membro, etc.)
  /editar_nome           → Mudar nome do servidor no bot
  /reset_config          → Apagar config e recomeçar (admin only)

Todos os comandos exigem permissão de Administrador.
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import Cores, Emojis, get_config, save_config
from utils import embed_aviso, embed_erro, embed_sucesso, e_admin, log_evento


# ─────────────────────────────────────────────────────────────────────────────
# Verificação de permissão centralizada
# ─────────────────────────────────────────────────────────────────────────────
def require_admin(interaction: discord.Interaction) -> bool:
    """Verifica se o utilizador é admin. Se não, envia mensagem de erro."""
    if not isinstance(interaction.user, discord.Member):
        return False
    if e_admin(interaction.user):
        return True
    # Em vez de enviar mensagem aqui (porque o interaction pode já ter sido respondido),
    # retorna False e o chamador trata.
    return False


async def check_admin_and_respond(interaction: discord.Interaction) -> bool:
    """Verifica admin e envia mensagem de erro se não for. Retorna True se OK."""
    if not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message(
            embed=embed_erro("Sem permissão", "Este comando só funciona em servidores."),
            ephemeral=True,
        )
        return False
    if e_admin(interaction.user):
        return True
    cfg = get_config(interaction.guild.id)
    await interaction.response.send_message(
        embed=embed_erro(
            "🚫 Sem permissão",
            f"Apenas **administradores** podem usar este comando.\n\n"
            f"Precisas de:\n"
            f"• Permissão de **Administrador** no servidor, **OU**\n"
            f"• Ter o cargo {f'<@&{cfg.cargo_admin}>' if cfg.cargo_admin else '👑 Admin'}",
            cfg.nome_servidor,
        ),
        ephemeral=True,
    )
    return False


# ─────────────────────────────────────────────────────────────────────────────
# /editar — Menu principal interativo
# ─────────────────────────────────────────────────────────────────────────────
class EditarMenuView(discord.ui.View):
    """Menu principal de edição com todas as opções."""

    def __init__(self, cog: "EditarCog") -> None:
        super().__init__(timeout=300)
        self.cog = cog

    @discord.ui.select(
        placeholder="📝 Escolhe o que queres editar...",
        options=[
            discord.SelectOption(
                label="Mensagens customizadas",
                value="mensagens",
                description="Boas-vindas, tickets",
                emoji="💬",
            ),
            discord.SelectOption(
                label="Categorias de tickets",
                value="categorias",
                description="Criar, editar e apagar categorias de tickets",
                emoji="🎫",
            ),
            discord.SelectOption(
                label="Canais",
                value="canais",
                description="Trocar canal de regras, tickets, etc.",
                emoji="📢",
            ),
            discord.SelectOption(
                label="Cargos",
                value="cargos",
                description="Trocar cargos de admin, staff, membro...",
                emoji="🎭",
            ),
            discord.SelectOption(
                label="Nome do servidor",
                value="nome",
                description="Mudar o nome que aparece nos embeds",
                emoji="🏷️",
            ),
            discord.SelectOption(
                label="Ver config atual",
                value="status",
                description="Mostra toda a configuração",
                emoji="📋",
            ),
            discord.SelectOption(
                label="Replicar painéis",
                value="republicar",
                description="Reenvia regras, tickets, boas-vindas",
                emoji="🔄",
            ),
            discord.SelectOption(
                label="⚠️ Reset completo",
                value="reset",
                description="Apaga config e recomeça do zero",
                emoji="⚠️",
            ),
        ],
        min_values=1, max_values=1,
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select) -> None:
        escolha = select.values[0]
        # Verifica admin novamente (segurança)
        if not await check_admin_and_respond(interaction):
            return

        if escolha == "mensagens":
            await self.cog.menu_editar_mensagens(interaction)
        elif escolha == "categorias":
            await self.cog.menu_categorias_tickets(interaction)
        elif escolha == "canais":
            await self.cog.menu_editar_canais(interaction)
        elif escolha == "cargos":
            await self.cog.menu_editar_cargos(interaction)
        elif escolha == "nome":
            await self.cog.menu_editar_nome(interaction)
        elif escolha == "status":
            await self.cog.mostrar_status(interaction)
        elif escolha == "republicar":
            await self.cog.menu_republicar(interaction)
        elif escolha == "reset":
            await self.cog.confirmar_reset(interaction)


# ─────────────────────────────────────────────────────────────────────────────
# Gestão de categorias de tickets
# ─────────────────────────────────────────────────────────────────────────────
class MenuCategoriasView(discord.ui.View):
    """Menu de gestão de categorias de tickets."""

    def __init__(self, cog: "EditarCog") -> None:
        super().__init__(timeout=300)
        self.cog = cog

    @discord.ui.button(label="➕ Adicionar categoria", emoji="➕", style=discord.ButtonStyle.success)
    async def btn_adicionar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await check_admin_and_respond(interaction):
            return
        await interaction.response.send_modal(CriarCategoriaModal(self.cog))

    @discord.ui.button(label="✏️ Editar categoria", emoji="✏️", style=discord.ButtonStyle.primary)
    async def btn_editar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await check_admin_and_respond(interaction):
            return
        await self.cog.mostrar_selecao_categoria_editar(interaction)

    @discord.ui.button(label="🗑️ Apagar categoria", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def btn_apagar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await check_admin_and_respond(interaction):
            return
        await self.cog.mostrar_selecao_categoria_apagar(interaction)

    @discord.ui.button(label="📋 Listar categorias", emoji="📋", style=discord.ButtonStyle.secondary)
    async def btn_listar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await check_admin_and_respond(interaction):
            return
        await self.cog.listar_categorias(interaction)

    @discord.ui.button(label="🔄 Restaurar defaults", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def btn_defaults(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await check_admin_and_respond(interaction):
            return
        await self.cog.restaurar_categorias_defaults(interaction)

    @discord.ui.button(label="↩️ Voltar", emoji="↩️", style=discord.ButtonStyle.secondary, row=2)
    async def btn_voltar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await check_admin_and_respond(interaction):
            return
        await self.cog.cmd_editar.callback(self.cog, interaction)


class CriarCategoriaModal(discord.ui.Modal):
    """Modal para criar nova categoria de ticket."""

    def __init__(self, cog: "EditarCog", categoria_existente: dict = None) -> None:
        titulo = "➕ Nova Categoria" if categoria_existente is None else "✏️ Editar Categoria"
        super().__init__(title=titulo, timeout=600)
        self.cog = cog
        self.categoria_existente = categoria_existente

        self.id_input = discord.ui.TextInput(
            label="ID único (slug, ex: suporte, comprar, bug)",
            placeholder="ex: suporte",
            default=categoria_existente["id"] if categoria_existente else "",
            max_length=30,
            required=True,
        )
        self.add_item(self.id_input)

        self.nome_input = discord.ui.TextInput(
            label="Nome da categoria (aparece no menu)",
            placeholder="ex: Suporte Geral",
            default=categoria_existente["nome"] if categoria_existente else "",
            max_length=100,
            required=True,
        )
        self.add_item(self.nome_input)

        self.emoji_input = discord.ui.TextInput(
            label="Emoji (1 caractere)",
            placeholder="ex: 🆘, 🛒, 🔧, 🛡️",
            default=categoria_existente["emoji"] if categoria_existente else "🎫",
            max_length=10,
            required=True,
        )
        self.add_item(self.emoji_input)

        self.descricao_input = discord.ui.TextInput(
            label="Descrição (aparece no menu)",
            placeholder="ex: Dúvidas gerais sobre o servidor",
            default=categoria_existente["descricao"] if categoria_existente else "",
            max_length=100,
            required=True,
        )
        self.add_item(self.descricao_input)

        self.placeholder_input = discord.ui.TextInput(
            label="💬 Placeholder do modal",
            placeholder="ex: Descreve a tua dúvida...",
            default=categoria_existente.get("placeholder", "") if categoria_existente else "",
            max_length=100,
            required=False,
        )
        self.add_item(self.placeholder_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        cfg = get_config(interaction.guild.id)
        import re as _re
        cat_id = self.id_input.value.strip().lower().replace(" ", "_")

        # Validação rigorosa do slug: apenas [a-z0-9_], 2-30 chars
        if not _re.match(r"^[a-z0-9_]{2,30}$", cat_id):
            await interaction.response.send_message(
                embed=embed_erro(
                    "ID inválido",
                    "O ID só pode ter **letras minúsculas, números e underscores** "
                    "(2 a 30 caracteres). Ex: `suporte_geral`, `comprar_vip`.",
                    cfg.nome_servidor,
                ),
                ephemeral=True,
            )
            return

        # Valida nome (não vazio)
        nome = self.nome_input.value.strip()
        if not nome or len(nome) < 2:
            await interaction.response.send_message(
                embed=embed_erro(
                    "Nome inválido",
                    "O nome da categoria tem de ter pelo menos 2 caracteres.",
                    cfg.nome_servidor,
                ),
                ephemeral=True,
            )
            return

        nova_categoria = {
            "id": cat_id,
            "nome": nome,
            "emoji": self.emoji_input.value.strip()[:10] or "🎫",
            "descricao": self.descricao_input.value.strip() or "—",
            "cor": self.categoria_existente["cor"] if self.categoria_existente else 0xFF3B3B,
            "placeholder": self.placeholder_input.value.strip() or "Descreve o teu caso...",
        }

        if not cfg.categorias_ticket:
            cfg.categorias_ticket = []

        if self.categoria_existente:
            # Edita existente — verifica duplicado (excluindo a própria categoria)
            id_antigo = self.categoria_existente["id"]
            if cat_id != id_antigo and any(c["id"] == cat_id for c in cfg.categorias_ticket):
                await interaction.response.send_message(
                    embed=embed_erro(
                        "ID duplicado",
                        f"Já existe uma categoria com ID `{cat_id}`. Usa outro.",
                        cfg.nome_servidor,
                    ),
                    ephemeral=True,
                )
                return
            for i, c in enumerate(cfg.categorias_ticket):
                if c["id"] == id_antigo:
                    cfg.categorias_ticket[i] = nova_categoria
                    break
            msg_acao = "editada"
        else:
            # Verifica duplicado
            if any(c["id"] == cat_id for c in cfg.categorias_ticket):
                await interaction.response.send_message(
                    embed=embed_erro(
                        "ID duplicado",
                        f"Já existe uma categoria com ID `{cat_id}`. Usa outro.",
                        cfg.nome_servidor,
                    ),
                    ephemeral=True,
                )
                return
            if len(cfg.categorias_ticket) >= 25:
                await interaction.response.send_message(
                    embed=embed_erro(
                        "Limite atingido",
                        "Máximo de 25 categorias. Apaga algumas antes de adicionar mais.",
                        cfg.nome_servidor,
                    ),
                    ephemeral=True,
                )
                return
            cfg.categorias_ticket.append(nova_categoria)
            msg_acao = "criada"

        save_config(cfg)

        embed = embed_sucesso(
            f"Categoria {msg_acao}!",
            f"**{nova_categoria['emoji']} {nova_categoria['nome']}** (`{nova_categoria['id']}`)\n"
            f"📋 {nova_categoria['descricao']}\n\n"
            f"💡 Usa `/editar` → **Replicar painéis** para aplicar no painel de tickets.",
            cfg.nome_servidor,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        await log_evento(
            interaction.client,
            f"🎫 Categoria {msg_acao}",
            f"**{nova_categoria['emoji']} {nova_categoria['nome']}** (`{nova_categoria['id']}`)\n"
            f"Por {interaction.user.mention}",
            Cores.DOURADO,
            interaction.user,
            interaction.guild,
        )


class SelecionarCategoriaView(discord.ui.View):
    """View para selecionar uma categoria (editar ou apagar)."""

    def __init__(self, cog: "EditarCog", categorias: list[dict], acao: str) -> None:
        super().__init__(timeout=120)
        self.cog = cog
        self.acao = acao  # "editar" ou "apagar"

        if not categorias:
            return

        options = [
            discord.SelectOption(
                label=f"{c.get('emoji', '🎫')} {c['nome']}"[:100],
                value=c["id"],
                description=c.get("descricao", "")[:100],
            )
            for c in categorias[:25]
        ]

        select = discord.ui.Select(
            placeholder=f"Seleciona a categoria para {acao}...",
            options=options,
            min_values=1, max_values=1,
        )

        async def cb(interaction: discord.Interaction) -> None:
            if not await check_admin_and_respond(interaction):
                return
            cat_id = select.values[0]
            categoria = next((c for c in categorias if c["id"] == cat_id), None)
            if categoria is None:
                await interaction.response.send_message("❌ Categoria não encontrada.", ephemeral=True)
                return

            if self.acao == "editar":
                await interaction.response.send_modal(CriarCategoriaModal(self.cog, categoria))
            elif self.acao == "apagar":
                await self.cog.confirmar_apagar_categoria(interaction, categoria)

        select.callback = cb
        self.add_item(select)

        # Botão voltar
        btn_voltar = discord.ui.Button(label="↩️ Voltar", style=discord.ButtonStyle.secondary)
        async def cb_voltar(interaction: discord.Interaction) -> None:
            if not await check_admin_and_respond(interaction):
                return
            await self.cog.menu_categorias_tickets(interaction)
        btn_voltar.callback = cb_voltar
        self.add_item(btn_voltar)


class ConfirmarApagarCategoriaView(discord.ui.View):
    def __init__(self, cog: "EditarCog", categoria: dict) -> None:
        super().__init__(timeout=60)
        self.cog = cog
        self.categoria = categoria

    @discord.ui.button(label="⚠️ Confirmar", emoji="⚠️", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await check_admin_and_respond(interaction):
            return
        cfg = get_config(interaction.guild.id)
        if cfg.categorias_ticket:
            cfg.categorias_ticket = [
                c for c in cfg.categorias_ticket if c["id"] != self.categoria["id"]
            ]
            save_config(cfg)

        await interaction.response.edit_message(
            embed=embed_sucesso(
                "Categoria apagada!",
                f"**{self.categoria['emoji']} {self.categoria['nome']}** foi removida.\n"
                f"💡 Replica o painel com `/editar` → **Replicar painéis**.",
                cfg.nome_servidor,
            ),
            view=None,
        )

    @discord.ui.button(label="Cancelar", emoji="❌", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            content="✅ Apagamento cancelado.", embed=None, view=None
        )


class MenuMensagensView_Select(discord.ui.View):
    """View com select para escolher qual mensagem editar."""

    def __init__(self, cog: "EditarCog") -> None:
        super().__init__(timeout=300)
        self.cog = cog

    @discord.ui.select(
        placeholder="💬 Escolhe a mensagem para editar...",
        options=[
            discord.SelectOption(
                label="Boas-vindas (canal)",
                value="bem_vindo",
                description="{user} {count} {regras} {tickets}",
                emoji="👋",
            ),
            discord.SelectOption(
                label="Painel de tickets",
                value="ticket_panel",
                description="{regras} {categorias}",
                emoji="🎫",
            ),
            discord.SelectOption(
                label="Mensagem dentro do ticket",
                value="ticket_criado",
                description="{user} {motivo}",
                emoji="📝",
            ),
            discord.SelectOption(
                label="↩️ Voltar ao menu",
                value="voltar",
                description="Voltar ao menu principal",
                emoji="↩️",
            ),
        ],
        min_values=1, max_values=1,
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select) -> None:
        if not await check_admin_and_respond(interaction):
            return
        escolha = select.values[0]
        if escolha == "voltar":
            await self.cog.cmd_editar.callback(self.cog, interaction)
            return
        await self.cog.abrir_modal_mensagem(interaction, escolha)


class EditarMensagemModal(discord.ui.Modal):
    def __init__(self, cog: "EditarCog", tipo: str, cfg) -> None:
        self.cog = cog
        self.tipo = tipo
        self.cfg = cfg

        nomes = {
            "bem_vindo": ("👋 Mensagem de Boas-vindas", "{user}, {count}, {regras}, {tickets}"),
            "ticket_panel": ("🎫 Mensagem do Painel de Tickets", "{regras}, {categorias}"),
            "ticket_criado": ("📝 Mensagem dentro do Ticket", "{user}, {motivo}"),
        }
        titulo, placeholders = nomes.get(tipo, ("Mensagem", ""))

        super().__init__(title=f"Editar — {titulo}", timeout=600)

        # Valor atual
        atual = {
            "bem_vindo": cfg.msg_bem_vindo,
            "ticket_panel": cfg.msg_ticket_panel,
            "ticket_criado": cfg.msg_ticket_criado,
        }.get(tipo, "")

        self.mensagem = discord.ui.TextInput(
            label=titulo[:45],
            placeholder=f"Placeholders: {placeholders}. Deixa vazio = padrão.",
            style=discord.TextStyle.paragraph,
            default=atual,
            max_length=1000,
            required=False,
        )
        self.add_item(self.mensagem)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        nova_msg = self.mensagem.value.strip()
        if self.tipo == "bem_vindo":
            self.cfg.msg_bem_vindo = nova_msg
        elif self.tipo == "ticket_panel":
            self.cfg.msg_ticket_panel = nova_msg
        elif self.tipo == "ticket_criado":
            self.cfg.msg_ticket_criado = nova_msg

        save_config(self.cfg)

        # Preview da mensagem com placeholders substituídos
        preview_map = {
            "bem_vindo": self.cfg.get_msg_bem_vindo,
            "ticket_panel": self.cfg.get_msg_ticket_panel,
            "ticket_criado": self.cfg.get_msg_ticket_criado,
        }
        preview = preview_map[self.tipo]()
        preview = preview.replace("{user}", interaction.user.mention)
        preview = preview.replace("{count}", "42")
        preview = preview.replace("{regras}", f"<#{self.cfg.canal_regras}>" if self.cfg.canal_regras else "#regras")
        preview = preview.replace("{tickets}", f"<#{self.cfg.canal_tickets}>" if self.cfg.canal_tickets else "#tickets")
        preview = preview.replace("{motivo}", "Exemplo de motivo")
        preview = preview.replace("{categorias}", "• 🆘 Suporte • 🛒 Comprar • 🔧 Bug • 🛡️ Apelar")

        embed = discord.Embed(
            title=f"{Emojis.VERIFICAR} Mensagem atualizada!",
            description=f"**Tipo:** `{self.tipo}`\n**Estado:** {'Customizada' if nova_msg else 'Padrão (vazio)'}",
            color=Cores.SUCESSO,
        )
        embed.add_field(
            name="📋 Preview (placeholders substituídos)",
            value=preview[:1000],
            inline=False,
        )
        embed.add_field(
            name="💡 Dica",
            value="Para aplicar nos painéis existentes, usa `/editar` → **Replicar painéis**.",
            inline=False,
        )
        embed.set_footer(text=self.cfg.nome_servidor)
        await interaction.response.send_message(embed=embed, ephemeral=True)

        await log_evento(
            interaction.client,
            "📝 Mensagem editada",
            f"Tipo: `{self.tipo}`\nEditada por {interaction.user.mention}",
            Cores.DOURADO,
            interaction.user,
            interaction.guild,
        )


# ─────────────────────────────────────────────────────────────────────────────
# /editar_canais — Trocar canais
# ─────────────────────────────────────────────────────────────────────────────
class MenuCanaisView(discord.ui.View):
    def __init__(self, cog: "EditarCog", guild: discord.Guild) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.guild = guild
        self.cfg = get_config(guild.id)

        canais = list(guild.text_channels[:22])

        for chave, label, emoji, attr in [
            ("regras", "📜 Canal de Regras", Emojis.REGRAS, "canal_regras"),
            ("bv", "👋 Canal de Boas-vindas", Emojis.BEM_VINDO, "canal_bem_vindas"),
            ("tickets", "🎫 Canal de Tickets", Emojis.TICKET, "canal_tickets"),
            ("logs", "📋 Canal de Logs", "📋", "canal_logs"),
            ("transcript", "📝 Canal de Transcripts", "📝", "canal_transcript"),
        ]:
            atual_id = getattr(self.cfg, attr, 0)
            atual_label = "— não configurado —"
            if atual_id:
                ch = guild.get_channel(atual_id)
                if ch:
                    atual_label = f"#{ch.name}"

            options = [
                discord.SelectOption(
                    label=f"#{c.name}"[:100],
                    value=str(c.id),
                    description="Canal existente",
                    emoji=emoji,
                )
                for c in canais
            ]
            if chave == "bv":
                options.append(discord.SelectOption(
                    label="🚫 Desativar boas-vindas",
                    value="off",
                    description="Desativa o sistema de boas-vindas",
                    emoji="🚫",
                ))
            options.append(discord.SelectOption(
                label="↩️ Manter atual",
                value="manter",
                description=f"Atual: {atual_label}",
                emoji="↩️",
            ))

            select = discord.ui.Select(
                placeholder=f"{emoji} {label} (atual: {atual_label})"[:100],
                options=options,
                min_values=1, max_values=1,
            )

            def make_callback(chave=chave, attr=attr, label=label):
                async def cb(interaction: discord.Interaction) -> None:
                    if not await check_admin_and_respond(interaction):
                        return
                    # Lê config fresca (evita sobrescrever alterações de outros admins)
                    cfg_fresh = get_config(self.guild.id)
                    valor = interaction.data["values"][0]
                    if valor == "manter":
                        await interaction.response.send_message(
                            "ℹ️ Mantido o canal atual.", ephemeral=True
                        )
                        return
                    if valor == "off":
                        setattr(cfg_fresh, attr, 0)
                        cfg_fresh.boas_vindas_ativas = False
                        save_config(cfg_fresh)
                        await interaction.response.send_message(
                            embed=embed_sucesso(
                                "Boas-vindas desativadas",
                                "O sistema de boas-vindas foi desativado.",
                                cfg_fresh.nome_servidor,
                            ),
                            ephemeral=True,
                        )
                        return
                    setattr(cfg_fresh, attr, int(valor))
                    if chave == "bv":
                        cfg_fresh.boas_vindas_ativas = True
                    save_config(cfg_fresh)
                    canal = self.guild.get_channel(int(valor))
                    await interaction.response.send_message(
                        embed=embed_sucesso(
                            "Canal atualizado!",
                            f"{label} agora é: {canal.mention}",
                            cfg_fresh.nome_servidor,
                        ),
                        ephemeral=True,
                    )
                    await log_evento(
                        interaction.client,
                        f"📢 Canal editado",
                        f"{label} → {canal.mention}\nPor {interaction.user.mention}",
                        Cores.DOURADO,
                        interaction.user,
                        interaction.guild,
                    )
                return cb

            select.callback = make_callback(chave=chave, attr=attr, label=label)
            self.add_item(select)

        # Botão voltar
        btn_voltar = discord.ui.Button(label="↩️ Voltar", style=discord.ButtonStyle.secondary, row=4)
        async def cb_voltar(interaction: discord.Interaction) -> None:
            if not await check_admin_and_respond(interaction):
                return
            await self.cog.cmd_editar.callback(self.cog, interaction)
        btn_voltar.callback = cb_voltar
        self.add_item(btn_voltar)


# ─────────────────────────────────────────────────────────────────────────────
# /editar_cargos — Trocar cargos
# ─────────────────────────────────────────────────────────────────────────────
class MenuCargosView(discord.ui.View):
    def __init__(self, cog: "EditarCog", guild: discord.Guild) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.guild = guild
        self.cfg = get_config(guild.id)

        cargos = [r for r in guild.roles if not r.is_bot_managed() and not r.is_default()][:24]

        for chave, label, emoji, attr in [
            ("admin", "👑 Admin", "👑", "cargo_admin"),
            ("staff", "🛡️ Staff", "🛡️", "cargo_staff"),
            ("ticket_staff", "🎫 Ticket Staff", "🎫", "cargo_ticket_staff"),
        ]:
            atual_id = getattr(self.cfg, attr, 0)
            atual_label = "— não configurado —"
            if atual_id:
                r = guild.get_role(atual_id)
                if r:
                    atual_label = r.name

            options = [
                discord.SelectOption(
                    label=r.name[:100],
                    value=str(r.id),
                    description="Cargo existente",
                    emoji=emoji,
                )
                for r in cargos
            ]
            options.append(discord.SelectOption(
                label="↩️ Manter atual",
                value="manter",
                description=f"Atual: {atual_label}",
                emoji="↩️",
            ))

            select = discord.ui.Select(
                placeholder=f"{emoji} {label} (atual: {atual_label})"[:100],
                options=options,
                min_values=1, max_values=1,
            )

            def make_callback(attr=attr, label=label):
                async def cb(interaction: discord.Interaction) -> None:
                    if not await check_admin_and_respond(interaction):
                        return
                    valor = interaction.data["values"][0]
                    if valor == "manter":
                        await interaction.response.send_message(
                            "ℹ️ Mantido o cargo atual.", ephemeral=True
                        )
                        return
                    setattr(self.cfg, attr, int(valor))
                    save_config(self.cfg)
                    cargo = self.guild.get_role(int(valor))
                    await interaction.response.send_message(
                        embed=embed_sucesso(
                            "Cargo atualizado!",
                            f"{label} agora é: {cargo.mention}",
                            self.cfg.nome_servidor,
                        ),
                        ephemeral=True,
                    )
                    await log_evento(
                        interaction.client,
                        "🎭 Cargo editado",
                        f"{label} → {cargo.mention}\nPor {interaction.user.mention}",
                        Cores.DOURADO,
                        interaction.user,
                        interaction.guild,
                    )
                return cb

            select.callback = make_callback(attr=attr, label=label)
            self.add_item(select)

        btn_voltar = discord.ui.Button(label="↩️ Voltar", style=discord.ButtonStyle.secondary, row=4)
        async def cb_voltar(interaction: discord.Interaction) -> None:
            if not await check_admin_and_respond(interaction):
                return
            await self.cog.cmd_editar.callback(self.cog, interaction)
        btn_voltar.callback = cb_voltar
        self.add_item(btn_voltar)


# ─────────────────────────────────────────────────────────────────────────────
# Editar nome do servidor
# ─────────────────────────────────────────────────────────────────────────────
class EditarNomeModal(discord.ui.Modal):
    def __init__(self, cog: "EditarCog", cfg) -> None:
        super().__init__(title="🏷️ Editar Nome do Servidor", timeout=300)
        self.cog = cog
        self.cfg = cfg

        self.nome = discord.ui.TextInput(
            label="Nome do servidor no bot",
            default=cfg.nome_servidor,
            max_length=80,
            required=True,
        )
        self.add_item(self.nome)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.cfg.nome_servidor = self.nome.value.strip() or "Rede Tuga"
        save_config(self.cfg)
        await interaction.response.send_message(
            embed=embed_sucesso(
                "Nome atualizado!",
                f"O nome do servidor no bot é agora: **{self.cfg.nome_servidor}**",
                self.cfg.nome_servidor,
            ),
            ephemeral=True,
        )
        await log_evento(
            interaction.client,
            "🏷️ Nome editado",
            f"Novo nome: **{self.cfg.nome_servidor}**\nPor {interaction.user.mention}",
            Cores.DOURADO,
            interaction.user,
            interaction.guild,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Republicar painéis
# ─────────────────────────────────────────────────────────────────────────────
class RepublicarView(discord.ui.View):
    def __init__(self, cog: "EditarCog") -> None:
        super().__init__(timeout=300)
        self.cog = cog

    @discord.ui.button(label="📜 Regras", emoji="📜", style=discord.ButtonStyle.primary)
    async def btn_regras(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await check_admin_and_respond(interaction):
            return
        await self.cog.republicar_regras(interaction)

    @discord.ui.button(label="👋 Boas-vindas", emoji="👋", style=discord.ButtonStyle.primary)
    async def btn_bv(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await check_admin_and_respond(interaction):
            return
        await self.cog.republicar_boas_vindas(interaction)

    @discord.ui.button(label="🎫 Tickets", emoji="🎫", style=discord.ButtonStyle.primary)
    async def btn_tickets(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await check_admin_and_respond(interaction):
            return
        await self.cog.republicar_tickets(interaction)

    @discord.ui.button(label="↩️ Voltar", emoji="↩️", style=discord.ButtonStyle.secondary)
    async def btn_voltar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await check_admin_and_respond(interaction):
            return
        await self.cog.cmd_editar.callback(self.cog, interaction)


# ─────────────────────────────────────────────────────────────────────────────
# Confirmar reset
# ─────────────────────────────────────────────────────────────────────────────
class ConfirmarResetView(discord.ui.View):
    def __init__(self, cog: "EditarCog") -> None:
        super().__init__(timeout=60)
        self.cog = cog

    @discord.ui.button(label="⚠️ Confirmar Reset", emoji="⚠️", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await check_admin_and_respond(interaction):
            return
        await self.cog.executar_reset(interaction)

    @discord.ui.button(label="Cancelar", emoji="❌", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            content="✅ Reset cancelado. Config mantida.", embed=None, view=None
        )


# ─────────────────────────────────────────────────────────────────────────────
# Cog principal
# ─────────────────────────────────────────────────────────────────────────────
class EditarCog(commands.Cog):
    """Sistema de edição pós-setup."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ─────────────────────────────────────────────────────────────────────────
    # /editar — Menu principal
    # ─────────────────────────────────────────────────────────────────────────
    @app_commands.command(
        name="editar",
        description="📝 Editar configuração do Tuguinha (admin)",
    )
    @app_commands.default_permissions(administrator=True)
    async def cmd_editar(self, interaction: discord.Interaction) -> None:
        if not await check_admin_and_respond(interaction):
            return

        cfg = get_config(interaction.guild.id)
        embed = discord.Embed(
            title=f"{Emojis.COROA} Menu de Edição — {cfg.nome_servidor}",
            description=(
                f"Olá {interaction.user.mention}! Escolhe no menu abaixo o que queres editar.\n\n"
                f"📊 **Estado atual:**\n"
                f"• Setup: {'✅ Completo' if cfg.setup_completo else '❌ Pendente'}\n"
                f"• Boas-vindas: {'✅ Ativas' if cfg.boas_vindas_ativas else '🚫 Desativadas'}\n\n"
                f"💡 **Podes editar:**\n"
                f"• 💬 **Mensagens** — boas-vindas, tickets, verificação\n"
                f"• 📢 **Canais** — trocar canal de regras, tickets, etc.\n"
                f"• 🎭 **Cargos** — trocar cargos de admin, staff, membro\n"
                f"• 🏷️ **Nome** — nome do servidor no bot\n"
                f"• 📋 **Status** — ver config atual\n"
                f"• 🔄 **Replicar painéis** — reenviar painéis com novas mensagens\n"
                f"• ⚠️ **Reset** — apagar tudo e recomeçar"
            ),
            color=Cores.DOURADO,
        )
        embed.set_footer(text=f"{cfg.nome_servidor} • Apenas admins")
        await interaction.response.send_message(
            embed=embed, view=EditarMenuView(self), ephemeral=True
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Sub-menus
    # ─────────────────────────────────────────────────────────────────────────
    async def menu_editar_mensagens(self, interaction: discord.Interaction) -> None:
        cfg = get_config(interaction.guild.id)
        embed = discord.Embed(
            title="💬 Editar Mensagens",
            description=(
                "Escolhe qual mensagem queres editar.\n\n"
                "**Placeholders disponíveis:**\n"
                "• `{user}` — menção do utilizador\n"
                "• `{count}` — nº de membros\n"
                "• `{regras}` — menção do canal de regras\n"
                "• `{tickets}` — menção do canal de tickets\n"
                "• `{motivo}` — motivo do ticket\n"
                "• `{categorias}` — lista de categorias (no painel de tickets)\n\n"
                "💡 Deixa vazio para usar o template padrão."
            ),
            color=Cores.DOURADO,
        )
        embed.set_footer(text=cfg.nome_servidor)
        await interaction.response.edit_message(
            embed=embed, view=MenuMensagensView_Select(self)
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Gestão de categorias de tickets
    # ─────────────────────────────────────────────────────────────────────────
    async def menu_categorias_tickets(self, interaction: discord.Interaction) -> None:
        cfg = get_config(interaction.guild.id)
        categorias = cfg.get_categorias_ticket()
        using_defaults = not cfg.categorias_ticket

        lista = "\n".join(
            f"• {c.get('emoji', '🎫')} **{c['nome']}** (`{c['id']}`) — {c.get('descricao', '')}"
            for c in categorias
        ) or "*(nenhuma categoria)*"

        embed = discord.Embed(
            title="🎫 Gerir Categorias de Tickets",
            description=(
                f"Categorias atuais ({'defaults' if using_defaults else 'customizadas'}):\n\n"
                f"{lista}\n\n"
                f"**O que podes fazer:**\n"
                f"• ➕ **Adicionar** — cria nova categoria com nome, emoji, descrição\n"
                f"• ✏️ **Editar** — modifica categoria existente\n"
                f"• 🗑️ **Apagar** — remove categoria\n"
                f"• 📋 **Listar** — vê as categorias em detalhe\n"
                f"• 🔄 **Restaurar defaults** — volta às 4 categorias padrão\n\n"
                f"💡 Máximo: 25 categorias."
            ),
            color=Cores.DOURADO,
        )
        embed.set_footer(text=cfg.nome_servidor)
        await interaction.response.edit_message(
            embed=embed, view=MenuCategoriasView(self)
        )

    async def mostrar_selecao_categoria_editar(self, interaction: discord.Interaction) -> None:
        cfg = get_config(interaction.guild.id)
        categorias = cfg.get_categorias_ticket()
        if not categorias:
            await interaction.response.send_message(
                embed=embed_erro("Sem categorias", "Não há categorias para editar.", cfg.nome_servidor),
                ephemeral=True,
            )
            return
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="✏️ Editar Categoria",
                description="Seleciona a categoria que queres editar.",
                color=Cores.DOURADO,
            ),
            view=SelecionarCategoriaView(self, categorias, "editar"),
        )

    async def mostrar_selecao_categoria_apagar(self, interaction: discord.Interaction) -> None:
        cfg = get_config(interaction.guild.id)
        categorias = cfg.get_categorias_ticket()
        if not categorias:
            await interaction.response.send_message(
                embed=embed_erro("Sem categorias", "Não há categorias para apagar.", cfg.nome_servidor),
                ephemeral=True,
            )
            return
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="🗑️ Apagar Categoria",
                description="Seleciona a categoria que queres apagar.",
                color=Cores.ERRO,
            ),
            view=SelecionarCategoriaView(self, categorias, "apagar"),
        )

    async def listar_categorias(self, interaction: discord.Interaction) -> None:
        cfg = get_config(interaction.guild.id)
        categorias = cfg.get_categorias_ticket()

        embed = discord.Embed(
            title=f"🎫 Categorias de Tickets — {cfg.nome_servidor}",
            description=f"Total: **{len(categorias)}** categorias",
            color=Cores.VERDE,
        )
        for c in categorias:
            embed.add_field(
                name=f"{c.get('emoji', '🎫')} {c['nome']} (`{c['id']}`)",
                value=f"📋 {c.get('descricao', '—')}\n💬 *{c.get('placeholder', '—')}*",
                inline=False,
            )
        embed.set_footer(text="Usa /editar para gerir")
        await interaction.response.edit_message(embed=embed, view=MenuCategoriasView(self))

    async def restaurar_categorias_defaults(self, interaction: discord.Interaction) -> None:
        cfg = get_config(interaction.guild.id)
        cfg.categorias_ticket = []  # vazio = usa defaults
        save_config(cfg)
        from config import CATEGORIAS_TICKET_DEFAULT
        await interaction.response.edit_message(
            embed=embed_sucesso(
                "Defaults restaurados!",
                f"Foram restauradas **{len(CATEGORIAS_TICKET_DEFAULT)}** categorias padrão.\n"
                f"💡 Replica o painel com `/editar` → **Replicar painéis**.",
                cfg.nome_servidor,
            ),
            view=MenuCategoriasView(self),
        )

    async def confirmar_apagar_categoria(self, interaction: discord.Interaction, categoria: dict) -> None:
        cfg = get_config(interaction.guild.id)
        embed = discord.Embed(
            title="⚠️ Confirmar Apagamento",
            description=(
                f"Vais apagar a categoria:\n\n"
                f"**{categoria['emoji']} {categoria['nome']}** (`{categoria['id']}`)\n"
                f"📋 {categoria.get('descricao', '')}\n\n"
                f"⚠️ Esta ação não pode ser desfeita."
            ),
            color=Cores.ERRO,
        )
        embed.set_footer(text=cfg.nome_servidor)
        await interaction.response.edit_message(
            embed=embed, view=ConfirmarApagarCategoriaView(self, categoria)
        )

    async def menu_editar_canais(self, interaction: discord.Interaction) -> None:
        cfg = get_config(interaction.guild.id)
        embed = discord.Embed(
            title="📢 Editar Canais",
            description="Escolhe os novos canais nos menus abaixo.",
            color=Cores.DOURADO,
        )
        embed.set_footer(text=cfg.nome_servidor)
        await interaction.response.edit_message(
            embed=embed, view=MenuCanaisView(self, interaction.guild)
        )

    async def menu_editar_cargos(self, interaction: discord.Interaction) -> None:
        cfg = get_config(interaction.guild.id)
        embed = discord.Embed(
            title="🎭 Editar Cargos",
            description="Escolhe os novos cargos nos menus abaixo.",
            color=Cores.DOURADO,
        )
        embed.set_footer(text=cfg.nome_servidor)
        await interaction.response.edit_message(
            embed=embed, view=MenuCargosView(self, interaction.guild)
        )

    async def menu_editar_nome(self, interaction: discord.Interaction) -> None:
        cfg = get_config(interaction.guild.id)
        await interaction.response.send_modal(EditarNomeModal(self, cfg))

    async def abrir_modal_mensagem(self, interaction: discord.Interaction, tipo: str) -> None:
        cfg = get_config(interaction.guild.id)
        await interaction.response.send_modal(EditarMensagemModal(self, tipo, cfg))

    # ─────────────────────────────────────────────────────────────────────────
    # Status — ver config atual
    # ─────────────────────────────────────────────────────────────────────────
    async def mostrar_status(self, interaction: discord.Interaction) -> None:
        cfg = get_config(interaction.guild.id)

        def canal_mention(cid: int) -> str:
            if not cid:
                return "❌ Não configurado"
            ch = interaction.guild.get_channel(cid)
            return ch.mention if ch else f"❌ ID {cid} (não encontrado)"

        def cargo_mention(rid: int) -> str:
            if not rid:
                return "❌ Não configurado"
            r = interaction.guild.get_role(rid)
            return r.mention if r else f"❌ ID {rid} (não encontrado)"

        embed = discord.Embed(
            title=f"📋 Configuração Atual — {cfg.nome_servidor}",
            description=(
                f"**Estado:** {'✅ Setup completo' if cfg.setup_completo else '⚠️ Setup pendente'}\n"
                f"**Boas-vindas:** {'✅ Ativas' if cfg.boas_vindas_ativas else '🚫 Desativadas'}"
            ),
            color=Cores.VERDE if cfg.setup_completo else Cores.AVISO,
        )

        embed.add_field(
            name="📢 Canais",
            value=(
                f"• 📜 Regras: {canal_mention(cfg.canal_regras)}\n"
                f"• 👋 Boas-vindas: {canal_mention(cfg.canal_bem_vindas)}\n"
                f"• 🎫 Tickets: {canal_mention(cfg.canal_tickets)}\n"
                f"• 📋 Logs: {canal_mention(cfg.canal_logs)}\n"
                f"• 📝 Transcripts: {canal_mention(cfg.canal_transcript)}\n"
                f"• 📂 Categoria tickets: {canal_mention(cfg.categoria_tickets)}"
            ),
            inline=False,
        )

        embed.add_field(
            name="🎭 Cargos",
            value=(
                f"• 👑 Admin: {cargo_mention(cfg.cargo_admin)}\n"
                f"• 🛡️ Staff: {cargo_mention(cfg.cargo_staff)}\n"
                f"• 🎫 Ticket Staff: {cargo_mention(cfg.cargo_ticket_staff)}"
            ),
            inline=False,
        )

        # Mensagens (com indicador se são customizadas)
        def status_msg(valor: str) -> str:
            return "✏️ Customizada" if valor else "📋 Padrão"

        embed.add_field(
            name="💬 Mensagens",
            value=(
                f"• 👋 Boas-vindas: {status_msg(cfg.msg_bem_vindo)}\n"
                f"• 🎫 Painel tickets: {status_msg(cfg.msg_ticket_panel)}\n"
                f"• 📝 Ticket criado: {status_msg(cfg.msg_ticket_criado)}"
            ),
            inline=False,
        )

        embed.set_footer(text=f"Para editar: /editar")
        await interaction.response.edit_message(embed=embed, view=EditarMenuView(self))

    # ─────────────────────────────────────────────────────────────────────────
    # Republicar painéis
    # ─────────────────────────────────────────────────────────────────────────
    async def menu_republicar(self, interaction: discord.Interaction) -> None:
        cfg = get_config(interaction.guild.id)
        embed = discord.Embed(
            title="🔄 Replicar Painéis",
            description=(
                "Escolhe qual painel queres replicar (reenviar) nos canais configurados.\n\n"
                "💡 Útil para aplicar novas mensagens customizadas aos painéis já existentes."
            ),
            color=Cores.DOURADO,
        )
        embed.set_footer(text=cfg.nome_servidor)
        await interaction.response.edit_message(
            embed=embed, view=RepublicarView(self)
        )

    async def republicar_regras(self, interaction: discord.Interaction) -> None:
        cfg = get_config(interaction.guild.id)
        if not cfg.canal_regras:
            await interaction.response.send_message(
                embed=embed_erro("Sem canal", "Canal de regras não configurado.", cfg.nome_servidor),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        canal = interaction.guild.get_channel(cfg.canal_regras)
        if canal is None:
            await interaction.followup.send(
                embed=embed_erro("Erro", "Canal de regras não encontrado.", cfg.nome_servidor),
                ephemeral=True,
            )
            return

        from cogs.regras import construir_embeds_regras
        guild_icon = interaction.guild.icon.url if interaction.guild.icon else None
        embeds = construir_embeds_regras(guild_icon, cfg.nome_servidor)

        # Apaga mensagens anteriores do bot
        try:
            async for m in canal.history(limit=20):
                if m.author == interaction.guild.me:
                    await m.delete()
        except discord.HTTPException:
            pass

        for i in range(0, len(embeds), 10):
            await canal.send(embeds=embeds[i:i + 10])

        await interaction.followup.send(
            embed=embed_sucesso(
                "Painel replicado!",
                f"Regras reenviadas em {canal.mention}.",
                cfg.nome_servidor,
            ),
            ephemeral=True,
        )

    async def republicar_boas_vindas(self, interaction: discord.Interaction) -> None:
        cfg = get_config(interaction.guild.id)
        if not cfg.canal_bem_vindas:
            await interaction.response.send_message(
                embed=embed_erro("Sem canal", "Canal de boas-vindas não configurado.", cfg.nome_servidor),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        canal = interaction.guild.get_channel(cfg.canal_bem_vindas)
        if canal is None:
            await interaction.followup.send(
                embed=embed_erro("Erro", "Canal não encontrado.", cfg.nome_servidor),
                ephemeral=True,
            )
            return

        # Usa a mensagem de boas-vindas (não há mais verificação)
        msg = cfg.get_msg_bem_vindo()
        msg = msg.replace("{user}", interaction.user.mention)
        msg = msg.replace("{count}", str(interaction.guild.member_count or 0))
        msg = msg.replace("{regras}", f"<#{cfg.canal_regras}>" if cfg.canal_regras else "#regras")
        msg = msg.replace("{tickets}", f"<#{cfg.canal_tickets}>" if cfg.canal_tickets else "#tickets")

        embed = discord.Embed(
            title=f"{Emojis.BEM_VINDO} Bem-vindo à {cfg.nome_servidor}!",
            description=msg,
            color=Cores.VERMELHO,
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=f"{cfg.nome_servidor} • Canal de Boas-vindas")

        # Apaga mensagens anteriores do bot
        try:
            async for m in canal.history(limit=20):
                if m.author == interaction.guild.me:
                    await m.delete()
        except discord.HTTPException:
            pass

        await canal.send(embed=embed)
        await interaction.followup.send(
            embed=embed_sucesso(
                "Painel replicado!",
                f"Boas-vindas reenviadas em {canal.mention}.",
                cfg.nome_servidor,
            ),
            ephemeral=True,
        )

    async def republicar_tickets(self, interaction: discord.Interaction) -> None:
        cfg = get_config(interaction.guild.id)
        if not cfg.canal_tickets:
            await interaction.response.send_message(
                embed=embed_erro("Sem canal", "Canal de tickets não configurado.", cfg.nome_servidor),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        canal = interaction.guild.get_channel(cfg.canal_tickets)
        if canal is None:
            await interaction.followup.send(
                embed=embed_erro("Erro", "Canal não encontrado.", cfg.nome_servidor),
                ephemeral=True,
            )
            return

        from cogs.tickets import PainelTicketsView
        cog_tickets = self.bot.get_cog("TicketsCog")
        if cog_tickets is None:
            await interaction.followup.send(
                embed=embed_erro(
                    "🚫 Erro",
                    "Sistema de tickets não está disponível. Tenta novamente mais tarde.",
                    cfg.nome_servidor,
                ),
                ephemeral=True,
            )
            return

        categorias = cfg.get_categorias_ticket()
        # Constrói lista formatada para o placeholder {categorias}
        lista_categorias = "\n".join(
            f"• {c.get('emoji', '🎫')} **{c['nome']}** — {c.get('descricao', '')}"
            for c in categorias
        )

        msg = cfg.get_msg_ticket_panel()
        msg = msg.replace("{regras}", f"<#{cfg.canal_regras}>" if cfg.canal_regras else "#regras")
        msg = msg.replace("{categorias}", lista_categorias)

        embed = discord.Embed(
            title=f"{Emojis.TICKET} {cfg.nome_servidor} — Ticket System",
            description=msg,
            color=Cores.VERMELHO,
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=f"{cfg.nome_servidor} • Sistema de Tickets")

        # Apaga mensagens anteriores do bot
        try:
            async for m in canal.history(limit=20):
                if m.author == interaction.guild.me:
                    await m.delete()
        except discord.HTTPException:
            pass

        await canal.send(embed=embed, view=PainelTicketsView(cog_tickets, categorias))
        await interaction.followup.send(
            embed=embed_sucesso(
                "Painel replicado!",
                f"Tickets reenviados em {canal.mention}.",
                cfg.nome_servidor,
            ),
            ephemeral=True,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Reset completo
    # ─────────────────────────────────────────────────────────────────────────
    async def confirmar_reset(self, interaction: discord.Interaction) -> None:
        cfg = get_config(interaction.guild.id)
        embed = discord.Embed(
            title="⚠️ Confirmar Reset Completo",
            description=(
                f"{interaction.user.mention}, vais **apagar toda a configuração** do bot neste servidor.\n\n"
                f"**O que vai ser apagado:**\n"
                f"• IDs de canais e cargos\n"
                f"• Mensagens customizadas\n"
                f"• Estado do setup\n\n"
                f"**NÃO vai ser apagado:**\n"
                f"• Canais e cargos já criados no Discord (apenas a referência no bot)\n"
                f"• Painéis já publicados\n\n"
                f"⚠️ Depois do reset tens de executar `/setup` novamente."
            ),
            color=Cores.ERRO,
        )
        embed.set_footer(text=cfg.nome_servidor)
        await interaction.response.edit_message(
            embed=embed, view=ConfirmarResetView(self)
        )

    async def executar_reset(self, interaction: discord.Interaction) -> None:
        from config import GuildConfig, _cache
        cfg = GuildConfig(guild_id=interaction.guild.id)
        save_config(cfg)
        # Limpa cache
        _cache.pop(interaction.guild.id, None)

        embed = embed_sucesso(
            "✅ Reset concluído",
            f"Toda a configuração foi apagada.\nExecuta `/setup` para reconfigurar o bot.",
            "Rede Tuga",
        )
        await interaction.response.edit_message(embed=embed, view=None)

        await log_evento(
            self.bot,
            "⚠️ Reset de configuração",
            f"Configuração apagada por {interaction.user.mention}.\n"
            f"Servidor: {interaction.guild.name}",
            Cores.ERRO,
            interaction.user,
            interaction.guild,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Comando: /config_status (atalho)
    # ─────────────────────────────────────────────────────────────────────────
    @app_commands.command(
        name="config_status",
        description="📋 Ver a configuração atual do Tuguinha (admin)",
    )
    @app_commands.default_permissions(administrator=True)
    async def cmd_status(self, interaction: discord.Interaction) -> None:
        if not await check_admin_and_respond(interaction):
            return
        # Reutiliza mostrar_status mas como resposta nova
        cfg = get_config(interaction.guild.id)

        def canal_mention(cid: int) -> str:
            if not cid:
                return "❌ Não configurado"
            ch = interaction.guild.get_channel(cid)
            return ch.mention if ch else f"❌ ID {cid}"

        def cargo_mention(rid: int) -> str:
            if not rid:
                return "❌ Não configurado"
            r = interaction.guild.get_role(rid)
            return r.mention if r else f"❌ ID {rid}"

        embed = discord.Embed(
            title=f"📋 Configuração — {cfg.nome_servidor}",
            color=Cores.VERDE if cfg.setup_completo else Cores.AVISO,
        )
        embed.add_field(
            name="📊 Estado",
            value=f"Setup: {'✅' if cfg.setup_completo else '❌'}\nBoas-vindas: {'✅' if cfg.boas_vindas_ativas else '🚫'}",
            inline=False,
        )
        embed.add_field(
            name="📢 Canais",
            value=(
                f"📜 {canal_mention(cfg.canal_regras)}\n"
                f"👋 {canal_mention(cfg.canal_bem_vindas)}\n"
                f"🎫 {canal_mention(cfg.canal_tickets)}\n"
                f"📋 {canal_mention(cfg.canal_logs)}\n"
                f"📝 {canal_mention(cfg.canal_transcript)}"
            ),
            inline=True,
        )
        embed.add_field(
            name="🎭 Cargos",
            value=(
                f"👑 {cargo_mention(cfg.cargo_admin)}\n"
                f"🛡️ {cargo_mention(cfg.cargo_staff)}\n"
                f"🎫 {cargo_mention(cfg.cargo_ticket_staff)}"
            ),
            inline=True,
        )
        embed.set_footer(text="Usa /editar para modificar")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EditarCog(bot))
