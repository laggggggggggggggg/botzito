"""
Cog de Auto-Roles — painel reativo onde os membros escolhem cargos.

Por defeito, o painel mostra um select menu com jogos/regiões/notificações.
Os cargos são configuráveis via comando /config_autoroles (apenas admin).
"""
from __future__ import annotations

import json
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from config import Cores, Emojis, config, DATA_DIR
from utils import (
    carregar_json,
    embed_aviso,
    embed_erro,
    embed_sucesso,
    e_admin,
    guardar_json,
    log_evento,
)

AUTOROLES_FILE = DATA_DIR / "autoroles.json"


def carregar_autoroles() -> list[dict]:
    """Lista de opções configuradas: [{id, label, emoji, cargo_id, descricao}]."""
    default = [
        {
            "id": "notificacoes",
            "label": "Notificações de Eventos",
            "emoji": "🔔",
            "cargo_id": 0,  # preenche com /config_autoroles
            "descricao": "Receber ping quando houver eventos ou anúncios importantes.",
        },
        {
            "id": "gaming",
            "label": "Gamer",
            "emoji": "🎮",
            "cargo_id": 0,
            "descricao": "Acesso aos canais de gaming e matchmaking.",
        },
        {
            "id": "musica",
            "label": "Música",
            "emoji": "🎵",
            "cargo_id": 0,
            "descricao": "Acesso aos canais de música e karaoke.",
        },
        {
            "id": "arte",
            "label": "Artista",
            "emoji": "🎨",
            "cargo_id": 0,
            "descricao": "Para criadores de conteúdo, artistas e streamers.",
        },
        {
            "id": "norte",
            "label": "Região Norte",
            "emoji": "🏔️",
            "cargo_id": 0,
            "descricao": "Para tugas do Norte — para encontros regionais.",
        },
        {
            "id": "centro",
            "label": "Região Centro",
            "emoji": "🌊",
            "cargo_id": 0,
            "descricao": "Para tugas do Centro — para encontros regionais.",
        },
        {
            "id": "sul",
            "label": "Região Sul",
            "emoji": "🏖️",
            "cargo_id": 0,
            "descricao": "Para tugas do Sul e Ilhas — para encontros regionais.",
        },
        {
            "id": "ilhas",
            "label": "Ilhas (Madeira/Açores)",
            "emoji": "🏝️",
            "cargo_id": 0,
            "descricao": "Para tugas das Ilhas — para encontros regionais.",
        },
    ]
    return carregar_json(AUTOROLES_FILE, default)


def guardar_autoroles(dados: list[dict]) -> bool:
    return guardar_json(AUTOROLES_FILE, dados)


class AutoRolesSelect(discord.ui.Select):
    """Select menu onde os membros escolhem cargos."""

    def __init__(self, opcoes: list[dict]) -> None:
        options = []
        for op in opcoes[:25]:
            cargo_id = op.get("cargo_id", 0)
            if cargo_id == 0:
                continue
            options.append(
                discord.SelectOption(
                    label=op["label"][:100],
                    value=str(cargo_id),
                    description=op.get("descricao", "")[:100],
                    emoji=op.get("emoji"),
                )
            )
        if not options:
            options.append(
                discord.SelectOption(
                    label="Aguarda configuração",
                    value="none",
                    description="A staff ainda não configurou os cargos.",
                )
            )
        super().__init__(
            placeholder="Escolhe os teus cargos... (podes escolher vários)",
            min_values=0,
            max_values=len(options) if len(options) < 25 else 25,
            options=options,
            custom_id="rede_tuga:autoroles_select",
        )
        self.opcoes_validas = options

    async def callback(self, interaction: discord.Interaction) -> None:
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ Só podes usar isto dentro do servidor.", ephemeral=True
            )
            return

        if str(self.values[0]) == "none" if self.values else False:
            await interaction.response.send_message(
                embed=embed_aviso(
                    "Sem cargos",
                    "A staff ainda não configurou os cargos. Tenta mais tarde.",
                ),
                ephemeral=True,
            )
            return

        cargos_selecionados = [int(v) for v in self.values if v != "none"]
        guild = interaction.guild

        # Cargos que o membro já tem desta lista
        cargos_atuais = {r.id for r in interaction.user.roles} & set(cargos_selecionados)

        # Toggle: remove os que já tem, adiciona os novos
        a_adicionar = [cid for cid in cargos_selecionados if cid not in cargos_atuais]
        a_remover = list(cargos_atuais)

        adicionados: list[str] = []
        removidos: list[str] = []

        for cid in a_adicionar:
            cargo = guild.get_role(cid)
            if cargo and not cargo.is_bot_managed() and not cargo.is_default():
                try:
                    await interaction.user.add_roles(cargo, reason="Auto-role selecionado")
                    adicionados.append(f"{cargo.mention}")
                except discord.Forbidden:
                    pass

        for cid in a_remover:
            cargo = guild.get_role(cid)
            if cargo:
                try:
                    await interaction.user.remove_roles(cargo, reason="Auto-role desmarcado")
                    removidos.append(f"{cargo.mention}")
                except discord.Forbidden:
                    pass

        msg_parts: list[str] = []
        if adicionados:
            msg_parts.append(f"✅ **Adicionados:** {', '.join(adicionados)}")
        if removidos:
            msg_parts.append(f"❌ **Removidos:** {', '.join(removidos)}")
        if not msg_parts:
            msg_parts.append("Nenhuma alteração — já tens os cargos selecionados.")

        await interaction.response.send_message(
            embed=discord.Embed(
                title=f"{Emojis.SETA} Cargos atualizados",
                description="\n".join(msg_parts),
                color=Cores.SUCESSO,
            ),
            ephemeral=True,
        )


class AutoRolesView(discord.ui.View):
    def __init__(self, opcoes: list[dict]) -> None:
        super().__init__(timeout=None)
        self.add_item(AutoRolesSelect(opcoes))


class AutoRolesCog(commands.Cog):
    """Sistema de auto-roles reativo."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        opcoes = carregar_autoroles()
        self.bot.add_view(AutoRolesView(opcoes))

    @app_commands.command(
        name="painel_cargos",
        description="Cria o painel de auto-roles com select menu (staff).",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def painel_cargos(self, interaction: discord.Interaction) -> None:
        from utils import e_staff

        if not e_staff(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro("Sem permissão", "Apenas a staff pode usar este comando."),
                ephemeral=True,
            )
            return

        opcoes = carregar_autoroles()
        opcoes_validas = [o for o in opcoes if o.get("cargo_id", 0) != 0]

        embed = discord.Embed(
            title=f"🎭 Escolhe os teus Cargos — {config.nome_servidor}",
            description=(
                f"Seleciona no menu abaixo os cargos que queres atribuir-te! 🎭\n\n"
                f"Podes escolher **vários ao mesmo tempo** — clica novamente para remover.\n\n"
                f"**Categorias disponíveis:**\n"
                f"{Emojis.SETA} 🔔 Notificações\n"
                f"{Emojis.SETA} 🎮 Interesses (gaming, música, arte)\n"
                f"{Emojis.SETA} 🌍 Região de Portugal\n\n"
                f"*Os cargos são opcionais e não afetam o teu acesso ao servidor.*"
            ),
            color=Cores.DOURADO,
        )
        embed.set_thumbnail(
            url=interaction.guild.icon.url if interaction.guild and interaction.guild.icon else discord.Embed.Empty
        )
        embed.set_footer(text=f"{config.nome_servidor} • Auto-Roles")

        view = AutoRolesView(opcoes)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            embed=embed_sucesso(
                "Painel criado!",
                f"Painel de auto-roles publicado. {len(opcoes_validas)} cargos disponíveis.",
            ),
            ephemeral=True,
        )

        await log_evento(
            self.bot,
            "🎭 Painel auto-roles criado",
            f"Por {interaction.user.mention} em {interaction.channel.mention}.",
            Cores.DOURADO,
            interaction.user,
        )

    @app_commands.command(
        name="config_autoroles",
        description="Configura os cargos do painel de auto-roles (apenas admin).",
    )
    @app_commands.describe(
        opcao_id="ID da opção (ex: gaming, musica, norte, sul...)",
        cargo="Cargo a atribuir para essa opção",
    )
    @app_commands.default_permissions(administrator=True)
    async def config_autoroles(
        self,
        interaction: discord.Interaction,
        opcao_id: str,
        cargo: discord.Role,
    ) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro("Sem permissão", "Apenas admins podem configurar auto-roles."),
                ephemeral=True,
            )
            return

        opcoes = carregar_autoroles()
        opcao = next((o for o in opcoes if o["id"] == opcao_id.lower()), None)
        if opcao is None:
            ids = ", ".join(o["id"] for o in opcoes)
            await interaction.response.send_message(
                embed=embed_erro(
                    "Opção inválida",
                    f"IDs disponíveis: `{ids}`",
                ),
                ephemeral=True,
            )
            return

        opcao["cargo_id"] = cargo.id
        guardar_autoroles(opcoes)

        await interaction.response.send_message(
            embed=embed_sucesso(
                "Configuração guardada!",
                f"Opção **{opcao['label']}** {opcao.get('emoji', '')} agora atribui {cargo.mention}.\n\n"
                f"Recria o painel com `/painel_cargos` para aplicar as alterações.",
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoRolesCog(bot))
