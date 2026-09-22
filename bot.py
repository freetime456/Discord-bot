import os
import discord
from discord.ext import commands
from discord import app_commands

TOKEN = os.environ["DISCORD_TOKEN"]
ADMIN_USERNAME = os.environ["ADMIN_USERNAME"].lstrip("@")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

tickets = {}


# =========================
# 管理者を探す
# =========================
async def find_admin(guild):
    for member in guild.members:
        if member.name.lower() == ADMIN_USERNAME.lower():
            return member
    return None


# =========================
# 問い合わせ送信ボタン
# =========================
class CloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="問い合わせを送信",
        style=discord.ButtonStyle.green,
        emoji="📨",
        custom_id="send_ticket"
    )
    async def send_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        user = interaction.user

        if user.id not in tickets:
            await interaction.response.send_message(
                "❌ このチケットは見つかりません。",
                ephemeral=True
            )
            return

        ticket = tickets[user.id]

        if ticket["status"] == "sent":
            await interaction.response.send_message(
                "⚠️ すでに管理者へ送信されています。",
                ephemeral=True
            )
            return

        admin = await find_admin(interaction.guild)

        if admin is None:
            await interaction.response.send_message(
                "❌ 管理者が見つかりません。",
                ephemeral=True
            )
            return

        history = ticket["messages"]

        if not history:
            await interaction.response.send_message(
                "❌ まだお問い合わせ内容がありません。",
                ephemeral=True
            )
            return

        conversation = "\n".join(history)

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
            value=ticket["type"],
            inline=False
        )

        embed.add_field(
            name="📝 会話内容",
            value=conversation[:4000],
            inline=False
        )

        embed.add_field(
            name="🎫 チャンネル",
            value=interaction.channel.mention,
            inline=False
        )

        embed.set_footer(
            text="サポート Bot｜対応完了したら ❤️ を押してください"
        )

        try:
            message = await admin.send(embed=embed)

            await message.add_reaction("❤️")

            ticket["status"] = "sent"
            ticket["admin_message_id"] = message.id

            await interaction.response.send_message(
                "✅ **管理者へお問い合わせ内容を送信しました！**\n\n"
                "管理者が対応するまで、このチャンネルでお待ちください。"
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ 管理者へDMを送れませんでした。",
                ephemeral=True
            )


# =========================
# 問い合わせ種類選択
# =========================
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
        guild = interaction.guild
        support_type = self.values[0]

        if guild is None:
            await interaction.response.send_message(
                "❌ サーバー内で使用してください。",
                ephemeral=True
            )
            return

        if user.id in tickets:
            await interaction.response.send_message(
                "⚠️ すでにお問い合わせ中です。",
                ephemeral=True
            )
            return

        admin = await find_admin(guild)

        if admin is None:
            await interaction.response.send_message(
                "❌ 管理者が見つかりません。",
                ephemeral=True
            )
            return

        # =========================
        # チャンネル権限
        # =========================

        overwrites = {

            guild.default_role:
                discord.PermissionOverwrite(
                    view_channel=False
                ),

            user:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                ),

            admin:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                ),

            guild.me:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_channels=True,
                    manage_messages=True
                )
        }

        # =========================
        # チャンネル名
        # =========================

        channel_name = f"ticket-{user.name}".lower()

        channel_name = "".join(
            c if c.isalnum() or c in "-_" else "-"
            for c in channel_name
        )

        channel_name = channel_name[:90]

        # =========================
        # チャンネル作成
        # =========================

        try:

            channel = await guild.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                reason="サポート Botによる問い合わせチケット作成"
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ チャンネルを作成できません。\n"
                "Botに「チャンネルの管理」権限を付けてください。",
                ephemeral=True
            )

            return

        # =========================
        # チケット情報保存
        # =========================

        tickets[user.id] = {

            "type": support_type,

            "status": "conversation",

            "channel_id": channel.id,

            "admin_message_id": None,

            "messages": []
        }

        # =========================
        # 最初のメッセージ
        # =========================

        embed = discord.Embed(

            title="🎫 サポート Bot",

            description=(
                f"{user.mention} さん、お問い合わせありがとうございます！\n\n"

                f"📂 種類：**{support_type}**\n\n"

                "まず、詳しい内容を教えてください。\n"
                "サポート Botがいくつか質問します。\n\n"

                "最後に📨 **問い合わせを送信**ボタンを押すと、"
                "管理者へ送信されます。"
            ),

            color=discord.Color.blurple()
        )

        await channel.send(embed=embed)

        # =========================
        # 最初の質問
        # =========================

        questions = {

            "相談":
                "💬 どんなことで困っていますか？",

            "荒らし・迷惑行為の報告":
                "🚨 どんな荒らし・迷惑行為がありましたか？",

            "サーバーへの提案":
                "💡 どんな提案をしたいですか？",

            "その他":
                "❓ お問い合わせ内容を詳しく教えてください。"
        }

        await channel.send(
            questions[support_type]
        )

        await interaction.response.send_message(

            "✅ **お問い合わせチャンネルを作成しました！**\n"

            f"🎫 {channel.mention}",

            ephemeral=True
        )


# =========================
# サポートパネル
# =========================
class SupportView(discord.ui.View):

    def __init__(self):

        super().__init__(timeout=None)

        self.add_item(
            SupportSelect()
        )


# =========================
# メッセージ処理
# =========================
@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if message.guild:

        user_id = message.author.id

        if user_id in tickets:

            ticket = tickets[user_id]

            if message.channel.id == ticket["channel_id"]:

                if ticket["status"] == "conversation":

                    ticket["messages"].append(

                        f"👤 {message.author.name}: "
                        f"{message.content}"
                    )

                    await message.channel.send(

                        "🤖 **サポート Bot**\n\n"
                        "ありがとうございます！\n"
                        "ほかに伝えておきたいことはありますか？\n\n"
                        "内容がすべて終わったら、"
                        "下の📨ボタンから管理者へ送信してください。"
                    )

                    await message.channel.send(

                        "📨 **お問い合わせ内容がまとまったらこちら**",

                        view=CloseView()
                    )

    await bot.process_commands(message)


# =========================
# 管理者の ❤️ を検知
# =========================
@bot.event
async def on_raw_reaction_add(payload):

    if bot.user and payload.user_id == bot.user.id:
        return

    if str(payload.emoji) != "❤️":
        return

    admin = None

    for guild in bot.guilds:

        member = guild.get_member(
            payload.user_id
        )

        if member:

            if member.name.lower() == ADMIN_USERNAME.lower():

                admin = member

                break

    if admin is None:
        return

    target_user_id = None

    for user_id, ticket in tickets.items():

        if ticket.get(
            "admin_message_id"
        ) == payload.message_id:

            target_user_id = user_id

            break

    if target_user_id is None:
        return

    ticket = tickets[target_user_id]

    channel = bot.get_channel(
        ticket["channel_id"]
    )

    if channel is None:

        try:

            channel = await bot.fetch_channel(
                ticket["channel_id"]
            )

        except discord.NotFound:

            del tickets[target_user_id]

            return

    # =========================
    # チャンネルに完了通知
    # =========================

    await channel.send(

        "✅ **サポート Bot**\n\n"
        "管理者の対応が完了いたしました！\n\n"
        "お問い合わせありがとうございました。"
    )

    # =========================
    # ユーザーにもDM
    # =========================

    try:

        user = await bot.fetch_user(
            target_user_id
        )

        await user.send(

            "✅ **サポート Bot**\n\n"
            "お問い合わせの対応が完了しました！\n\n"
            "お問い合わせありがとうございました。"
        )

    except:

        pass

    del tickets[target_user_id]

    print(
        f"✅ サポート Bot｜対応完了: {target_user_id}"
    )


# =========================
# /チケット コマンド
# =========================
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

        title="🎫 サポート Bot",

        description=(

            "お問い合わせはこちらから！\n\n"

            "下のメニューから内容を選択してください。\n\n"

            "💬 **相談**\n"
            "🚨 **荒らし・迷惑行為の報告**\n"
            "💡 **サーバーへの提案**\n"
            "❓ **その他**\n\n"

            "🤖 **サポート Botがお問い合わせを受け付けます。**"
        ),

        color=discord.Color.blurple()
    )

    embed.set_footer(
        text="サポート Bot"
    )

    await interaction.response.send_message(

        embed=embed,

        view=SupportView()
    )


# =========================
# コマンドエラー
# =========================
@ticket.error
async def ticket_error(
    interaction: discord.Interaction,
    error
):

    if isinstance(
        error,
        app_commands.errors.MissingPermissions
    ):

        await interaction.response.send_message(

            "❌ このコマンドは管理者のみ使用できます。",

            ephemeral=True
        )


# =========================
# Bot起動時
# =========================
@bot.event
async def setup_hook():

    bot.add_view(
        SupportView()
    )

    bot.add_view(
        CloseView()
    )

    await bot.tree.sync()


# =========================
# ログイン成功
# =========================
@bot.event
async def on_ready():

    print(
        f"🤖 サポート Bot ログイン成功: {bot.user}"
    )

    print(
        f"👤 管理者: {ADMIN_USERNAME}"
    )


# =========================
# Bot起動
# =========================
bot.run(TOKEN)
