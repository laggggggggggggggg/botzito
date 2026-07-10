"""
╔════════════════════════════════════════════════════════════════════════════╗
║                          🇵🇹  BOT REDE TUGA  🇵🇹                              ║
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
║    • Sistema de boas-vindas com DM + verify                                ║
║    • Sistema completo de tickets (7 categorias)                            ║
║    • Auto-roles reativos                                                   ║
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
        cogs_ordenados = ["setup", "regras", "boas_vindas", "tickets",
                          "auto_roles", "embed_builder", "sugestoes"]

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
@bot.event
async def on_ready() -> None:
    log.info("═══════════════════════════════════════════════════")
    log.info("🇵🇹  BOT REDE TUGA — ONLINE")
    log.info("═══════════════════════════════════════════════════")
    log.info("👤 Conectado como: %s", bot.user)
    log.info("🆔 ID: %s", bot.user.id if bot.user else "—")
    log.info("🏠 Servidores: %d", len(bot.guilds))
    log.info("👥 Utilizadores: %d", sum(g.member_count or 0 for g in bot.guilds))
    log.info("⚡ Latência: %.0fms", round(bot.latency * 1000))
    log.info("═══════════════════════════════════════════════════")
    log.info("💡 Para configurar: executa /setup no teu servidor Discord")
    log.info("═══════════════════════════════════════════════════")

    try:
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"a comunidade 🇵🇹 • /setup",
            ),
        )
    except Exception as e:
        log.warning("Não foi possível definir presença: %s", e)


@bot.event
async def on_guild_join(guild: discord.Guild) -> None:
    """Quando o bot entra num servidor novo, avisa o dono para fazer /setup."""
    log.info("🎉 Bot adicionado ao servidor: %s (%d)", guild.name, guild.id)
    # Tenta encontrar um canal de sistema ou o primeiro canal onde pode falar
    canal = guild.system_channel
    if canal is None or not canal.permissions_for(guild.me).send_messages:
        for c in guild.text_channels:
            if c.permissions_for(guild.me).send_messages:
                canal = c
                break
    if canal is None:
        return

    embed = discord.Embed(
        title=f"{Emojis.BEM_VINDO} Olá! Sou o Bot da Rede Tuga 🇵🇹",
        description=(
            f"Obrigado por me adicionares ao **{guild.name}**!\n\n"
            f"🎯 **Para começar, executa:**\n"
            f"```\n/setup\n```\n"
            f"Vou criar automaticamente:\n"
            f"• 📂 Categorias e canais (regras, boas-vindas, tickets, etc.)\n"
            f"• 🎭 Cargos (Admin, Staff, Membro, Verificado...)\n"
            f"• 📜 Painéis prontos a usar (regras, tickets, auto-roles)\n\n"
            f"⚠️ **Importante:** Preciso de permissão de **Administrador** para fazer o setup.\n"
            f"Se ainda não a dei, vai a **Definições do Servidor > Cargos > [Bot] > Ativar Administrador**."
        ),
        color=Cores.VERMELHO,
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url if bot.user else discord.Embed.Empty)
    embed.set_footer(text="Rede Tuga • Bot de Gestão de Comunidade")
    try:
        await canal.send(embed=embed)
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
    await ctx.send(f"❌ Ocorreu um erro: `{error}`", delete_after=15)


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
    else:
        log.exception("Erro em slash command: %s", error)
        msg = f"❌ Ocorreu um erro: `{error}`"

    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


# ─────────────────────────────────────────────────────────────────────────────
# Comandos globais
# ─────────────────────────────────────────────────────────────────────────────
@bot.tree.command(name="ajuda", description="Mostra os comandos disponíveis do bot")
async def cmd_ajuda(interaction: discord.Interaction) -> None:
    embed = discord.Embed(
        title=f"{Emojis.REGRAS} Comandos do Bot Rede Tuga",
        description="Aqui tens a lista de comandos disponíveis. Usa-os no servidor!",
        color=Cores.VERMELHO,
    )
    embed.add_field(
        name="🚀 `/setup`",
        value="**Comando principal!** Configura o bot automaticamente — cria canais, cargos e painéis.",
        inline=False,
    )
    embed.add_field(
        name="📜 `/regras`",
        value="Reenvia o painel de regras no canal atual ou configurado.",
        inline=False,
    )
    embed.add_field(
        name="🎫 `/painel_tickets`",
        value="Cria o painel de tickets com botões para todos os tipos de suporte.",
        inline=False,
    )
    embed.add_field(
        name="🎭 `/painel_cargos`",
        value="Cria o painel de auto-roles — os membros escolhem os seus cargos.",
        inline=False,
    )
    embed.add_field(
        name="📢 `/embed`",
        value="Cria um anúncio personalizado (apenas staff).",
        inline=False,
    )
    embed.add_field(
        name="💡 `/sugerir`",
        value="Envia uma sugestão para o canal de sugestões.",
        inline=False,
    )
    embed.add_field(
        name="ℹ️ `/info` • 🏓 `/ping`",
        value="Informações técnicas do bot e latência.",
        inline=False,
    )
    embed.set_footer(text="Rede Tuga • /setup para configurar tudo!")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="ping", description="Verifica a latência do bot")
async def cmd_ping(interaction: discord.Interaction) -> None:
    latency_ms = round(bot.latency * 1000)
    cor = 0x2ECC71 if latency_ms < 100 else (0xF39C12 if latency_ms < 300 else 0xE74C3C)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latência da API: **{latency_ms}ms**",
        color=cor,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="info", description="Informações sobre o bot")
async def cmd_info(interaction: discord.Interaction) -> None:
    from config import get_config

    cfg = get_config(interaction.guild.id) if interaction.guild else None
    nome = cfg.nome_servidor if cfg else "Rede Tuga"

    embed = discord.Embed(
        title=f"{Emojis.COROA} {nome} — Bot",
        description="Bot de gestão da comunidade Rede Tuga.",
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
            log.exception("Erro fatal: %s", e)
            sys.exit(1)
        finally:
            if not bot.is_closed():
                await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nEncerrado.")
