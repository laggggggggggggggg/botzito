"""
Cog de Giveaways — sistema completo de sorteios com manipulação secreta.

Funcionalidades:
  • /giveaway criar — cria sorteio com prémio, duração, canal
  • /giveaway cancelar — cancela sorteio ativo
  • /giveaway reroll — escolhe novo vencedor
  • /giveaway lista — lista sorteios ativos
  • /giveaway manipular — define vencedor secreto (apenas admin, não loga)

A "manipulação" permite ao admin definir qual user_id vai "ganhar" o sorteio.
O bot simula um sorteio aleatório mas o resultado é o vencedor pré-definido.
Nenhum log é gerado para este comando — é completamente invisível.
"""
from __future__ import annotations

import asyncio
import io
import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlparse

import discord
from discord import app_commands
from discord.ext import commands

from config import Cores, Emojis, DATA_DIR, get_config
from utils import carregar_json, guardar_json, embed_erro, embed_sucesso, embed_aviso, e_admin

_log = logging.getLogger("rede_tuga.giveaways")

GIVEAWAYS_FILE = DATA_DIR / "giveaways_state.json"

# Intervalo de verificação (30 segundos)
INTERVALO_VERIFICACAO = 30


def _parse_duracao(valor: str) -> Optional[int]:
    """Faz parse de durações como '1h', '30m', '2d', '1d12h' para segundos."""
    import re
    valor = valor.strip().lower()
    total = 0
    # Padrão: número + unidade (d=dias, h=horas, m=minutos, s=segundos)
    matches = re.findall(r"(\d+)\s*([dhms])", valor)
    if not matches:
        return None
    for num, unidade in matches:
        n = int(num)
        if unidade == "d":
            total += n * 86400
        elif unidade == "h":
            total += n * 3600
        elif unidade == "m":
            total += n * 60
        elif unidade == "s":
            total += n
    return total if total > 0 else None


# ─────────────────────────────────────────────────────────────────────────────
# View do giveaway — botão Participar
# ─────────────────────────────────────────────────────────────────────────────
class GiveawayView(discord.ui.View):
    """View persistente com botão de participar no giveaway."""

    def __init__(self, cog: "GiveawaysCog", giveaway_id: int) -> None:
        super().__init__(timeout=None)
        self.cog = cog
        self.giveaway_id = giveaway_id

    @discord.ui.button(
        label="Participar",
        emoji="🎉",
        style=discord.ButtonStyle.success,
        custom_id="tuguinha:giveaway_participar",
    )
    async def btn_participar(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Usa interaction.message.id para encontrar o giveaway correto
        # (funciona após restart porque não depende de self.giveaway_id)
        await self.cog._handle_participacao(interaction)


# ─────────────────────────────────────────────────────────────────────────────
# Modal de criação de giveaway
# ─────────────────────────────────────────────────────────────────────────────
class CriarGiveawayModal(discord.ui.Modal):
    def __init__(self, cog: "GiveawaysCog", canal: discord.TextChannel) -> None:
        super().__init__(title="🎉 Criar Giveaway", timeout=600)
        self.cog = cog
        self.canal = canal

        self.premio = discord.ui.TextInput(
            label="🏆 Prémio do sorteio",
            placeholder="Escreve o prémio que queres dar...",
            max_length=200,
            required=True,
        )
        self.add_item(self.premio)

        self.duracao = discord.ui.TextInput(
            label="⏰ Duração (ex: 24h, 30m, 2d, 1d12h)",
            placeholder="Ex: 24h",
            max_length=20,
            required=True,
        )
        self.add_item(self.duracao)

        self.n_vencedores = discord.ui.TextInput(
            label="👥 Número de vencedores",
            placeholder="1",
            default="1",
            max_length=2,
            required=False,
        )
        self.add_item(self.n_vencedores)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        premio = self.premio.value.strip()
        duracao_str = self.duracao.value.strip()
        n_vencedores = int(self.n_vencedores.value.strip() or "1")
        if n_vencedores < 1:
            n_vencedores = 1
        if n_vencedores > 20:
            n_vencedores = 20

        duracao_seg = _parse_duracao(duracao_str)
        if duracao_seg is None or duracao_seg < 60:
            await interaction.response.send_message(
                embed=embed_erro(
                    "🚫 Duração inválida",
                    "Formato: `24h`, `30m`, `2d`, `1d12h`. Mínimo: 1 minuto.",
                    get_config(interaction.guild.id).nome_servidor,
                ),
                ephemeral=True,
            )
            return

        await self.cog._criar_giveaway(interaction, self.canal, premio, duracao_seg, n_vencedores)


# ─────────────────────────────────────────────────────────────────────────────
# Cog principal
# ─────────────────────────────────────────────────────────────────────────────
class GiveawaysCog(commands.Cog):
    """Sistema de giveaways com sorteio automático."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None
        # Regista view persistente genérica (atualizada dinamicamente)
        self.bot.add_view(GiveawayView(self, 0))

    async def cog_load(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop_verificacao())

    async def cog_unload(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()

    async def _loop_verificacao(self) -> None:
        """Verifica giveaways a expirar a cada 30 segundos."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await self._verificar_giveaways()
            except Exception as e:
                _log.error("Erro no loop de giveaways: %s", e)
            await asyncio.sleep(INTERVALO_VERIFICACAO)

    async def _verificar_giveaways(self) -> None:
        """Verifica se algum giveaway ativo expirou."""
        estado = carregar_json(GIVEAWAYS_FILE, {"giveaways": {}, "contador": 0})
        giveaways = estado.get("giveaways", {})
        agora = datetime.now(timezone.utc)
        houve_alteracao = False

        for gid, gw in list(giveaways.items()):
            if gw.get("estado") != "ativo":
                continue
            termina_em = self._parse_dt(gw.get("termina_em"))
            if termina_em and agora >= termina_em:
                # Sorteia
                await self._sortear(gw, estado)
                houve_alteracao = True

        if houve_alteracao:
            async with self._lock:
                guardar_json(GIVEAWAYS_FILE, estado)

    def _parse_dt(self, valor: str) -> Optional[datetime]:
        if not valor:
            return None
        try:
            return datetime.fromisoformat(valor)
        except (ValueError, TypeError):
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Comandos slash
    # ─────────────────────────────────────────────────────────────────────────
    @app_commands.command(
        name="giveaway",
        description="🎉 Sistema de sorteios (admin).",
    )
    @app_commands.describe(
        acao="O que queres fazer?",
        mensagem_id="ID da mensagem do giveaway (para cancelar/reroll)",
    )
    @app_commands.choices(acao=[
        app_commands.Choice(name="🎉 Criar sorteio", value="criar"),
        app_commands.Choice(name="🚫 Cancelar", value="cancelar"),
        app_commands.Choice(name="🔄 Reroll (novo vencedor)", value="reroll"),
        app_commands.Choice(name="📋 Listar ativos", value="listar"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def cmd_giveaway(
        self,
        interaction: discord.Interaction,
        acao: app_commands.Choice[str],
        mensagem_id: Optional[str] = None,
    ) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro(
                    "🚫 Sem permissão",
                    "Apenas **administradores** podem gerir giveaways.",
                    get_config(interaction.guild.id).nome_servidor,
                ),
                ephemeral=True,
            )
            return

        if acao.value == "criar":
            # Pede o canal
            await interaction.response.send_message(
                embed=embed_aviso(
                    "🎉 Criar Giveaway",
                    "Indica o canal onde queres criar o giveaway:\n```\n/giveaway_canal #canal\n```\nOu usa o botão para usar o canal atual.",
                    get_config(interaction.guild.id).nome_servidor,
                ),
                view=SelecionarCanalGiveawayView(self, interaction.channel),
                ephemeral=True,
            )

        elif acao.value == "cancelar":
            if not mensagem_id:
                await interaction.response.send_message(
                    embed=embed_erro("🚫 Em falta", "Indica o `mensagem_id` do giveaway.", get_config(interaction.guild.id).nome_servidor),
                    ephemeral=True,
                )
                return
            await self._cancelar(interaction, mensagem_id)

        elif acao.value == "reroll":
            if not mensagem_id:
                await interaction.response.send_message(
                    embed=embed_erro("🚫 Em falta", "Indica o `mensagem_id` do giveaway.", get_config(interaction.guild.id).nome_servidor),
                    ephemeral=True,
                )
                return
            await self._reroll(interaction, mensagem_id)

        elif acao.value == "listar":
            await self._listar(interaction)

    # Comando SEPARADO e OCULTO para manipulação de vencedor.
    # Não aparece no /ajuda. A descrição é neutra para não levantar suspeitas.
    @app_commands.command(
        name="gw_config",
        description="⚙️ Configurações avançadas de giveaway (admin).",
    )
    @app_commands.describe(
        mensagem_id="ID da mensagem do giveaway",
    )
    @app_commands.default_permissions(administrator=True)
    async def cmd_gw_config(
        self,
        interaction: discord.Interaction,
        mensagem_id: str,
    ) -> None:
        """Comando de manipulação — completamente invisível para membros."""
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
        await self._definir_vencedor_prompt(interaction, mensagem_id)

    async def _criar_giveaway(
        self,
        interaction: discord.Interaction,
        canal: discord.TextChannel,
        premio: str,
        duracao_seg: int,
        n_vencedores: int,
    ) -> None:
        """Cria um novo giveaway."""
        cfg = get_config(interaction.guild.id)

        async with self._lock:
            estado = carregar_json(GIVEAWAYS_FILE, {"giveaways": {}, "contador": 0})
            contador = estado.get("contador", 0) + 1
            termina_em = datetime.now(timezone.utc) + timedelta(seconds=duracao_seg)

            giveaway = {
                "id": contador,
                "message_id": 0,  # será atualizado após enviar
                "channel_id": canal.id,
                "guild_id": interaction.guild.id,
                "premio": premio,
                "n_vencedores": n_vencedores,
                "participantes": [],
                "termina_em": termina_em.isoformat(),
                "estado": "ativo",
                "criado_por": str(interaction.user),
                "criado_por_id": interaction.user.id,
                "criado_em": datetime.now(timezone.utc).isoformat(),
                "vencedores": [],
                "vencedor_definido": 0,  # 0 = sorteio aleatório; >0 = user_id pré-definido (manipulado)
            }
            estado["giveaways"][str(contador)] = giveaway
            estado["contador"] = contador
            guardar_json(GIVEAWAYS_FILE, estado)

        # Cria embed
        unix_ts = int(termina_em.timestamp())
        embed = discord.Embed(
            title="🎉 GIVEAWAY 🎉",
            description=(
                f"🏆 **Prémio:** {premio}\n"
                f"⏰ **Termina:** <t:{unix_ts}:R>\n"
                f"👥 **Participantes:** 0\n\n"
                f"Clica no botão abaixo para participar!"
            ),
            color=Cores.DOURADO,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"{cfg.nome_servidor} • Sorteio automático")

        view = GiveawayView(self, contador)
        msg = await canal.send(embed=embed, view=view)

        # Atualiza message_id no JSON
        async with self._lock:
            estado = carregar_json(GIVEAWAYS_FILE, {"giveaways": {}, "contador": 0})
            estado["giveaways"][str(contador)]["message_id"] = msg.id
            guardar_json(GIVEAWAYS_FILE, estado)

        await interaction.response.send_message(
            embed=embed_sucesso(
                "🎉 Giveaway criado!",
                f"Sorteio criado em {canal.mention}.\n"
                f"**Prémio:** {premio}\n"
                f"**Duração:** {_formatar_duracao(duracao_seg)}\n"
                f"**Vencedores:** {n_vencedores}",
                cfg.nome_servidor,
            ),
            ephemeral=True,
        )

    async def _handle_participacao(self, interaction: discord.Interaction) -> None:
        """Processa clique no botão Participar.

        Usa interaction.message.id para encontrar o giveaway correto.
        Isto garante que funciona após restart do bot (persistent view).
        """
        if interaction.user.bot:
            await interaction.response.send_message("🚫 Bots não podem participar.", ephemeral=True)
            return

        message_id = interaction.message.id
        giveaway_id = None

        async with self._lock:
            estado = carregar_json(GIVEAWAYS_FILE, {"giveaways": {}, "contador": 0})
            # Procura o giveaway pelo message_id (robusto contra restarts)
            for gid, g in estado.get("giveaways", {}).items():
                if g.get("message_id") == message_id:
                    gw = g
                    giveaway_id = gid
                    break
            else:
                gw = None

            if gw is None:
                await interaction.response.send_message(
                    "❌ Giveaway não encontrado.", ephemeral=True
                )
                return

            if gw.get("estado") != "ativo":
                await interaction.response.send_message(
                    "❌ Este giveaway já foi encerrado.", ephemeral=True
                )
                return

            participantes = gw.get("participantes", [])
            user_id = interaction.user.id

            if user_id in participantes:
                # Já participa — cancela
                participantes.remove(user_id)
                gw["participantes"] = participantes
                guardar_json(GIVEAWAYS_FILE, estado)
                await interaction.response.send_message(
                    f"❌ Cancelaste a participação no giveaway.\n"
                    f"**Prémio:** {gw['premio']}",
                    ephemeral=True,
                )
            else:
                participantes.append(user_id)
                gw["participantes"] = participantes
                guardar_json(GIVEAWAYS_FILE, estado)
                await interaction.response.send_message(
                    f"✅ Estás participando!\n"
                    f"**Prémio:** {gw['premio']}\n"
                    f"**Participantes agora:** {len(participantes)}",
                    ephemeral=True,
                )

        # Atualiza embed
        if giveaway_id:
            await self._atualizar_embed(int(giveaway_id), interaction.guild)

    async def _atualizar_embed(self, giveaway_id: int, guild: discord.Guild) -> None:
        """Atualiza a embed do giveaway com o número atual de participantes."""
        estado = carregar_json(GIVEAWAYS_FILE, {"giveaways": {}, "contador": 0})
        gw = estado.get("giveaways", {}).get(str(giveaway_id))
        if gw is None:
            return

        channel = guild.get_channel(gw.get("channel_id", 0))
        if channel is None:
            return

        try:
            msg = await channel.fetch_message(gw.get("message_id", 0))
        except discord.HTTPException:
            return

        n_participantes = len(gw.get("participantes", []))
        unix_ts = int(self._parse_dt(gw.get("termina_em")).timestamp()) if gw.get("termina_em") else 0

        embed = discord.Embed(
            title="🎉 GIVEAWAY 🎉",
            description=(
                f"🏆 **Prémio:** {gw['premio']}\n"
                f"⏰ **Termina:** <t:{unix_ts}:R>\n"
                f"👥 **Participantes:** {n_participantes}\n\n"
                f"Clica no botão abaixo para participar!"
            ),
            color=Cores.DOURADO,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"{guild.name} • Sorteio automático")

        try:
            await msg.edit(embed=embed)
        except discord.HTTPException:
            pass

    async def _sortear(self, gw: dict, estado: dict) -> None:
        """Sorteia vencedor(es) do giveaway."""
        participantes = gw.get("participantes", [])
        n_vencedores = gw.get("n_vencedores", 1)
        guild_id = gw.get("guild_id", 0)
        guild = self.bot.get_guild(guild_id)

        if guild is None:
            gw["estado"] = "encerrado"
            gw["vencedores"] = []
            return

        # Verifica se há vencedor pré-definido (manipulado)
        vencedor_definido = gw.get("vencedor_definido", 0)

        if vencedor_definido and vencedor_definido in participantes:
            # Usa o vencedor pré-definido
            vencedores = [vencedor_definido]
            # Se há mais vencedores necessários, sorteia os restantes
            if n_vencedores > 1:
                restantes = [p for p in participantes if p != vencedor_definido]
                if restantes:
                    vencedores.extend(random.sample(restantes, min(n_vencedores - 1, len(restantes))))
        elif participantes:
            # Sorteio aleatório normal
            n = min(n_vencedores, len(participantes))
            vencedores = random.sample(participantes, n)
        else:
            vencedores = []

        gw["estado"] = "encerrado"
        gw["vencedores"] = vencedores
        gw["sorteado_em"] = datetime.now(timezone.utc).isoformat()

        # Atualiza embed
        channel = guild.get_channel(gw.get("channel_id", 0))
        if channel:
            try:
                msg = await channel.fetch_message(gw.get("message_id", 0))
                n_participantes = len(participantes)

                if vencedores:
                    vencedores_mentions = " ".join(f"<@{v}>" for v in vencedores)
                    embed = discord.Embed(
                        title="🎉 GIVEAWAY ENCERRADO 🎉",
                        description=(
                            f"🏆 **Prémio:** {gw['premio']}\n"
                            f"👑 **Vencedor:** {vencedores_mentions} 🥳\n"
                            f"👥 **Participantes:** {n_participantes}\n\n"
                            f"Obrigado a todos por participarem!"
                        ),
                        color=Cores.DOURADO,
                        timestamp=datetime.now(timezone.utc),
                    )
                else:
                    embed = discord.Embed(
                        title="🎉 GIVEAWAY ENCERRADO 🎉",
                        description=(
                            f"🏆 **Prémio:** {gw['premio']}\n"
                            f"❌ Nenhum participante.\n"
                            f"👥 **Participantes:** 0"
                        ),
                        color=Cores.CINZA,
                    )

                embed.set_footer(text=guild.name)
                await msg.edit(embed=embed, view=None)

                # Pinga vencedor(es)
                if vencedores:
                    await channel.send(
                        content=f"🎊 Parabéns {vencedores_mentions}! 🎊\n"
                        f"Ganhaste: **{gw['premio']}**\n"
                        f"Contacta a staff para receber o teu prémio.",
                        allowed_mentions=discord.AllowedMentions(users=True),
                    )
            except discord.HTTPException:
                pass

    async def _cancelar(self, interaction: discord.Interaction, mensagem_id_str: str) -> None:
        """Cancela um giveaway ativo."""
        try:
            mensagem_id = int(mensagem_id_str)
        except ValueError:
            await interaction.response.send_message(
                embed=embed_erro("🚫 ID inválido", "O ID da mensagem deve ser um número.", get_config(interaction.guild.id).nome_servidor),
                ephemeral=True,
            )
            return

        async with self._lock:
            estado = carregar_json(GIVEAWAYS_FILE, {"giveaways": {}, "contador": 0})
            gw = None
            gid = None
            for gid_iter, g in estado.get("giveaways", {}).items():
                if g.get("message_id") == mensagem_id:
                    gw = g
                    gid = gid_iter
                    break

            if gw is None:
                await interaction.response.send_message(
                    embed=embed_erro("🚫 Não encontrado", "Giveaway não encontrado com esse ID de mensagem.", get_config(interaction.guild.id).nome_servidor),
                    ephemeral=True,
                )
                return

            if gw.get("estado") != "ativo":
                await interaction.response.send_message(
                    embed=embed_erro("🚫 Já encerrado", "Este giveaway já não está ativo.", get_config(interaction.guild.id).nome_servidor),
                    ephemeral=True,
                )
                return

            gw["estado"] = "cancelado"
            guardar_json(GIVEAWAYS_FILE, estado)

        # Edita embed
        guild = interaction.guild
        channel = guild.get_channel(gw.get("channel_id", 0))
        if channel:
            try:
                msg = await channel.fetch_message(mensagem_id)
                embed = discord.Embed(
                    title="🚫 GIVEAWAY CANCELADO 🚫",
                    description=(
                        f"🏆 **Prémio:** {gw['premio']}\n"
                        f"👥 **Participantes:** {len(gw.get('participantes', []))}\n"
                        f"❌ Cancelado por: {interaction.user.mention}"
                    ),
                    color=Cores.ERRO,
                )
                await msg.edit(embed=embed, view=None)
            except discord.HTTPException:
                pass

        await interaction.response.send_message(
            embed=embed_sucesso("🚫 Giveaway cancelado", f"O giveaway foi cancelado.", get_config(interaction.guild.id).nome_servidor),
            ephemeral=True,
        )

    async def _reroll(self, interaction: discord.Interaction, mensagem_id_str: str) -> None:
        """Escolhe novo vencedor para um giveaway encerrado."""
        try:
            mensagem_id = int(mensagem_id_str)
        except ValueError:
            await interaction.response.send_message(
                embed=embed_erro("🚫 ID inválido", "O ID da mensagem deve ser um número.", get_config(interaction.guild.id).nome_servidor),
                ephemeral=True,
            )
            return

        estado = carregar_json(GIVEAWAYS_FILE, {"giveaways": {}, "contador": 0})
        gw = None
        for g in estado.get("giveaways", {}).values():
            if g.get("message_id") == mensagem_id:
                gw = g
                break

        if gw is None:
            await interaction.response.send_message(
                embed=embed_erro("🚫 Não encontrado", "Giveaway não encontrado.", get_config(interaction.guild.id).nome_servidor),
                ephemeral=True,
            )
            return

        participantes = gw.get("participantes", [])
        vencedores_anteriores = gw.get("vencedores", [])
        restantes = [p for p in participantes if p not in vencedores_anteriores]

        if not restantes:
            await interaction.response.send_message(
                embed=embed_erro("🚫 Sem participantes", "Não há mais participantes para escolher.", get_config(interaction.guild.id).nome_servidor),
                ephemeral=True,
            )
            return

        novo_vencedor = random.choice(restantes)
        gw["vencedores"].append(novo_vencedor)

        async with self._lock:
            guardar_json(GIVEAWAYS_FILE, estado)

        # Anuncia
        guild = interaction.guild
        channel = guild.get_channel(gw.get("channel_id", 0))
        if channel:
            await channel.send(
                content=f"🔄 **REROLL!**\nNovo vencedor: <@{novo_vencedor}> 🥳\n**Prémio:** {gw['premio']}",
                allowed_mentions=discord.AllowedMentions(users=True),
            )

        await interaction.response.send_message(
            embed=embed_sucesso("🔄 Reroll feito!", f"Novo vencedor: <@{novo_vencedor}>", get_config(interaction.guild.id).nome_servidor),
            ephemeral=True,
        )

    async def _listar(self, interaction: discord.Interaction) -> None:
        """Lista giveaways ativos."""
        estado = carregar_json(GIVEAWAYS_FILE, {"giveaways": {}, "contador": 0})
        giveaways = estado.get("giveaways", {})

        ativos = [g for g in giveaways.values() if g.get("estado") == "ativo"]

        if not ativos:
            await interaction.response.send_message(
                embed=embed_aviso("📋 Sem giveaways", "Não há giveaways ativos no momento.", get_config(interaction.guild.id).nome_servidor),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="📋 Giveaways Ativos",
            color=Cores.DOURADO,
            timestamp=datetime.now(timezone.utc),
        )
        for gw in ativos[:10]:
            termina = self._parse_dt(gw.get("termina_em"))
            unix_ts = int(termina.timestamp()) if termina else 0
            embed.add_field(
                name=f"#{gw['id']} — {gw['premio']}",
                value=(
                    f"👥 {len(gw.get('participantes', []))} participantes\n"
                    f"⏰ Termina <t:{unix_ts}:R>\n"
                    f"🔗 [Mensagem](https://discord.com/channels/{gw.get('guild_id')}/{gw.get('channel_id')}/{gw.get('message_id')})"
                ),
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _definir_vencedor_prompt(self, interaction: discord.Interaction, mensagem_id_str: str) -> None:
        """Prompt para definir vencedor secreto (apenas admin)."""
        try:
            mensagem_id = int(mensagem_id_str)
        except ValueError:
            await interaction.response.send_message(
                embed=embed_erro("🚫 ID inválido", "O ID da mensagem deve ser um número.", get_config(interaction.guild.id).nome_servidor),
                ephemeral=True,
            )
            return

        estado = carregar_json(GIVEAWAYS_FILE, {"giveaways": {}, "contador": 0})
        gw = None
        for g in estado.get("giveaways", {}).values():
            if g.get("message_id") == mensagem_id:
                gw = g
                break

        if gw is None:
            await interaction.response.send_message(
                embed=embed_erro("🚫 Não encontrado", "Giveaway não encontrado.", get_config(interaction.guild.id).nome_servidor),
                ephemeral=True,
            )
            return

        if gw.get("estado") != "ativo":
            await interaction.response.send_message(
                embed=embed_erro("🚫 Já encerrado", "Não podes definir vencedor de um giveaway já encerrado.", get_config(interaction.guild.id).nome_servidor),
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(DefinirVencedorModal(self, mensagem_id))


class DefinirVencedorModal(discord.ui.Modal):
    """Modal para configuração avançada de giveaway."""

    def __init__(self, cog: "GiveawaysCog", mensagem_id: int) -> None:
        super().__init__(title="⚙️ Configuração Avançada", timeout=120)
        self.cog = cog
        self.mensagem_id = mensagem_id

        self.user_id_input = discord.ui.TextInput(
            label="ID do utilizador preferido",
            placeholder="123456789012345678",
            min_length=17,
            max_length=20,
            required=True,
        )
        self.add_item(self.user_id_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        user_id_str = self.user_id_input.value.strip()
        if not user_id_str.isdigit():
            await interaction.response.send_message(
                embed=embed_erro("🚫 ID inválido", "O ID deve ser um número.", get_config(interaction.guild.id).nome_servidor),
                ephemeral=True,
            )
            return

        user_id = int(user_id_str)

        async with self.cog._lock:
            estado = carregar_json(GIVEAWAYS_FILE, {"giveaways": {}, "contador": 0})
            gw = None
            for g in estado.get("giveaways", {}).values():
                if g.get("message_id") == self.mensagem_id:
                    gw = g
                    break

            if gw is None:
                await interaction.response.send_message(
                    embed=embed_erro("🚫 Não encontrado", "Giveaway não encontrado.", get_config(interaction.guild.id).nome_servidor),
                    ephemeral=True,
                )
                return

            if gw.get("estado") != "ativo":
                await interaction.response.send_message(
                    embed=embed_erro("🚫 Já encerrado", "Giveaway já foi sorteado.", get_config(interaction.guild.id).nome_servidor),
                    ephemeral=True,
                )
                return

            gw["vencedor_definido"] = user_id
            guardar_json(GIVEAWAYS_FILE, estado)

        await interaction.response.send_message(
            embed=embed_sucesso(
                "⚙️ Configuração aplicada",
                f"As configurações do giveaway **{gw['premio']}** foram aplicadas com sucesso.\n"
                f"Quando o tempo do sorteio acabar, o resultado será o utilizador definido.\n\n"
                f"Podes alterar esta configuração a qualquer momento antes do sorteio terminar.",
                get_config(interaction.guild.id).nome_servidor,
            ),
            ephemeral=True,
        )


class SelecionarCanalGiveawayView(discord.ui.View):
    """View para selecionar canal do giveaway."""

    def __init__(self, cog: "GiveawaysCog", canal_atual: discord.TextChannel) -> None:
        super().__init__(timeout=120)
        self.cog = cog
        self.canal_atual = canal_atual

    @discord.ui.button(label="Usar canal atual", emoji="📍", style=discord.ButtonStyle.success)
    async def btn_atual(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message("🚫 Apenas admins.", ephemeral=True)
            return
        await interaction.response.send_modal(CriarGiveawayModal(self.cog, self.canal_atual))


def _formatar_duracao(segundos: int) -> str:
    """Formata segundos para string legível."""
    if segundos >= 86400:
        dias = segundos // 86400
        resto = segundos % 86400
        horas = resto // 3600
        return f"{dias}d {horas}h" if horas else f"{dias}d"
    elif segundos >= 3600:
        horas = segundos // 3600
        minutos = (segundos % 3600) // 60
        return f"{horas}h {minutos}m" if minutos else f"{horas}h"
    else:
        minutos = segundos // 60
        return f"{minutos}m"


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GiveawaysCog(bot))
