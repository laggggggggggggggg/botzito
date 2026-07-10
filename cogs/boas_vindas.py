"""
Cog de Boas-Vindas — envia embed personalizada quando um membro entra,
envia DM com resumo das regras e gere o botão de verificação.
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import Cores, Emojis, get_config
from utils import embed_erro, embed_sucesso, log_evento


class VerificacaoView(discord.ui.View):
    """Botão persistente que atribui o cargo de verificado/membro."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Verificar-me",
        emoji=Emojis.VERIFICAR,
        style=discord.ButtonStyle.success,
        custom_id="rede_tuga:verificar",
    )
    async def verificar(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "❌ Só podes verificar dentro do servidor.", ephemeral=True
            )
            return

        cfg = get_config(interaction.guild.id)
        cargos_adicionados: list[str] = []
        for cargo_id in (cfg.cargo_verificado, cfg.cargo_membro):
            if not cargo_id:
                continue
            cargo = interaction.guild.get_role(cargo_id)
            if cargo is None:
                continue
            if cargo not in member.roles:
                try:
                    await member.add_roles(cargo, reason="Verificação automática")
                    cargos_adicionados.append(cargo.mention)
                except discord.Forbidden:
                    pass

        if cargos_adicionados:
            await interaction.response.send_message(
                embed=embed_sucesso(
                    "Verificação concluída!",
                    f"Recebeste os cargos: {', '.join(cargos_adicionados)}\n"
                    f"Bem-vindo à **{cfg.nome_servidor}**! 🇵🇹 Já podes ver todos os canais.",
                    cfg.nome_servidor,
                ),
                ephemeral=True,
            )
            await log_evento(
                interaction.client,
                "✅ Membro verificado",
                f"{member.mention} completou a verificação e recebeu {len(cargos_adicionados)} cargo(s).",
                Cores.SUCESSO,
                member,
                interaction.guild,
            )
        else:
            await interaction.response.send_message(
                embed=embed_sucesso(
                    "Já estás verificado!",
                    "Todos os teus cargos já estão atribuídos. Bom estar aqui! 🇵🇹",
                    cfg.nome_servidor,
                ),
                ephemeral=True,
            )


class BoasVindasCog(commands.Cog):
    """Sistema de boas-vindas e verificação de membros."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.bot.add_view(VerificacaoView())

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.bot:
            return
        cfg = get_config(member.guild.id)
        # Se o setup ainda não foi feito, não envia boas-vindas avançadas
        if not cfg.setup_completo:
            return

        await self._enviar_boas_vindas_canal(member, cfg)
        await self._enviar_dm(member, cfg)

        await log_evento(
            self.bot,
            f"{Emojis.BEM_VINDO} Novo membro",
            f"{member.mention} entrou no servidor!\n"
            f"Conta criada em <t:{int(member.created_at.timestamp())}:R>.",
            Cores.VERDE,
            member,
            member.guild,
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        if member.bot:
            return
        await log_evento(
            self.bot,
            "👋 Membro saiu",
            f"**{member}** (`{member.id}`) deixou o servidor.",
            Cores.CINZA,
            member,
            member.guild,
        )

    async def _enviar_boas_vindas_canal(self, member: discord.Member, cfg) -> None:
        if not cfg.canal_bem_vindas:
            return
        canal = self.bot.get_channel(cfg.canal_bem_vindas)
        if canal is None:
            return

        guild = member.guild
        membros = guild.member_count or 0

        embed = discord.Embed(
            title=f"{Emojis.BEM_VINDO} Bem-vindo à {cfg.nome_servidor}!",
            description=(
                f"Olá {member.mention}! 🎉\n\n"
                f"És o nosso **{membros}º membro** desta comunidade tuga. 🇵🇹\n\n"
                f"Antes de começares a explorar o servidor:\n"
                f"{Emojis.SETA} Lê as regras em <#{cfg.canal_regras}>\n"
                f"{Emojis.SETA} **Clica no botão verde abaixo para te verificares** e desbloqueares todos os canais\n"
                f"{Emojis.SETA} Escolhe os teus cargos no canal de auto-roles\n\n"
                f"Se precisares de ajuda, abre um ticket em <#{cfg.canal_tickets}>. Boa estadia! 💪"
            ),
            color=Cores.VERMELHO,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        if guild.icon:
            embed.set_author(name=guild.name, icon_url=guild.icon.url)
        embed.set_footer(text=f"Membro #{membros:04d} • {cfg.nome_servidor}")

        view = VerificacaoView()
        try:
            await canal.send(content=member.mention, embed=embed, view=view,
                             allowed_mentions=discord.AllowedMentions(users=True))
        except discord.HTTPException:
            pass

    async def _enviar_dm(self, member: discord.Member, cfg) -> None:
        embed = discord.Embed(
            title=f"{Emojis.REGRAS} Bem-vindo à {cfg.nome_servidor}! 🇵🇹",
            description=(
                f"Olá **{member.name}**! Recebeste as boas-vindas oficiais da nossa comunidade.\n\n"
                f"Antes de começares a interagir, é importante que leias as regras completas "
                f"no servidor. Aqui ficam as **regras essenciais** resumidas:"
            ),
            color=Cores.VERDE,
        )
        embed.add_field(name="🤝 Respeito",
                        value="Trata todos com respeito. Sem insultos, bullying ou discurso de ódio.",
                        inline=False)
        embed.add_field(name="🚫 Proibido",
                        value="NSFW, spam, phishing, pirataria e partilha de dados pessoais.",
                        inline=False)
        embed.add_field(name="🎮 Gaming",
                        value="Sem cheating. Respeita regras dos canais de voz e jogos.",
                        inline=False)
        embed.add_field(name="🎫 Tickets",
                        value="Para suporte, abre ticket em #tickets. Não abras tickets por brincadeira.",
                        inline=False)
        embed.add_field(name="⚖️ Sanções",
                        value="Aviso → mute → ban temporário → ban permanente.",
                        inline=False)
        embed.add_field(name="✅ Próximo passo",
                        value=(
                            f"Vai ao canal <#{cfg.canal_bem_vindas}> e clica no botão **Verificar-me** "
                            f"para desbloqueares o resto do servidor!"
                        ),
                        inline=False)
        embed.set_footer(text=cfg.nome_servidor)

        try:
            await member.send(embed=embed)
        except discord.Forbidden:
            pass

    @app_commands.command(
        name="painel_boas_vindas",
        description="Cria o painel de boas-vindas com botão de verificação (staff).",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def painel_boas_vindas(
        self, interaction: discord.Interaction, canal: discord.TextChannel | None = None
    ) -> None:
        from utils import e_staff

        if not e_staff(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro("Sem permissão", "Apenas a staff pode usar este comando.",
                                 get_config(interaction.guild.id).nome_servidor),
                ephemeral=True,
            )
            return

        cfg = get_config(interaction.guild.id)
        alvo = canal or (self.bot.get_channel(cfg.canal_bem_vindas) if cfg.canal_bem_vindas else interaction.channel)
        if alvo is None:
            await interaction.response.send_message(
                embed=embed_erro("Sem canal", "Indica um canal válido.", cfg.nome_servidor),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"{Emojis.VERIFICAR} Verificação de Membro",
            description=(
                f"Olá! Para teres acesso a todos os canais da **{cfg.nome_servidor}**, "
                f"precisas de te verificar.\n\n"
                f"**Como te verificas?**\n"
                f"{Emojis.SETA} Clica no botão verde **Verificar-me** abaixo\n"
                f"{Emojis.SETA} Receberás automaticamente o cargo de membro\n"
                f"{Emojis.SETA} Já podes explorar o servidor à vontade!\n\n"
                f"Se tiveres problemas, fala com a staff em <#{cfg.canal_tickets}>."
            ),
            color=Cores.VERDE,
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=f"{cfg.nome_servidor} • Sistema de Verificação")

        view = VerificacaoView()
        await alvo.send(embed=embed, view=view)
        await interaction.response.send_message(
            embed=embed_sucesso("Painel criado!",
                                f"Painel de verificação enviado para {alvo.mention}.",
                                cfg.nome_servidor),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BoasVindasCog(bot))
