"""
Cog Geral — painel unificado /geral + /painel_boas_vindas customizável.

/geral:
  Painel único com botões para aceder a todos os menus do bot:
  • Setup
  • Editar config
  • Status da config
  • Painel de regras
  • Painel de tickets
  • Painel de boas-vindas
  • Anunciar
  • Anunciar agendado
  • Falar
  • Falar embed
  • Sugestões (info)

/painel_boas_vindas:
  Permite ao admin escolher:
  • Canal de boas-vindas (select menu com canais existentes)
  • Ativar/desativar boas-vindas
  • Editar mensagem de boas-vindas
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import Cores, Emojis, get_config, save_config
from utils import (
    embed_aviso,
    embed_erro,
    embed_sucesso,
    e_admin,
    log_evento,
    mention_canal_regras,
)


# ─────────────────────────────────────────────────────────────────────────────
# View do painel /geral
# ─────────────────────────────────────────────────────────────────────────────
class PainelGeralView(discord.ui.View):
    """Painel único com botões para todas as funcionalidades do Tuguinha."""

    def __init__(self, cog: "GeralCog") -> None:
        super().__init__(timeout=300)
        self.cog = cog

    @discord.ui.button(label="Setup", emoji="🚀", style=discord.ButtonStyle.success, row=0)
    async def btn_setup(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message(
                "🚫 Apenas admins.", ephemeral=True,
            )
            return
        # Encaminha para o comando /setup
        setup_cog = interaction.client.get_cog("SetupCog")
        if setup_cog is None:
            await interaction.response.send_message(
                "❌ Cog de setup não disponível.", ephemeral=True,
            )
            return
        await setup_cog.cmd_setup.callback(setup_cog, interaction)

    @discord.ui.button(label="Editar", emoji="📝", style=discord.ButtonStyle.primary, row=0)
    async def btn_editar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message("🚫 Apenas admins.", ephemeral=True)
            return
        editar_cog = interaction.client.get_cog("EditarCog")
        if editar_cog is None:
            await interaction.response.send_message("❌ Cog de edição não disponível.", ephemeral=True)
            return
        await editar_cog.cmd_editar.callback(editar_cog, interaction)

    @discord.ui.button(label="Status", emoji="📋", style=discord.ButtonStyle.secondary, row=0)
    async def btn_status(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message("🚫 Apenas admins.", ephemeral=True)
            return
        editar_cog = interaction.client.get_cog("EditarCog")
        if editar_cog is None:
            await interaction.response.send_message("❌ Cog não disponível.", ephemeral=True)
            return
        await editar_cog.cmd_status.callback(editar_cog, interaction)

    @discord.ui.button(label="Regras", emoji="📜", style=discord.ButtonStyle.primary, row=1)
    async def btn_regras(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message("🚫 Apenas admins.", ephemeral=True)
            return
        regras_cog = interaction.client.get_cog("RegrasCog")
        if regras_cog is None:
            await interaction.response.send_message("❌ Cog de regras não disponível.", ephemeral=True)
            return
        await regras_cog.regras.callback(regras_cog, interaction)

    @discord.ui.button(label="Tickets", emoji="🎫", style=discord.ButtonStyle.primary, row=1)
    async def btn_tickets(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message("🚫 Apenas admins.", ephemeral=True)
            return
        tickets_cog = interaction.client.get_cog("TicketsCog")
        if tickets_cog is None:
            await interaction.response.send_message("❌ Cog de tickets não disponível.", ephemeral=True)
            return
        await tickets_cog.painel_tickets.callback(tickets_cog, interaction)

    @discord.ui.button(label="Boas-vindas", emoji="👋", style=discord.ButtonStyle.primary, row=1)
    async def btn_boas_vindas(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message("🚫 Apenas admins.", ephemeral=True)
            return
        await self.cog.cmd_painel_boas_vindas.callback(self.cog, interaction)

    @discord.ui.button(label="Anunciar", emoji="📢", style=discord.ButtonStyle.primary, row=2)
    async def btn_anunciar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message("🚫 Apenas admins.", ephemeral=True)
            return
        anuncios_cog = interaction.client.get_cog("AnunciosCog")
        if anuncios_cog is None:
            await interaction.response.send_message("❌ Cog de anúncios não disponível.", ephemeral=True)
            return
        await anuncios_cog.cmd_anunciar.callback(anuncios_cog, interaction)

    @discord.ui.button(label="Agendar", emoji="📅", style=discord.ButtonStyle.primary, row=2)
    async def btn_agendar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message("🚫 Apenas admins.", ephemeral=True)
            return
        anuncios_cog = interaction.client.get_cog("AnunciosCog")
        if anuncios_cog is None:
            await interaction.response.send_message("❌ Cog de anúncios não disponível.", ephemeral=True)
            return
        await anuncios_cog.cmd_anunciar_agendar.callback(anuncios_cog, interaction)

    @discord.ui.button(label="Falar", emoji="💬", style=discord.ButtonStyle.primary, row=2)
    async def btn_falar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message("🚫 Apenas admins.", ephemeral=True)
            return
        # /falar precisa de args; mostra instruções
        await interaction.response.send_message(
            embed=embed_aviso(
                "💬 /falar",
                "Para usar `/falar`, executa o comando diretamente:\n```\n/falar canal:#canal mensagem:Olá!\n```",
                get_config(interaction.guild.id).nome_servidor,
            ),
            ephemeral=True,
        )

    @discord.ui.button(label="Ajuda", emoji="❓", style=discord.ButtonStyle.secondary, row=3)
    async def btn_ajuda(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # /ajuda é global — encaminha chamando diretamente
        # Como está registado no tree, chamamos o callback via interaction
        # Basta reenviar a mensagem de ajuda
        from main import bot
        # Procura o comando no tree
        cmd = bot.tree.get_command("ajuda")
        if cmd:
            await cmd.callback(interaction)
        else:
            await interaction.response.send_message(
                "❓ Usa `/ajuda` para ver todos os comandos.", ephemeral=True,
            )


# ─────────────────────────────────────────────────────────────────────────────
# View do painel de boas-vindas
# ─────────────────────────────────────────────────────────────────────────────
class PainelBoasVindasView(discord.ui.View):
    """Painel para configurar boas-vindas (canal + ativar/desativar + mensagem)."""

    def __init__(self, cog: "GeralCog", guild: discord.Guild) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.guild = guild
        self.cfg = get_config(guild.id)

        # 1. Select de canal de boas-vindas
        canais = list(guild.text_channels[:22])
        options_bv = [
            discord.SelectOption(
                label=f"#{c.name}"[:100],
                value=str(c.id),
                description="Canal existente",
                emoji="📢",
            )
            for c in canais
        ]
        if self.cfg.canal_bem_vindas:
            ch_atual = guild.get_channel(self.cfg.canal_bem_vindas)
            if ch_atual:
                options_bv.insert(0, discord.SelectOption(
                    label=f"✅ Atual: #{ch_atual.name}"[:100],
                    value=str(ch_atual.id),
                    description="Manter canal atual",
                    emoji="✅",
                ))
        options_bv.append(discord.SelectOption(
            label="🚫 Desativar boas-vindas",
            value="off",
            description="Desativar o sistema de boas-vindas",
            emoji="🚫",
        ))

        self.select_canal = discord.ui.Select(
            placeholder="👋 Escolhe o canal de boas-vindas",
            options=options_bv,
            min_values=1, max_values=1,
        )
        self.select_canal.callback = self._on_canal
        self.add_item(self.select_canal)

        # 2. Botão editar mensagem
        self.btn_msg = discord.ui.Button(
            label="Editar mensagem",
            emoji="✏️",
            style=discord.ButtonStyle.primary,
            row=1,
        )
        self.btn_msg.callback = self._on_editar_msg
        self.add_item(self.btn_msg)

        # 3. Botão testar boas-vindas
        self.btn_testar = discord.ui.Button(
            label="Testar",
            emoji="🧪",
            style=discord.ButtonStyle.secondary,
            row=1,
        )
        self.btn_testar.callback = self._on_testar
        self.add_item(self.btn_testar)

        # 4. Botão voltar
        self.btn_voltar = discord.ui.Button(
            label="↩️ Voltar",
            emoji="↩️",
            style=discord.ButtonStyle.secondary,
            row=1,
        )
        self.btn_voltar.callback = self._on_voltar
        self.add_item(self.btn_voltar)

    async def _on_canal(self, interaction: discord.Interaction) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message("🚫 Apenas admins.", ephemeral=True)
            return
        # Lê config fresca (evita sobrescrever alterações de outros admins)
        cfg = get_config(self.guild.id)
        valor = self.select_canal.values[0]
        if valor == "off":
            cfg.boas_vindas_ativas = False
            save_config(cfg)
            await interaction.response.send_message(
                embed=embed_sucesso(
                    "🚫 Boas-vindas desativadas",
                    "O sistema de boas-vindas foi desativado.",
                    cfg.nome_servidor,
                ),
                ephemeral=True,
            )
            return
        canal_id = int(valor)
        cfg.canal_bem_vindas = canal_id
        cfg.boas_vindas_ativas = True
        save_config(cfg)
        canal = self.guild.get_channel(canal_id)
        await interaction.response.send_message(
            embed=embed_sucesso(
                "✅ Canal atualizado!",
                f"Boas-vindas vão ser enviadas para {canal.mention if canal else f'`{canal_id}`'}.",
                cfg.nome_servidor,
            ),
            ephemeral=True,
        )
        await log_evento(
            interaction.client,
            "👋 Canal de boas-vindas alterado",
            f"Por {interaction.user.mention}\nNovo canal: {canal.mention if canal else valor}",
            Cores.DOURADO,
            interaction.user,
            interaction.guild,
        )

    async def _on_editar_msg(self, interaction: discord.Interaction) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message("🚫 Apenas admins.", ephemeral=True)
            return
        # Lê config fresca
        cfg = get_config(self.guild.id)
        await interaction.response.send_modal(EditarMensagemBVModal(self.cog, cfg))

    async def _on_testar(self, interaction: discord.Interaction) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message("🚫 Apenas admins.", ephemeral=True)
            return
        # Lê config fresca
        cfg = get_config(self.guild.id)
        if not cfg.canal_bem_vindas:
            await interaction.response.send_message(
                embed=embed_erro("🚫 Sem canal", "Configura primeiro um canal de boas-vindas.", cfg.nome_servidor),
                ephemeral=True,
            )
            return
        canal = self.guild.get_channel(cfg.canal_bem_vindas)
        if canal is None:
            await interaction.response.send_message(
                embed=embed_erro("🚫 Canal não encontrado", "O canal configurado já não existe.", cfg.nome_servidor),
                ephemeral=True,
            )
            return

        # Simula boas-vindas do próprio utilizador
        msg = cfg.get_msg_bem_vindo()
        msg = msg.replace("{user}", interaction.user.mention)
        msg = msg.replace("{count}", str(self.guild.member_count or 0))
        msg = msg.replace("{regras}", mention_canal_regras(cfg))
        msg = msg.replace("{tickets}", f"<#{cfg.canal_tickets}>" if cfg.canal_tickets else "#tickets")

        embed = discord.Embed(
            title=f"{Emojis.BEM_VINDO} Bem-vindo à {cfg.nome_servidor}! (TESTE)",
            description=msg,
            color=Cores.VERMELHO,
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"🧪 Teste • {cfg.nome_servidor}")

        try:
            await canal.send(embed=embed)
            await interaction.response.send_message(
                embed=embed_sucesso("🧪 Teste enviado!", f"Enviei uma mensagem de teste para {canal.mention}.", self.cfg.nome_servidor),
                ephemeral=True,
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                embed=embed_erro("🚫 Erro", "Falha ao enviar teste.", self.cfg.nome_servidor),
                ephemeral=True,
            )

    async def _on_voltar(self, interaction: discord.Interaction) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message("🚫 Apenas admins.", ephemeral=True)
            return
        await self.cog.cmd_geral.callback(self.cog, interaction)


class EditarMensagemBVModal(discord.ui.Modal):
    def __init__(self, cog: "GeralCog", cfg) -> None:
        super().__init__(title="✏️ Editar mensagem de boas-vindas", timeout=600)
        self.cog = cog
        self.cfg = cfg

        self.mensagem = discord.ui.TextInput(
            label="👋 Mensagem de boas-vindas",
            placeholder="Placeholders: {user} {count} {regras} {tickets}. Deixa vazio = padrão.",
            style=discord.TextStyle.paragraph,
            default=cfg.msg_bem_vindo if cfg.msg_bem_vindo else "",
            max_length=1000,
            required=False,
        )
        self.add_item(self.mensagem)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.cfg.msg_bem_vindo = self.mensagem.value.strip()
        save_config(self.cfg)
        await interaction.response.send_message(
            embed=embed_sucesso(
                "✅ Mensagem atualizada!",
                f"Estado: {'✏️ Customizada' if self.cfg.msg_bem_vindo else '📋 Padrão (vazio)'}\n\n"
                f"💡 Usa o botão **🧪 Testar** para ver como fica.",
                self.cfg.nome_servidor,
            ),
            ephemeral=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Cog principal
# ─────────────────────────────────────────────────────────────────────────────
class GeralCog(commands.Cog):
    """Painel unificado /geral + gestão de boas-vindas."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="geral",
        description="🎛️ Painel geral com todos os menus do Tuguinha (apenas admins).",
    )
    @app_commands.default_permissions(administrator=True)
    async def cmd_geral(self, interaction: discord.Interaction) -> None:
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
        embed = discord.Embed(
            title=f"🎛️ Painel Geral — Tuguinha 🇵🇹",
            description=(
                f"Olá {interaction.user.mention}! Bem-vindo ao painel de controlo do Tuguinha.\n\n"
                f"📊 **Estado atual:**\n"
                f"• Setup: {'✅ Completo' if cfg.setup_completo else '❌ Pendente'}\n"
                f"• Boas-vindas: {'✅ Ativas' if cfg.boas_vindas_ativas else '🚫 Desativadas'}\n"
                f"• Nome do servidor: **{cfg.nome_servidor}**\n\n"
                f"🎯 **Clica num botão abaixo para aceder à funcionalidade:**"
            ),
            color=Cores.DOURADO,
        )
        embed.set_footer(text=f"Tuguinha • {cfg.nome_servidor} • Apenas admins")
        await interaction.response.send_message(
            embed=embed,
            view=PainelGeralView(self),
            ephemeral=True,
        )

    @app_commands.command(
        name="painel_boas_vindas",
        description="👋 Configura o sistema de boas-vindas (canal + mensagem) (apenas admins).",
    )
    @app_commands.default_permissions(administrator=True)
    async def cmd_painel_boas_vindas(self, interaction: discord.Interaction) -> None:
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
        canal_atual = "— não configurado —"
        if cfg.canal_bem_vindas:
            ch = interaction.guild.get_channel(cfg.canal_bem_vindas)
            if ch:
                canal_atual = ch.mention

        embed = discord.Embed(
            title="👋 Painel de Boas-vindas",
            description=(
                f"Configura como o Tuguinha recebe novos membros.\n\n"
                f"📊 **Estado atual:**\n"
                f"• Ativo: {'✅ Sim' if cfg.boas_vindas_ativas else '🚫 Não'}\n"
                f"• Canal: {canal_atual}\n"
                f"• Mensagem: {'✏️ Customizada' if cfg.msg_bem_vindo else '📋 Padrão'}\n\n"
                f"**Placeholders disponíveis:**\n"
                f"• `{{user}}` — menção do membro\n"
                f"• `{{count}}` — nº de membros\n"
                f"• `{{regras}}` — menção do canal de regras\n"
                f"• `{{tickets}}` — menção do canal de tickets\n\n"
                f"🎯 **Usa os botões abaixo:**"
            ),
            color=Cores.VERMELHO,
        )
        embed.set_footer(text=f"{cfg.nome_servidor} • Apenas admins")
        await interaction.response.send_message(
            embed=embed,
            view=PainelBoasVindasView(self, interaction.guild),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GeralCog(bot))
