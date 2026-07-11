"""
╔════════════════════════════════════════════════════════════════════════════╗
║                          🇵🇹  TUGUINHA  🇵🇹                                    ║
║                                                                            ║
║  Bot profissional para a comunidade Rede Tuga no Discord.                  ║
║                                                                            ║
║  Setup simples:                                                            ║
║    1. Configura apenas DISCORD_TOKEN nos Secrets do Railway                ║
║    2. Convida o bot para o servidor (com permissão Administrator)          ║
║    3. Executa /setup no Discord — o bot cria tudo automaticamente         ║
║                                                                            ║
║  Funcionalidades (todas configuradas via /setup):                          ║
║    • Painel de regras                                                      ║
║    • Sistema de boas-vindas com DM                                         ║
║    • Sistema completo de tickets (5 categorias customizáveis)              ║
║    • Feedback por DM com estrelas quando ticket é fechado                  ║
║    • Embed builder para anúncios da staff                                  ║
║    • Sistema de sugestões                                                  ║
║                                                                            ║
║  Deploy: Railway (free tier) com 1 único Secret: DISCORD_TOKEN             ║
╚════════════════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import discord
from discord.ext import commands

from config import Cores, Emojis, get_token, get_donos, REGRAS_FILE


# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("rede_tuga.main")


# ─────────────────────────────────────────────────────────────────────────────
# Intents
# ─────────────────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
intents.voice_states = True


# ─────────────────────────────────────────────────────────────────────────────
# Instância do bot
# ─────────────────────────────────────────────────────────────────────────────
class RedeTugaBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            case_insensitive=True,
        )
        self.start_time = discord.utils.utcnow()

    async def setup_hook(self) -> None:
        cogs_dir = Path(__file__).parent / "cogs"
        carregados, falhados = 0, 0

        # Ordem de carregamento — setup primeiro
        cogs_ordenados = ["setup", "geral", "editar", "regras", "boas_vindas", "tickets",
                          "anuncios", "falar", "embed_builder", "sla", "giveaways"]

        for nome in cogs_ordenados:
            ficheiro = cogs_dir / f"{nome}.py"
            if not ficheiro.exists():
                continue
            nome_cog = f"cogs.{nome}"
            try:
                await self.load_extension(nome_cog)
                carregados += 1
                log.info("✅ Cog carregado: %s", nome_cog)
            except Exception as e:
                falhados += 1
                log.exception("❌ Falha ao carregar %s: %s", nome_cog, e)

        # Carrega qualquer cog extra
        for ficheiro in sorted(cogs_dir.glob("*.py")):
            if ficheiro.name.startswith("_") or ficheiro.stem in cogs_ordenados:
                continue
            nome_cog = f"cogs.{ficheiro.stem}"
            try:
                await self.load_extension(nome_cog)
                carregados += 1
                log.info("✅ Cog carregado: %s", nome_cog)
            except Exception as e:
                falhados += 1
                log.exception("❌ Falha ao carregar %s: %s", nome_cog, e)

        log.info("📊 Cogs: %d carregados, %d falhados", carregados, falhados)

        # Sincroniza slash commands globalmente
        # (pode demorar até 1h no Discord; para sync instantâneo, define GUILD_ID)
        import os
        guild_id_env = os.getenv("GUILD_ID", "0").strip()
        try:
            if guild_id_env and guild_id_env.isdigit() and int(guild_id_env) > 0:
                guild = discord.Object(id=int(guild_id_env))
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                log.info("🔄 %d slash commands sincronizados (guild %s)", len(synced), guild_id_env)
            else:
                synced = await self.tree.sync()
                log.info("🔄 %d slash commands sincronizados (global — pode demorar até 1h)", len(synced))
        except Exception as e:
            log.exception("⚠️ Erro ao sincronizar slash commands: %s", e)

    @property
    def uptime(self) -> str:
        delta = discord.utils.utcnow() - self.start_time
        horas, resto = divmod(int(delta.total_seconds()), 3600)
        minutos, segundos = divmod(resto, 60)
        return f"{horas}h {minutos}m {segundos}s"


bot = RedeTugaBot()


# ─────────────────────────────────────────────────────────────────────────────
# Eventos globais
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# Rich presence rotativa — muda a cada 30 segundos (com link do servidor)
# ─────────────────────────────────────────────────────────────────────────────
LINK_SERVIDOR = "https://discord.gg/AN2Pc5Yvh6"
PRESENCAS_ROTATIVAS = [
    discord.Game(name=f"O melhor server de minecraft tuga!! {LINK_SERVIDOR}"),
    discord.Game(name="Tuguinha é o Goat!!!"),
    discord.Game(name="Tuguinha sempre aqui para ajudar!!!"),
]
_presenca_index = 0
_presenca_task = None


# ─────────────────────────────────────────────────────────────────────────────
# BLOQUEIO DE SERVIDOR — o Tuguinha só funciona no servidor da Rede Tuga
# ─────────────────────────────────────────────────────────────────────────────
GUILD_ID_PERMITIDO = 1489030726534955090


async def _sair_servidor_nao_permitido(guild: discord.Guild) -> None:
    """Envia mensagem e sai do servidor se não for o servidor permitido."""
    log.warning("🚫 Servidor não permitido: %s (%d) — vou sair", guild.name, guild.id)

    # Tenta encontrar um canal onde pode falar
    canal = guild.system_channel
    if canal is None or not canal.permissions_for(guild.me).send_messages:
        for c in guild.text_channels:
            if c.permissions_for(guild.me).send_messages:
                canal = c
                break

    if canal:
        embed = discord.Embed(
            title="🇵🇹 Não me sinto em casa...",
            description=(
                f"Não me sinto em casa, a minha verdadeira casa é {LINK_SERVIDOR}\n\n"
                f"O Tuguinha só funciona no servidor oficial da Rede Tuga.\n"
                f"Obrigado por me teres convidado, mas vou ter de sair. 🇵🇹"
            ),
            color=Cores.VERMELHO,
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url if bot.user else None)
        embed.set_footer(text="Tuguinha • Rede Tuga 🇵🇹")
        try:
            await canal.send(embed=embed)
        except discord.HTTPException:
            pass

    # Aguarda 3 segundos para a mensagem ser lida
    await asyncio.sleep(3)

    # Sai do servidor
    try:
        await guild.leave()
        log.info("✅ Saí do servidor não permitido: %s (%d)", guild.name, guild.id)
    except discord.HTTPException as e:
        log.error("❌ Não consegui sair do servidor %s: %s", guild.name, e)


async def _rotar_presenca() -> None:
    """Task em background que rota a rich presence a cada 30 segundos."""
    global _presenca_index
    while not bot.is_closed():
        try:
            presenca = PRESENCAS_ROTATIVAS[_presenca_index % len(PRESENCAS_ROTATIVAS)]
            await bot.change_presence(
                status=discord.Status.online,
                activity=presenca,
            )
            _presenca_index += 1
        except Exception as e:
            log.warning("Erro ao rotar presença: %s", e)
        await asyncio.sleep(30)


@bot.event
async def on_ready() -> None:
    global _presenca_task
    log.info("═══════════════════════════════════════════════════")
    log.info("🇵🇹  TUGUINHA — ONLINE")
    log.info("═══════════════════════════════════════════════════")
    log.info("👤 Conectado como: %s", bot.user)
    log.info("🆔 ID: %s", bot.user.id if bot.user else "—")
    log.info("🏠 Servidores: %d", len(bot.guilds))
    log.info("👥 Utilizadores: %d", sum(g.member_count or 0 for g in bot.guilds))
    log.info("⚡ Latência: %.0fms", round(bot.latency * 1000))
    log.info("🔒 Servidor permitido: %d", GUILD_ID_PERMITIDO)
    log.info("═══════════════════════════════════════════════════")

    # Inicia task de rich presence rotativa (apenas uma vez)
    if _presenca_task is None or _presenca_task.done():
        _presenca_task = asyncio.create_task(_rotar_presenca())

    # Verifica se está em servidores não permitidos e sai deles (Opção A)
    for guild in bot.guilds:
        if guild.id != GUILD_ID_PERMITIDO:
            log.warning("🚫 Encontrado servidor não permitido no arranque: %s (%d)", guild.name, guild.id)
            asyncio.create_task(_sair_servidor_nao_permitido(guild))


@bot.event
async def on_guild_join(guild: discord.Guild) -> None:
    """Quando o bot é adicionado a um servidor."""
    log.info("🎉 Bot adicionado ao servidor: %s (%d)", guild.name, guild.id)

    # OPÇÃO A — Se não for o servidor permitido, envia mensagem e sai
    if guild.id != GUILD_ID_PERMITIDO:
        await _sair_servidor_nao_permitido(guild)
        return

    # Servidor permitido — mostra mensagem de boas-vindas normal
    canal = guild.system_channel
    if canal is None or not canal.permissions_for(guild.me).send_messages:
        for c in guild.text_channels:
            if c.permissions_for(guild.me).send_messages:
                canal = c
                break
    if canal is None:
        return

    embed = discord.Embed(
        title=f"{Emojis.BEM_VINDO} Olá! Sou o Tuguinha 🇵🇹",
        description=(
            f"Obrigado por me adicionares ao **{guild.name}**!\n\n"
            f"Sou o **Tuguinha**, o bot oficial da Rede Tuga. 🎉\n\n"
            f"🎯 **Para começar, executa:**\n"
            f"```\n/setup\n```\n"
            f"Vou criar automaticamente:\n"
            f"• 📂 Categorias e canais (regras, boas-vindas, tickets, etc.)\n"
            f"• 📜 Painéis prontos a usar (regras, tickets, boas-vindas)\n\n"
            f"⚠️ **Importante:** Preciso de permissão de **Administrador** para fazer o setup.\n"
        ),
        color=Cores.VERMELHO,
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url if bot.user else None)
    embed.set_footer(text="Tuguinha • Bot da Rede Tuga 🇵🇹")
    try:
        await canal.send(embed=embed)
    except discord.HTTPException:
        pass


@bot.event
async def on_interaction(interaction: discord.Interaction) -> None:
    """OPÇÃO B (backup) — Bloqueia interações em servidores não permitidos.

    Se por alguma razão o bot não conseguir sair do servidor (Opção A),
    pelo menos ignora todas as interações de comandos.
    """
    # Só verifica interações de guild (não DMs)
    if interaction.guild is not None and interaction.guild.id != GUILD_ID_PERMITIDO:
        # Se for um comando slash ou botão/select
        if interaction.type in (discord.InteractionType.application_command, discord.InteractionType.component):
            try:
                embed = discord.Embed(
                    title="🇵🇹 Não me sinto em casa...",
                    description=(
                        f"Não me sinto em casa, a minha verdadeira casa é {LINK_SERVIDOR}\n\n"
                        f"O Tuguinha só funciona no servidor oficial da Rede Tuga. 🇵🇹"
                    ),
                    color=Cores.VERMELHO,
                )
                embed.set_thumbnail(url=bot.user.display_avatar.url if bot.user else None)
                embed.set_footer(text="Tuguinha • Rede Tuga 🇵🇹")
                await interaction.response.send_message(embed=embed, ephemeral=True)
            except discord.InteractionResponded:
                pass
            except discord.HTTPException:
                pass


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception) -> None:
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Não tens permissões para usar este comando.", delete_after=10)
        return
    log.exception("Erro em comando %s: %s", ctx.command, error)
    await ctx.send("❌ Ocorreu um erro inesperado. Tenta novamente.", delete_after=15)


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: discord.app_commands.AppCommandError
) -> None:
    if isinstance(error, discord.app_commands.CommandInvokeError):
        error = error.original
    if isinstance(error, discord.app_commands.MissingPermissions):
        msg = "❌ Não tens permissões para usar este comando."
    elif isinstance(error, discord.app_commands.BotMissingPermissions):
        msg = "❌ O bot não tem permissões suficientes."
    elif isinstance(error, discord.app_commands.CommandOnCooldown):
        retry = int(error.retry_after)
        msg = f"⏳ Calma! Aguarda **{retry}s** antes de usar este comando novamente."
    else:
        log.exception("Erro em slash command: %s", error)
        msg = "❌ Ocorreu um erro inesperado. Tenta novamente."

    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


# ─────────────────────────────────────────────────────────────────────────────
# Comandos globais
# ─────────────────────────────────────────────────────────────────────────────
@bot.tree.command(name="ajuda", description="❓ Mostra todos os comandos do Tuguinha")
async def cmd_ajuda(interaction: discord.Interaction) -> None:
    embed = discord.Embed(
        title=f"{Emojis.REGRAS} Comandos do Tuguinha 🇵🇹",
        description=(
            f"Olá! Sou o **Tuguinha** 🇵🇹\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🟢 **Comandos para todos (@everyone)**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        color=Cores.VERMELHO,
    )
    embed.add_field(
        name="❓ `/ajuda`",
        value="Mostra esta lista de comandos.",
        inline=False,
    )
    embed.add_field(
        name="🏓 `/ping`",
        value="Verifica a latência do Tuguinha.",
        inline=False,
    )
    embed.add_field(
        name="ℹ️ `/info`",
        value="Informações técnicas sobre o Tuguinha.",
        inline=False,
    )
    embed.add_field(
        name="👑 `/criador` • `/owner`",
        value="Mostra quem criou o Tuguinha (o GOAT Ricardo!)",
        inline=False,
    )
    embed.add_field(
        name="🎫 Abrir ticket",
        value="Vai ao canal de tickets e seleciona uma categoria no menu.",
        inline=False,
    )
    embed.add_field(
        name="⭐ Avaliar atendimento",
        value="Após fecho de ticket, receive uma DM para avaliar com estrelas.",
        inline=False,
    )

    # Só mostra comandos admin se for admin
    is_admin = isinstance(interaction.user, discord.Member) and (
        interaction.user.guild_permissions.administrator
    )
    if is_admin:
        embed.add_field(
            name="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🔴 **Comandos para Admins**\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            value="*Precisas de permissão de Administrador no servidor.*",
            inline=False,
        )
        embed.add_field(
            name="🎛️ `/geral`",
            value="**Painel unificado** com todos os menus do Tuguinha.",
            inline=False,
        )
        embed.add_field(
            name="🚀 `/setup`",
            value="Configura o bot automaticamente (canais + painéis).",
            inline=False,
        )
        embed.add_field(
            name="📝 `/editar`",
            value="Edita tudo após o setup (mensagens, canais, cargos, categorias).",
            inline=False,
        )
        embed.add_field(
            name="📋 `/config_status`",
            value="Mostra a configuração atual completa.",
            inline=False,
        )
        embed.add_field(
            name="📜 `/regras`",
            value="Reenvia o painel de regras no canal.",
            inline=False,
        )
        embed.add_field(
            name="🔄 `/recarregar_regras`",
            value="Recarrega as regras a partir do `data/regras.json`.",
            inline=False,
        )
        embed.add_field(
            name="🎫 `/painel_tickets`",
            value="Cria o painel de tickets com select menu.",
            inline=False,
        )
        embed.add_field(
            name="👋 `/painel_boas_vindas`",
            value="Configura o sistema de boas-vindas (canal + mensagem).",
            inline=False,
        )
        embed.add_field(
            name="📢 `/anunciar`",
            value="Cria um anúncio com embed e envia para um canal.",
            inline=False,
        )
        embed.add_field(
            name="📅 `/anunciar_agendar`",
            value="Agenda um anúncio para uma data e hora específicas.",
            inline=False,
        )
        embed.add_field(
            name="💬 `/falar`",
            value="Faz o Tuguinha enviar uma mensagem num canal.",
            inline=False,
        )
        embed.add_field(
            name="🎨 `/falar_embed`",
            value="Faz o Tuguinha enviar uma embed num canal.",
            inline=False,
        )
        embed.add_field(
            name="📬 `/mensagemprivado`",
            value="Envia uma mensagem privada (DM) a um membro pelo Tuguinha.",
            inline=False,
        )
        embed.add_field(
            name="📢 `/embed`",
            value="Construtor de embeds avançado (anúncios personalizados).",
            inline=False,
        )
        embed.add_field(
            name="🎉 `/giveaway`",
            value="Sistema de sorteios (criar, cancelar, reroll, listar).",
            inline=False,
        )
        embed.add_field(
            name="⏱️ SLA Tracking",
            value="Avisos automáticos de tickets sem resposta (configura em `/editar`).",
            inline=False,
        )

    embed.set_footer(text="Tuguinha • Feito com 🤍 pelo GOAT Ricardo 🇵🇹")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="ping", description="🏓 Verifica a latência do Tuguinha")
async def cmd_ping(interaction: discord.Interaction) -> None:
    latency_ms = round(bot.latency * 1000)
    cor = 0x2ECC71 if latency_ms < 100 else (0xF39C12 if latency_ms < 300 else 0xE74C3C)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latência da API: **{latency_ms}ms**",
        color=cor,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="info", description="ℹ️ Informações sobre o Tuguinha")
async def cmd_info(interaction: discord.Interaction) -> None:
    from config import get_config

    cfg = get_config(interaction.guild.id) if interaction.guild else None
    nome = cfg.nome_servidor if cfg else "Rede Tuga"

    embed = discord.Embed(
        title=f"{Emojis.COROA} Tuguinha — {nome}",
        description="Sou o **Tuguinha**, o bot oficial da Rede Tuga. 🇵🇹",
        color=Cores.VERMELHO,
    )
    embed.add_field(name="🤖 Utilizador", value=f"`{bot.user}`", inline=True)
    embed.add_field(name="🆔 ID", value=f"`{bot.user.id}`", inline=True)
    embed.add_field(name="📅 Online desde", value=f"<t:{int(bot.start_time.timestamp())}:R>", inline=True)
    embed.add_field(name="🏠 Servidores", value=f"`{len(bot.guilds)}`", inline=True)
    embed.add_field(name="👥 Utilizadores", value=f"`{sum(g.member_count or 0 for g in bot.guilds):,}`", inline=True)
    embed.add_field(name="⚡ Ping", value=f"`{round(bot.latency * 1000)}ms`", inline=True)
    embed.add_field(
        name="🛠️ Stack",
        value="`discord.py 2.4+` · `Python 3.11+` · `Railway`",
        inline=False,
    )
    if cfg and not cfg.setup_completo:
        embed.add_field(
            name="⚠️ Setup pendente",
            value="Executa `/setup` para configurar o bot automaticamente!",
            inline=False,
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ─────────────────────────────────────────────────────────────────────────────
# /criador — público (qualquer pessoa pode usar)
# ─────────────────────────────────────────────────────────────────────────────
@bot.tree.command(
    name="criador",
    description="👑 Mostra quem criou este bot",
)
async def cmd_criador(interaction: discord.Interaction) -> None:
    """Comando público — qualquer membro pode executar."""
    embed = discord.Embed(
        title=f"{Emojis.COROA} Sobre o Tuguinha",
        description=(
            f"Olá! Sou o **Tuguinha** 🇵🇹, o teu bot de gestão de comunidade!\n\n"
            f"Fui **feito com carinho** pelo **GOAT Ricardo** 👑🐐\n\n"
            f"💡 *Obrigado por usares o Tuguinha! Se gostaste, diz ao Ricardo.* 😄"
        ),
        color=Cores.DOURADO,
    )
    embed.set_thumbnail(
        url=bot.user.display_avatar.url if bot.user else None
    )
    embed.set_footer(text="Tuguinha • Feito com 🤍 pelo GOAT Ricardo 🇵🇹")
    await interaction.response.send_message(embed=embed)


# ─────────────────────────────────────────────────────────────────────────────
# /owner — alias público do /criador
# ─────────────────────────────────────────────────────────────────────────────
@bot.tree.command(
    name="owner",
    description="👑 Mostra quem é o dono/criador do bot",
)
async def cmd_owner(interaction: discord.Interaction) -> None:
    """Alias público do /criador."""
    embed = discord.Embed(
        title=f"{Emojis.COROA} Dono do Tuguinha",
        description=(
            f"O dono e criador do Tuguinha é o **GOAT Ricardo** 👑🐐\n\n"
            f"🇵🇹 **Rede Tuga** — Feito com carinho\n\n"
            f"💡 *Para questões sobre o bot, fala com o Ricardo.* 😄"
        ),
        color=Cores.DOURADO,
    )
    embed.set_thumbnail(
        url=bot.user.display_avatar.url if bot.user else None
    )
    embed.set_footer(text="Tuguinha • Feito com 🤍 pelo GOAT Ricardo 🇵🇹")
    await interaction.response.send_message(embed=embed)


# ─────────────────────────────────────────────────────────────────────────────
# Ponto de entrada
# ─────────────────────────────────────────────────────────────────────────────
async def main() -> None:
    token = get_token()
    if not token or token == "coloca_aqui_o_teu_token":
        log.error("═══════════════════════════════════════════════════")
        log.error("❌ DISCORD_TOKEN não configurado!")
        log.error("   Define a variável DISCORD_TOKEN nos Secrets do Railway")
        log.error("   (é o ÚNICO Secret obrigatório)")
        log.error("═══════════════════════════════════════════════════")
        sys.exit(1)

    REGRAS_FILE.parent.mkdir(parents=True, exist_ok=True)

    async with bot:
        try:
            await bot.start(token)
        except KeyboardInterrupt:
            log.info("Encerramento solicitado pelo utilizador.")
        except discord.LoginFailure:
            log.error("❌ Token inválido. Verifica o DISCORD_TOKEN.")
            sys.exit(1)
        except Exception as e:
            # Não logar o erro raw — pode conter o token em mensagens de conexão
            log.error("Erro fatal ao iniciar o bot: %s", type(e).__name__)
            log.debug("Detalhes do erro (apenas em modo debug): %s", str(e).replace(token, "***") if token else e)
            sys.exit(1)
        finally:
            if not bot.is_closed():
                await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nEncerrado.")
