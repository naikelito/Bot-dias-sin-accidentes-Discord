# wardaybot.py
# Requisitos:
#   pip install disnake
# Configura:
#   - DISCORD_TOKEN (variable de entorno) o pega el token en MY_TOKEN
#   - TEXT_CHANNEL_ID con el ID del canal donde se mostrará el contador

import os
import time
import disnake
from disnake.ext import commands, tasks

# ========== CONFIGURA AQUÍ ==========
TEXT_CHANNEL_ID = 1427876160867536926  # <-- REEMPLAZA por el ID del canal de texto
MY_TOKEN = "a"  # usa variable de entorno o pega aquí
DATA_FILE = "data.txt"
MSG_ID_FILE = "message_id.txt"
# ====================================

def now_ts() -> int:
    return int(time.time())

def ensure_data_file():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            f.write(str(now_ts()))

def read_last_time() -> int:
    ensure_data_file()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        content = (f.read() or "0").strip()
    try:
        return int(content)
    except ValueError:
        return now_ts()

def write_last_time(ts: int):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        f.write(str(ts))

def save_message_id(mid: int):
    with open(MSG_ID_FILE, "w", encoding="utf-8") as f:
        f.write(str(mid))

def read_message_id() -> int | None:
    if not os.path.exists(MSG_ID_FILE):
        return None
    with open(MSG_ID_FILE, "r", encoding="utf-8") as f:
        content = (f.read() or "").strip()
    try:
        return int(content)
    except ValueError:
        return None

def format_elapsed(last_time: int) -> tuple[int, str]:
    dt = now_ts() - last_time
    if dt < 0:
        dt = 0
    days = dt // 86400
    rem = dt % 86400
    hours = rem // 3600
    rem %= 3600
    minutes = rem // 60
    seconds = rem % 60
    hhmmss = f"{hours:02}:{minutes:02}:{seconds:02}"
    return days, hhmmss

def render_content(last_time: int) -> str:
    days, hhmmss = format_elapsed(last_time)
    marker = "〔accident_counter〕"
    return (
        f" **Días sin catástrofes:** **{days}**\n"
    )

# ----- Vista con botón persistente -----
class ResetView(disnake.ui.View):
    def __init__(self, bot: "AccidentBot"):
        # timeout=None => persistente tras reinicios
        super().__init__(timeout=None)
        self.bot = bot

    @disnake.ui.button(
        label="Reiniciar contador",
        style=disnake.ButtonStyle.danger,
        custom_id="accident_counter:reset",  # necesario para persistencia
        emoji="🔁",
    )
    async def reset_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        new_ts = now_ts()
        write_last_time(new_ts)
        self.bot.last_time = new_ts
        try:
            await self.bot.update_counter_message()
            await inter.response.send_message("✅ Contador reiniciado.", ephemeral=True)
        except Exception as e:
            await inter.response.send_message(f"⚠️ Ocurrió un error al actualizar: {e}", ephemeral=True)

# ----- Bot -----
class AccidentBot(commands.InteractionBot):
    def __init__(self):
        intents = disnake.Intents.default()
        super().__init__(intents=intents)
        self.last_time: int = read_last_time()
        self.counter_message: disnake.Message | None = None
        # ❌ NO iniciar tareas ni add_view aquí (no hay event loop todavía)

    async def setup_hook(self):
        # ✅ Aquí ya hay event loop: registra la View persistente y arranca la tarea
        self.add_view(ResetView(self))
        self.bg_updater.start()

    async def on_ready(self):
        print(f"✅ Bot iniciado como {self.user} (ID: {self.user.id})")
        await self.ensure_counter_message()

    @tasks.loop(seconds=60)
    async def bg_updater(self):
        await self.update_counter_message()

    @bg_updater.before_loop
    async def before_bg_updater(self):
        await self.wait_until_ready()

    async def ensure_counter_message(self):
        """Crea o recupera el mensaje del contador en el canal configurado y adjunta la vista."""
        channel = self.get_channel(TEXT_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.fetch_channel(TEXT_CHANNEL_ID)
            except Exception as e:
                print(f"❌ No se pudo obtener el canal {TEXT_CHANNEL_ID}: {e}")
                return

        msg_id = read_message_id()
        message: disnake.Message | None = None

        if msg_id:
            try:
                message = await channel.fetch_message(msg_id)
            except Exception:
                message = None

        view = ResetView(self)

        if message is None:
            content = render_content(self.last_time)
            try:
                message = await channel.send(content, view=view)
                save_message_id(message.id)
            except Exception as e:
                print(f"❌ No se pudo enviar el mensaje al canal: {e}")
                return
        else:
            try:
                await message.edit(view=view)
            except Exception as e:
                print(f"⚠️ No se pudo re-vincular la vista: {e}")

        self.counter_message = message

    async def update_counter_message(self):
        """Edita el mensaje del contador si existe; si no, intenta crearlo."""
        if self.counter_message is None:
            await self.ensure_counter_message()
            if self.counter_message is None:
                return
        try:
            await self.counter_message.edit(content=render_content(self.last_time), view=ResetView(self))
        except disnake.NotFound:
            self.counter_message = None
            await self.ensure_counter_message()
        except Exception as e:
            print(f"⚠️ Error al actualizar el mensaje: {e}")

# ----- slash command opcional -----
bot = AccidentBot()

@bot.slash_command(description="Reinicia manualmente el contador de días sin accidentes")
async def reset_counter(inter: disnake.ApplicationCommandInteraction):
    new_ts = now_ts()
    write_last_time(new_ts)
    bot.last_time = new_ts
    await bot.update_counter_message()
    await inter.response.send_message("✅ Contador reiniciado.", ephemeral=True)

# ----- run -----
if __name__ == "__main__":
    if not MY_TOKEN or MY_TOKEN == "PEGATU_TOKEN_AQUI":
        raise RuntimeError("Debes configurar el token en DISCORD_TOKEN o en MY_TOKEN.")
    bot.run(MY_TOKEN)
