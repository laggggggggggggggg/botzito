"""
Cog de Staff — gere quem tem acesso aos comandos do Tuguinha.

Comandos (apenas admins do Discord):
  /staff lista         → mostra todos os membros com acesso
  /staff adicionar     → adiciona um membro à lista de autorizados
  /staff remover       → remove um membro da lista de autorizados

Estes comandos NÃO aparecem para @everyone — apenas para quem tem
permissão de Administrador no Discord.
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import Cores, Emojis, get_config, save_config
from utils import embed_erro, embed_sucesso, embed_aviso, e_admin, log_evento


class StaffCog(commands.Cog):
    """Gestão de staff autorizada a usar o Tuguinha."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="staff",
        description="👥 Gere quem tem acesso aos comandos do Tuguinha (admin).",
    )
    @app_commands.describe(
        acao="O que queres fazer?",
        membro="Membro para adicionar ou remover (obrigatório para adicionar/remover)",
    )
    @app_commands.choices(acao=[
        app_commands.Choice(name="📋 Ver lista de autorizados", value="lista"),
        app_commands.Choice(name="➕ Adicionar membro", value="adicionar"),
        app_commands.Choice(name="➖ Remover membro", value="remover"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def cmd_staff(
        self,
        interaction: discord.Interaction,
        acao: app_commands.Choice[str],
        membro: discord.Member = None,
    ) -> None:
        """Comando de gestão de staff — apenas admins do Discord."""

        # ═══════════════════════════════════════════════════════════════
        # BLOQUEIO DURO: apenas admins do Discord (NÃO staff_autorizada)
        # Isto é intencional — só quem é admin do Discord pode gerir a lista
        # ═══════════════════════════════════════════════════════════════
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                embed=embed_erro("🚫 Sem permissão", "Este comando só funciona em servidores."),
                ephemeral=True,
            )
            return

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=embed_erro(
                    "🚫 Sem permissão",
                    "Apenas **administradores do Discord** podem gerir a staff.\n\n"
                    "Membros autorizados via `/staff adicionar` podem **usar** os comandos do bot,\n"
                    "mas **não podem** gerir a lista de staff.",
                    get_config(interaction.guild.id).nome_servidor,
                ),
                ephemeral=True,
            )
            return

        cfg = get_config(interaction.guild.id)

        # ─── LISTA ─────────────────────────────────────────────────────
        if acao.value == "lista":
            await self._mostrar_lista(interaction, cfg)

        # ─── ADICIONAR ─────────────────────────────────────────────────
        elif acao.value == "adicionar":
            if membro is None:
                await interaction.response.send_message(
                    embed=embed_erro(
                        "🚫 Em falta",
                        "Indica o membro que queres adicionar.",
                        cfg.nome_servidor,
                    ),
                    ephemeral=True,
                )
                return
            await self._adicionar(interaction, cfg, membro)

        # ─── REMOVER ───────────────────────────────────────────────────
        elif acao.value == "remover":
            if membro is None:
                await interaction.response.send_message(
                    embed=embed_erro(
                        "🚫 Em falta",
                        "Indica o membro que queres remover.",
                        cfg.nome_servidor,
                    ),
                    ephemeral=True,
                )
                return
            await self._remover(interaction, cfg, membro)

    async def _mostrar_lista(self, interaction: discord.Interaction, cfg) -> None:
        """Mostra todos os membros com acesso aos comandos do bot."""
        embed = discord.Embed(
            title=f"👥 Staff Autorizada — {cfg.nome_servidor}",
            description=(
                "Estes membros podem usar **todos os comandos** do Tuguinha.\n\n"
                "**Quem tem acesso automático:**\n"
                "• 👑 Administradores do Discord (permissão Administrator)\n"
                "• 👑 Donos do bot (se configurado em DONOS_IDS)\n"
            ),
            color=Cores.DOURADO,
            timestamp=discord.utils.utcnow(),
        )

        # Lista de membros autorizados via /staff
        staff_ids = cfg.staff_autorizada or []
        if staff_ids:
            linhas = []
            for i, uid in enumerate(staff_ids, start=1):
                # Tenta encontrar o membro no servidor
                membro = interaction.guild.get_member(uid)
                if membro:
                    linhas.append(f"{i}. {membro.mention} — `{membro}` (`{uid}`)")
                else:
                    linhas.append(f"{i}. ⚠️ Utilizador não encontrado — `{uid}`")
            embed.add_field(
                name=f"✅ Membros autorizados via /staff ({len(staff_ids)})",
                value="\n".join(linhas),
                inline=False,
            )
        else:
            embed.add_field(
                name="✅ Membros autorizados via /staff",
                value="*(nenhum — usa `/staff adicionar` para adicionar)*",
                inline=False,
            )

        embed.set_footer(text=f"{cfg.nome_servidor} • Gestão de Staff")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _adicionar(
        self, interaction: discord.Interaction, cfg, membro: discord.Member
    ) -> None:
        """Adiciona um membro à lista de staff autorizada."""
        # Não permite adicionar bots
        if membro.bot:
            await interaction.response.send_message(
                embed=embed_erro(
                    "🚫 Bot",
                    "Não podes adicionar bots à lista de staff.",
                    cfg.nome_servidor,
                ),
                ephemeral=True,
            )
            return

        # Verifica se já está na lista
        if not cfg.staff_autorizada:
            cfg.staff_autorizada = []

        if membro.id in cfg.staff_autorizada:
            await interaction.response.send_message(
                embed=embed_aviso(
                    "ℹ️ Já autorizado",
                    f"{membro.mention} já está na lista de staff autorizada.",
                    cfg.nome_servidor,
                ),
                ephemeral=True,
            )
            return

        # Verifica se já é admin do Discord (redundante mas informativo)
        if membro.guild_permissions.administrator:
            await interaction.response.send_message(
                embed=embed_aviso(
                    "ℹ️ Já é admin",
                    f"{membro.mention} já é **administrador do Discord** — não precisa de ser adicionado.",
                    cfg.nome_servidor,
                ),
                ephemeral=True,
            )
            return

        # Adiciona
        cfg.staff_autorizada.append(membro.id)
        save_config(cfg)

        await interaction.response.send_message(
            embed=embed_sucesso(
                "➕ Membro adicionado!",
                f"{membro.mention} foi adicionado à staff autorizada.\n\n"
                f"A partir de agora, este membro pode usar **todos os comandos** do Tuguinha:\n"
                f"• `/setup`, `/editar`, `/regras`, `/painel_tickets`\n"
                f"• `/anunciar`, `/falar`, `/embed`\n"
                f"• `/giveaway`, etc.\n\n"
                f"⚠️ Este membro **não pode** usar `/staff` (apenas admins do Discord).",
                cfg.nome_servidor,
            ),
            ephemeral=True,
        )

        await log_evento(
            self.bot,
            "➕ Staff adicionada",
            f"Por {interaction.user.mention}\nAdicionado: {membro.mention} (`{membro.id}`)",
            Cores.DOURADO,
            interaction.user,
            interaction.guild,
        )

    async def _remover(
        self, interaction: discord.Interaction, cfg, membro: discord.Member
    ) -> None:
        """Remove um membro da lista de staff autorizada."""
        if not cfg.staff_autorizada or membro.id not in cfg.staff_autorizada:
            await interaction.response.send_message(
                embed=embed_aviso(
                    "ℹ️ Não está na lista",
                    f"{membro.mention} não está na lista de staff autorizada.",
                    cfg.nome_servidor,
                ),
                ephemeral=True,
            )
            return

        cfg.staff_autorizada.remove(membro.id)
        save_config(cfg)

        await interaction.response.send_message(
            embed=embed_sucesso(
                "➖ Membro removido!",
                f"{membro.mention} foi removido da staff autorizada.\n"
                f"Este membro já não pode usar os comandos do Tuguinha.",
                cfg.nome_servidor,
            ),
            ephemeral=True,
        )

        await log_evento(
            self.bot,
            "➖ Staff removida",
            f"Por {interaction.user.mention}\nRemovido: {membro.mention} (`{membro.id}`)",
            Cores.ERRO,
            interaction.user,
            interaction.guild,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StaffCog(bot))
