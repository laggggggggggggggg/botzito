"""
Cog de Sugestões — comando /sugerir que cria embed votável no canal de sugestões.
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import Cores, Emojis, get_config
from utils import embed_aviso, embed_erro, embed_sucesso, log_evento


class SugestoesCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="sugerir",
        description="💡 Envia uma sugestão para o canal de sugestões.",
    )
    @app_commands.describe(
        sugestao="A tua sugestão para o servidor ou comunidade.",
        tipo="Tipo de sugestão.",
    )
    @app_commands.choices(
        tipo=[
            app_commands.Choice(name="🎮 Evento / Atividade", value="evento"),
            app_commands.Choice(name="🛠️ Melhoria do servidor", value="melhoria"),
            app_commands.Choice(name="🎲 Novo jogo/canal", value="jogo"),
            app_commands.Choice(name="💡 Outro", value="outro"),
        ]
    )
    @app_commands.checks.cooldown(1, 300.0, key=commands.BucketType.user)
    async def sugerir(
        self,
        interaction: discord.Interaction,
        sugestao: str,
        tipo: app_commands.Choice[str] | None = None,
    ) -> None:
        cfg = get_config(interaction.guild.id)
        if not cfg.canal_sugestoes:
            await interaction.response.send_message(
                embed=embed_aviso(
                    "Canal não configurado",
                    "O canal de sugestões ainda não foi configurado. Executa `/setup` para o configurar.",
                    cfg.nome_servidor,
                ),
                ephemeral=True,
            )
            return

        canal = self.bot.get_channel(cfg.canal_sugestoes)
        if canal is None or not isinstance(canal, discord.TextChannel):
            await interaction.response.send_message(
                embed=embed_erro("Canal inválido", "Não foi possível aceder ao canal de sugestões.",
                                 cfg.nome_servidor),
                ephemeral=True,
            )
            return

        tipo_label = tipo.name if tipo else "💡 Sugestão"

        embed = discord.Embed(
            title=f"Nova Sugestão — {tipo_label}",
            description=sugestao,
            color=Cores.DOURADO,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_author(
            name=str(interaction.user),
            icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else discord.Embed.Empty,
        )
        embed.set_footer(text=f"ID: {interaction.user.id} • {cfg.nome_servidor}")
        embed.add_field(name="Estado", value="🟡 Em análise", inline=True)
        embed.add_field(name="Votos", value="Aguarda...", inline=True)

        msg = await canal.send(embed=embed)
        try:
            await msg.add_reaction("👍")
            await msg.add_reaction("👎")
            await msg.add_reaction("🤷")
        except discord.HTTPException:
            pass

        await interaction.response.send_message(
            embed=embed_sucesso(
                "Sugestão enviada!",
                f"A tua sugestão foi publicada em {canal.mention}. Obrigado pela tua contribuição! 🙌",
                cfg.nome_servidor,
            ),
            ephemeral=True,
        )

        await log_evento(
            self.bot,
            "💡 Nova sugestão",
            f"Por {interaction.user.mention} em {canal.mention}.\nTipo: {tipo_label}",
            Cores.DOURADO,
            interaction.user,
            interaction.guild,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SugestoesCog(bot))
