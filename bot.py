import os
import discord
from discord.ext import commands
from discord import app_commands

# =====================================
# 環境変数
# =====================================

TOKEN = os.environ["DISCORD_TOKEN"]
ADMIN_USERNAME = os.environ["ADMIN_USERNAME"].lstrip("@")

# =====================================
# Discord設定
# =====================================

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# ユーザーID : チケット情報
tickets = {}


# =====================================
# 管理者を探す
# =====================================

async def find_admin():

    # Botが参加しているサーバーから探す
    for guild in bot.guilds:

        for member in guild.members:

            # Discordユーザー名で検索
            if member.name.lower() == ADMIN_USERNAME.lower():
                return member

    return None


# =====================================
# サポート選択メニュー
# =====================================

class SupportSelect(discord.ui.Select):

    def __init__(self):

        options = [
            discord.SelectOption(
                label="相談",
                description="困っていることを相談",
                emoji="💬"
            ),
            discord.SelectOption(
                label="荒らし・迷惑行為の報告",
                description="荒らしや迷惑行為を報告",
                emoji="🚨"
            ),
            discord.SelectOption(
                label="サーバーへの提案",
                description="サーバーへの意見・提案",
                emoji="💡"
            ),
            discord.SelectOption(
                label="その他",
                description="その他のお問い合わせ",
                emoji="❓"
            )
        ]

        super().__init__(
            placeholder="お問い合わせ内容を選択してください",
            options=options,
            custom_id="support_select"
        )

    async def callback(self, interaction: discord.Interaction):

        user = interaction.user
        support_type = self.values[0]

        # 既に受付中
        if user.id in tickets:

            await interaction.response.send_message(
                "⚠️ 現在お問い合わせを受付中です。\n"
                "対応が完了してから、もう一度利用してください。",
                ephemeral=True
            )

            return

        # チケット登録
        tickets[user.id] = {
            "type": support_type,
            "status": "waiting",
            "admin_message_id": None
        }

        await interaction.response.send_message(
            f"✅ **{support_type}**を受け付けました！\n\n"
            "📩 BotからDMを送ります。",
            ephemeral=True
        )

        # ユーザーDM
        try:

            await user.send(
                "🎫 **じいちゃんの鯖 サポート**\n\n"
                f"お問い合わせ種類：**{support_type}**\n\n"
                "お問い合わせ内容を、このDMに送ってください。"
            )

        except discord.Forbidden:

            del tickets[user.id]

            await interaction.followup.send(
                "❌ DMを送れませんでした。\n"
                "BotからのDMを受け取れる設定にしてください。",
                ephemeral=True
            )


# =====================================
# サポートパネル
# =====================================

class SupportView(discord.ui.View):

    def __init__(self):

        super().__init__(timeout=None)

        self.add_item(
            SupportSelect()
        )


# =====================================
# 管理者DMへ送信
# =====================================

async def send_to_admin(
    user,
    support_type,
    content
):

    admin = await find_admin()

    # 管理者が見つからない
    if admin is None:

        print(
            f"❌ 管理者が見つかりません: "
            f"{ADMIN_USERNAME}"
        )

        return False

    embed = discord.Embed(
        title="🎫 新しいお問い合わせ",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="👤 ユーザー",
        value=f"{user.name}\nID: `{user.id}`",
        inline=False
    )

    embed.add_field(
        name="📂 種類",
        value=support_type,
        inline=False
    )

    embed.add_field(
        name="📝 内容",
        value=content[:4000],
        inline=False
    )

    embed.set_footer(
        text="対応完了したら、このDMに 👍 を付けてください"
    )

    try:

        message = await admin.send(
            embed=embed
        )

        # 管理者が押す完了リアクション
        await message.add_reaction("👍")

        tickets[user.id]["admin_message_id"] = message.id

        return True

    except discord.Forbidden:

        print(
            "❌ 管理者へDMを送れません。"
        )

        return False


# =====================================
# DM受信
# =====================================

@bot.event
async def on_message(message):

    # Bot無視
    if message.author.bot:
        return

    # DMのみ
    if isinstance(
        message.channel,
        discord.DMChannel
    ):

        user_id = message.author.id

        if user_id in tickets:

            ticket = tickets[user_id]

            # 最初のお問い合わせ
            if ticket["status"] == "waiting":

                ticket["status"] = "admin"

                # ユーザーへ自動返信
                await message.channel.send(
                    "✅ **お問い合わせを受け付けました！**\n\n"
                    "🤖 管理者へ内容を送信しました。\n"
                    "管理者が対応できるまでお待ちください。"
                )

                # 管理者へDM
                success = await send_to_admin(
                    message.author,
                    ticket["type"],
                    message.content
                )

                if not success:

                    await message.channel.send(
                        "⚠️ 管理者への送信に失敗しました。\n"
                        "管理者に直接お知らせください。"
                    )

    await bot.process_commands(message)


# =====================================
# 管理者の👍を検知
# =====================================

@bot.event
async def on_raw_reaction_add(payload):

    # Bot自身は無視
    if payload.user_id == bot.user.id:
        return

    # リアクションした人の情報
    user = None

    for guild in bot.guilds:

        member = guild.get_member(
            payload.user_id
        )

        if member:
            user = member
            break

    if user is None:
        return

    # 管理者か確認
    if user.name.lower() != ADMIN_USERNAME.lower():
        return

    # 👍以外無視
    if str(payload.emoji) != "👍":
        return

    # チケット検索
    target_user_id = None

    for user_id, ticket in tickets.items():

        if ticket.get(
            "admin_message_id"
        ) == payload.message_id:

            target_user_id = user_id
            break

    if target_user_id is None:
        return

    # ユーザー取得
    try:

        target_user = await bot.fetch_user(
            target_user_id
        )

    except discord.NotFound:

        return

    # ユーザーへ完了DM
    try:

        await target_user.send(
            "✅ **管理者の対応が完了いたしました。**\n\n"
            "お問い合わせありがとうございました！"
        )

    except discord.Forbidden:

        print(
            "❌ ユーザーへのDMに失敗しました。"
        )

    # チケット終了
    del tickets[target_user_id]

    print(
        f"✅ 対応完了: {target_user.name}"
    )


# =====================================
# /チケット
# =====================================

@bot.tree.command(
    name="チケット",
    description="サポートパネルを設置します"
)
@app_commands.checks.has_permissions(
    administrator=True
)
async def ticket(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="🎫 じいちゃんの鯖 サポート",
        description=(
            "お問い合わせはこちらから！\n\n"
            "下のメニューから内容を選択してください。\n\n"
            "💬 **相談**\n"
            "🚨 **荒らし・迷惑行為の報告**\n"
            "💡 **サーバーへの提案**\n"
            "❓ **その他**"
        ),
        color=discord.Color.blurple()
    )

    embed.set_footer(
        text="じいちゃんの鯖 サポートBot"
    )

    await interaction.response.send_message(
        embed=embed,
        view=SupportView()
    )


# =====================================
# /チケット 権限エラー
# =====================================

@ticket.error
async def ticket_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        await interaction.response.send_message(
            "❌ このコマンドは管理者のみ使用できます。",
            ephemeral=True
        )


# =====================================
# Bot起動準備
# =====================================

@bot.event
async def setup_hook():

    # 再起動後もパネルを動かす
    bot.add_view(
        SupportView()
    )

    # スラッシュコマンド同期
    await bot.tree.sync()


# =====================================
# 起動
# =====================================

@bot.event
async def on_ready():

    print(
        f"✅ Botログイン成功: {bot.user}"
    )

    print(
        f"👤 管理者: {ADMIN_USERNAME}"
    )


bot.run(TOKEN)
