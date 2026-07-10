"""
Cog de Regras — envia o painel de regras completo no canal configurado.
Lê as regras de data/regras.json, podendo ser editadas sem mexer no código.
"""
from __future__ import annotations

import json

import discord
from discord import app_commands
from discord.ext import commands

from config import Cores, Emojis, REGRAS_FILE, get_config
from utils import embed_aviso, embed_erro, e_admin, log_evento


def carregar_regras() -> dict:
    if REGRAS_FILE.exists():
        try:
            with REGRAS_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            import logging
            logging.getLogger("rede_tuga.regras").warning(
                "Falha ao ler %s: %s — usando regras padrão", REGRAS_FILE, e
            )
    return _regras_default()


def _regras_default() -> dict:
    return {
        "titulo": "📜 Regras da Rede Tuga",
        "intro": (
            "Bem-vindo à **Rede Tuga**! 🇵🇹\n\n"
            "Para garantir uma boa experiência a todos os membros, "
            "pedimos que leias e respeites as seguintes regras. "
            "Ao permaneceres no servidor, aceitas automaticamente estas normas.\n\n"
            "⚠️ O desconhecimento das regras **não isenta** do seu cumprimento."
        ),
        "secoes": [
            {
                "emoji": "🤝",
                "titulo": "1. Respeito Mútuo",
                "itens": [
                    "Trata todos os membros com respeito, independentemente de idade, género, orientação, religião ou nacionalidade.",
                    "Proibido insultos, provocações, bullying ou discurso de ódio.",
                    "Conflitos pessoais devem ser resolvidos em privado, não no chat público.",
                    "Respeita opiniões divergentes — debater é saudável, agredir não.",
                ],
            },
            {
                "emoji": "🚫",
                "titulo": "2. Conduta Proibida",
                "itens": [
                    "Sem conteúdo NSFW (pornográfico, gore, ou inapropriado para menores).",
                    "Proibido spam, flood, raid ou self-promotion descontrolada.",
                    "Proibido partilhar links maliciosos, phishing ou downloads piratas.",
                    "Proibido disclosing de dados pessoais (teus ou de terceiros).",
                    "Proibido uso de alts para contornar sanções — resultará em ban direto.",
                ],
            },
            {
                "emoji": "🎮",
                "titulo": "3. Gaming e Voz",
                "itens": [
                    "Nos canais de voz, mantém o microfone em push-to-talk se houver ruído de fundo.",
                    "Não grites, não toques música alta sem permissão, não faças earrape.",
                    "Respeita as regras específicas de cada jogo anunciadas em #info-jogos.",
                    "Proibido cheating, hacking ou glitching em servidores oficiais da Rede Tuga.",
                    "Em partidas competitivas, mantém espírito desportivo — sem flame à equipa.",
                ],
            },
            {
                "emoji": "🇵🇹",
                "titulo": "4. Identidade e Cargos",
                "itens": [
                    "Podes escolher cargos no canal #auto-roles para personalizar a tua experiência.",
                    "Não pedires cargos de staff — as candidaturas abrem por iniciativa da equipa.",
                    "Nomes de utilizador e apelidos devem ser legíveis — sem símbolos ofensivos.",
                    "Avatares e banners ofensivos serão removidos — staff reserva-se o direito de os alterar.",
                ],
            },
            {
                "emoji": "🎫",
                "titulo": "5. Tickets e Suporte",
                "itens": [
                    "Para qualquer dúvida ou problema, abre um ticket no canal #tickets.",
                    "Não abras tickets sem motivo válido ou para brincadeiras.",
                    "Mantém o respeito na conversa com a staff — são voluntários a ajudar-te.",
                    "Tickets inativos por 7 dias são automaticamente arquivados.",
                    "Não pingues a staff repetidamente dentro do ticket — serás atendido quando possível.",
                ],
            },
            {
                "emoji": "📢",
                "titulo": "6. Publicidade e Parcerias",
                "itens": [
                    "Proibido publicitar outros servidores Discord sem autorização prévia da staff.",
                    "Para parcerias, abre ticket na categoria 'Parcerias'.",
                    "Proibido partilhar links de afiliados sem autorização.",
                    "Proibido DM-spam a membros do servidor com publicidade — denuncia se acontecer.",
                ],
            },
            {
                "emoji": "⚖️",
                "titulo": "7. Sanções",
                "itens": [
                    "O não conhecimento das regras não isenta do seu cumprimento.",
                    "Sanções: aviso verbal → mute temporário → ban temporário → ban permanente.",
                    "Decisões da staff são finais. Para recorrer, abre ticket na categoria 'Apelar Ban'.",
                    "A gravidade da infração dita o salto de sanção — infrações graves podem levar a ban direto.",
                    "Membros sancionados perdem o direito a eventos VIP durante 30 dias.",
                ],
            },
            {
                "emoji": "🎁",
                "titulo": "8. Doações e VIP",
                "itens": [
                    "As doações são voluntárias e não reembolsáveis.",
                    "Benefícios VIP estão descritos no canal #beneficios-vip.",
                    "Proibido usar VIP como ameaça ou chantagem — resultará em revogação.",
                    "Para questões sobre doações, abre ticket na categoria 'Doações / VIP'.",
                ],
            },
        ],
        "footer": (
            "Obrigado pela tua colaboração! Vamos juntos fazer desta a melhor comunidade tuga. 🇵🇹\n"
            "Em caso de dúvida, fala com a staff no canal #tickets."
        ),
    }


def construir_embeds_regras(guild_icon: str | None = None, nome_servidor: str = "Rede Tuga") -> list[discord.Embed]:
    dados = carregar_regras()
    embeds: list[discord.Embed] = []

    capa = discord.Embed(
        title=dados.get("titulo", "📜 Regras"),
        description=dados.get("intro", ""),
        color=Cores.VERMELHO,
    )
    if guild_icon:
        capa.set_thumbnail(url=guild_icon)
    capa.set_footer(text=f"{nome_servidor} • Lê com atenção")
    embeds.append(capa)

    for sec in dados.get("secoes", []):
        embed = discord.Embed(
            title=f"{sec.get('emoji', '📌')} {sec.get('titulo', 'Secção')}",
            color=Cores.VERDE,
        )
        for i, item in enumerate(sec.get("itens", []), start=1):
            embed.add_field(name=f"{Emojis.SETA} {i}", value=item, inline=False)
        embed.set_footer(text=nome_servidor)
        embeds.append(embed)

    final = discord.Embed(
        title="✨ Bem-vindo à comunidade!",
        description=dados.get("footer", ""),
        color=Cores.DOURADO,
    )
    if guild_icon:
        final.set_thumbnail(url=guild_icon)
    embeds.append(final)

    return embeds


class RegrasCog(commands.Cog):
    """Gestão do painel de regras do servidor."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="regras",
        description="📜 Envia o painel de regras no canal atual ou configurado (admin).",
    )
    @app_commands.describe(
        canal="Canal onde enviar as regras (opcional — usa o configurado por defeito).",
    )
    @app_commands.default_permissions(administrator=True)
    async def regras(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel | None = None,
    ) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro("🚫 Sem permissão",
                                 "Apenas **administradores** podem usar este comando.",
                                 get_config(interaction.guild.id).nome_servidor),
                ephemeral=True,
            )
            return

        cfg = get_config(interaction.guild.id)
        alvo = canal or (self.bot.get_channel(cfg.canal_regras) if cfg.canal_regras else None)
        if alvo is None:
            await interaction.response.send_message(
                embed=embed_aviso(
                    "Canal não definido",
                    "Executa `/setup` primeiro ou indica um canal manualmente.",
                    cfg.nome_servidor,
                ),
                ephemeral=True,
            )
            return

        if not alvo.permissions_for(interaction.guild.me).send_messages:
            await interaction.response.send_message(
                embed=embed_erro("Sem permissões",
                                 f"O bot não tem permissão para enviar mensagens em {alvo.mention}.",
                                 cfg.nome_servidor),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        guild_icon = interaction.guild.icon.url if interaction.guild and interaction.guild.icon else None
        embeds = construir_embeds_regras(guild_icon, cfg.nome_servidor)

        for i in range(0, len(embeds), 10):
            await alvo.send(embeds=embeds[i:i + 10])

        await interaction.followup.send(
            embed=discord.Embed(
                title=f"{Emojis.VERIFICAR} Regras enviadas",
                description=f"Painel de regras publicado em {alvo.mention}.\nTotal de embeds: **{len(embeds)}**",
                color=Cores.SUCESSO,
            ),
            ephemeral=True,
        )

        await log_evento(
            self.bot,
            "📜 Regras publicadas",
            f"Enviadas por {interaction.user.mention} para {alvo.mention}.",
            Cores.VERDE,
            interaction.user,
            interaction.guild,
        )

    @app_commands.command(
        name="recarregar_regras",
        description="🔄 Recarrega as regras a partir do ficheiro JSON (admin).",
    )
    @app_commands.default_permissions(administrator=True)
    async def recarregar_regras(self, interaction: discord.Interaction) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro("🚫 Sem permissão",
                                 "Apenas **administradores** podem usar este comando.",
                                 get_config(interaction.guild.id).nome_servidor),
                ephemeral=True,
            )
            return
        dados = carregar_regras()
        n_secoes = len(dados.get("secoes", []))
        await interaction.response.send_message(
            embed=discord.Embed(
                title=f"{Emojis.VERIFICAR} Regras recarregadas",
                description=f"Carregadas **{n_secoes}** secções do ficheiro `data/regras.json`.",
                color=Cores.SUCESSO,
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RegrasCog(bot))
