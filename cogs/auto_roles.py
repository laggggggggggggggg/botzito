"""
Cog de Auto-Roles — painel reativo onde os membros escolhem cargos.
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import Cores, Emojis, AUTOROLES_FILE, get_config
from utils import (
    carregar_json,
    embed_aviso,
    embed_erro,
    embed_sucesso,
    e_admin,
    guardar_json,
    log_evento,
)


def carregar_autoroles() -> list[dict]:
    default = [
        {"id": "notificacoes", "label": "Notificações de Eventos", "emoji": "🔔",
         "cargo_id": 0, "descricao": "Receber ping quando houver eventos ou anúncios importantes."},
        {"id": "gaming", "label": "Gamer", "emoji": "🎮",
         "cargo_id": 0, "descricao": "Acesso aos canais de gaming e matchmaking."},
        {"id": "musica", "label": "Música", "emoji": "🎵",
         "cargo_id": 0, "descricao": "Acesso aos canais de música e karaoke."},
        {"id": "arte", "label": "Artista", "emoji": "🎨",
         "cargo_id": 0, "descricao": "Para criadores de conteúdo, artistas e streamers."},
        {"id": "norte", "label": "Região Norte", "emoji": "🏔️",
         "cargo_id": 0, "descricao": "Para tugas do Norte — para encontros regionais."},
        {"id": "centro", "label": "Região Centro", "emoji": "🌊",
         "cargo_id": 0, "descricao": "Para tugas do Centro — para encontros regionais."},
        {"id": "sul", "label": "Região Sul", "emoji": "🏖️",
         "cargo_id": 0, "descricao": "Para tugas do Sul e Ilhas — para encontros regionais."},
        {"id": "ilhas", "label": "Ilhas (Madeira/Açores)", "emoji": "🏝️",
         "cargo_id": 0, "descricao": "Para tugas das Ilhas — para encontros regionais."},
    ]
    return carregar_json(AUTOROLES_FILE, default)


def guardar_autoroles(dados: list[dict]) -> bool:
    return guardar_json(AUTOROLES_FILE, dados)


class AutoRolesSelect(discord.ui.Select):
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

        cfg = get_config(interaction.guild.id)

        if self.values and str(self.values[0]) == "none":
            await interaction.response.send_message(
                embed=embed_aviso("Sem cargos",
                                  "A staff ainda não configurou os cargos. Tenta mais tarde.",
                                  cfg.nome_servidor),
                ephemeral=True,
            )
            return

        cargos_selecionados = [int(v) for v in self.values if v != "none"]
        guild = interaction.guild
        cargos_atuais = {r.id for r in interaction.user.roles} & set(cargos_selecionados)

        a_adicionar = [cid for cid in cargos_selecionados if cid not in cargos_atuais]
        a_remover = list(cargos_atuais)

        adicionados: list[str] = []
        removidos: list[str] = []

        # Máscara de permissões perigosas — duplo check no momento de atribuir
        PERMS_PERIGOSAS_MASK = (
            (1 << 3) | (1 << 1) | (1 << 2) | (1 << 5) | (1 << 28) | (1 << 4)
        )
        for cid in a_adicionar:
            cargo = guild.get_role(cid)
            if cargo and not cargo.is_bot_managed() and not cargo.is_default() \
               and not (cargo.permissions.value & PERMS_PERIGOSAS_MASK):
                try:
                    await interaction.user.add_roles(cargo, reason="Auto-role selecionado")
                    adicionados.append(cargo.mention)
                except discord.Forbidden:
                    pass

        for cid in a_remover:
            cargo = guild.get_role(cid)
            if cargo:
                try:
                    await interaction.user.remove_roles(cargo, reason="Auto-role desmarcado")
                    removidos.append(cargo.mention)
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
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        opcoes = carregar_autoroles()
        self.bot.add_view(AutoRolesView(opcoes))

    @app_commands.command(
        name="painel_cargos",
        description="Cria o painel de auto-roles com select menu (apenas admins).",
    )
    @app_commands.default_permissions(administrator=True)
    async def painel_cargos(self, interaction: discord.Interaction) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro("🚫 Sem permissão",
                                 "Apenas **administradores** podem usar este comando.",
                                 get_config(interaction.guild.id).nome_servidor),
                ephemeral=True,
            )
            return

        cfg = get_config(interaction.guild.id)
        opcoes = carregar_autoroles()
        opcoes_validas = [o for o in opcoes if o.get("cargo_id", 0) != 0]

        embed = discord.Embed(
            title=f"🎭 Escolhe os teus Cargos — {cfg.nome_servidor}",
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
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=f"{cfg.nome_servidor} • Auto-Roles")

        view = AutoRolesView(opcoes)
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            embed=embed_sucesso("Painel criado!",
                                f"Painel de auto-roles publicado. {len(opcoes_validas)} cargos disponíveis.",
                                cfg.nome_servidor),
            ephemeral=True,
        )

        await log_evento(
            self.bot,
            "🎭 Painel auto-roles criado",
            f"Por {interaction.user.mention} em {interaction.channel.mention}.",
            Cores.DOURADO,
            interaction.user,
            interaction.guild,
        )

    @app_commands.command(
        name="config_autoroles",
        description="Configura os cargos do painel de auto-roles (apenas admin).",
    )
    @app_commands.describe(
        opcao_id="ID da opção (ex: gaming, musica, norte, sul...)",
        cargo="Cargo a atribuir para essa opção",
    )
    @app_commands.choices(
        opcao_id=[
            app_commands.Choice(name="🔔 Notificações", value="notificacoes"),
            app_commands.Choice(name="🎮 Gamer", value="gaming"),
            app_commands.Choice(name="🎵 Música", value="musica"),
            app_commands.Choice(name="🎨 Artista", value="arte"),
            app_commands.Choice(name="🏔️ Norte", value="norte"),
            app_commands.Choice(name="🌊 Centro", value="centro"),
            app_commands.Choice(name="🏖️ Sul", value="sul"),
            app_commands.Choice(name="🏝️ Ilhas", value="ilhas"),
        ]
    )
    @app_commands.default_permissions(administrator=True)
    async def config_autoroles(
        self,
        interaction: discord.Interaction,
        opcao_id: app_commands.Choice[str],
        cargo: discord.Role,
    ) -> None:
        if not e_admin(interaction.user):
            await interaction.response.send_message(
                embed=embed_erro("Sem permissão", "Apenas admins podem configurar auto-roles.",
                                 get_config(interaction.guild.id).nome_servidor),
                ephemeral=True,
            )
            return

        cfg = get_config(interaction.guild.id)
        opcoes = carregar_autoroles()
        opcao = next((o for o in opcoes if o["id"] == opcao_id.value), None)
        if opcao is None:
            ids = ", ".join(o["id"] for o in opcoes)
            await interaction.response.send_message(
                embed=embed_erro("Opção inválida", f"IDs disponíveis: `{ids}`", cfg.nome_servidor),
                ephemeral=True,
            )
            return

        # ── SEGURANÇA: proibir cargos com permissões perigosas ──
        # Evita que um admin (por erro) permita auto-atribuição de Admin/Staff/Ban
        PERMS_PERIGOSAS_MASK = (
            (1 << 3)    # administrator
            | (1 << 1)  # kick_members
            | (1 << 2)  # ban_members
            | (1 << 5)  # manage_guild
            | (1 << 28) # manage_roles
            | (1 << 4)  # manage_channels
        )
        if cargo.is_bot_managed() or cargo.is_default():
            await interaction.response.send_message(
                embed=embed_erro(
                    "Cargo inválido",
                    "Não podes usar cargos de bots ou @everyone como auto-role.",
                    cfg.nome_servidor,
                ),
                ephemeral=True,
            )
            return
        if cargo.permissions.value & PERMS_PERIGOSAS_MASK:
            await interaction.response.send_message(
                embed=embed_erro(
                    "🚫 Cargo perigoso",
                    "Por segurança, **não podes** configurar um cargo com permissões "
                    "administrativas (Administrator, Ban, Kick, Manage Roles/Guild/Channels) "
                    "como auto-role.\n\n"
                    "Isto previne que membros se auto-promovam a admin/staff.\n\n"
                    "Cria um cargo simples (sem permissões perigosas) e usa esse.",
                    cfg.nome_servidor,
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
                cfg.nome_servidor,
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoRolesCog(bot))
