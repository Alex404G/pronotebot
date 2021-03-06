import time
from datetime import datetime
from collections import defaultdict
from typing import List, DefaultDict

import discord
import pronotepy
from discord.ext.commands import Context
from discord.ext import commands, tasks

from app import JsonData, JsonDict
from app.utils import json_wr


class Pronote(commands.Cog):

    def __init__(self, client):
        """Initialize the search for new homeworks."""
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        self.refresh_pronote.start()

    @tasks.loop(seconds=300)
    async def refresh_pronote(self) -> None:

        date = time.strftime("%Y-%m-%d %H:%M", time.gmtime())

        # Does not work at night
        hour = datetime.now().hour
        if hour > 22 or hour < 5:
            return

        try:
            pronote: pronotepy.Client = pronotepy.Client(
                self.client.config["url"],
                self.client.config["username"],
                self.client.config["password"]
            )

        except pronotepy.CryptoError:
            print(
                "Connexion à Pronote échoué. "
                "Mauvais nom d'utilisateur ou mot de passe."
            )
            await self.client.close()
            return

        except pronotepy.PronoteAPIError:
            print(f"{date} - Connexion à Pronote échoué")
            return

        if not pronote.logged_in:
            print(f"{date} - Connexion à Pronote échoué")
            return

        fetched_homeworks: List[pronote.homework] = pronote.homework(
            pronote.start_day
        )

        homeworks_file: JsonData = json_wr("devoirs")

        homeworks: DefaultDict[str, List[pronote.homework]] = defaultdict(list)

        for homework in fetched_homeworks:
            homeworks[str(homework.date)].append(
                {
                    "subject": homework.subject.name,
                    "description": homework.description.replace("\n", " ")
                }
            )

        try:
            pronote_channel: discord.TextChannel = (
                await self.client.fetch_channel(
                    int(self.client.config.get("channelID"))
                )
            )
        except discord.errors.NotFound:
            print("Channel non-trouvé ou inexistant")
            await self.client.close()
            return

        if homeworks_file == {} or isinstance(homeworks_file, list):
            json_wr("devoirs", "w", homeworks)
            print("La première connexion aux serveurs de PRONOTE à été un "
                  "succès, les prochains devoirs seront envoyés ici.")
            await pronote_channel.send(
                embed=discord.Embed(
                    title="Première connexion réussie",
                    description=(
                        "La connexion aux serveurs de PRONOTE à été un succès, "
                        "les prochains devoirs seront envoyés ici."
                    ),
                    color=0x1E744F
                )
            )
            return

        if homeworks == homeworks_file:
            print(f"{date} - Aucun nouveau devoir trouvé.")
            return

        json_wr("devoirs", "w", homeworks)

        homeworks_list: list = []
        for key, value in homeworks.items():
            for i in value:
                i["date"] = key
            homeworks_list.extend(value)

        homeworks_old_list: list = []
        for key, value in homeworks_file.items():
            for i in value:
                i["date"] = key
            homeworks_old_list.extend(value)

        new_homework_count = 0

        for homework in homeworks_list:
            if homework in homeworks_old_list:
                continue

            new_homework_count += 1

            time_marker: int = int(
                time.mktime(time.strptime(homework["date"], "%Y-%m-%d"))
            )

            await pronote_channel.send(
                embed=discord.Embed(
                    title=(
                        f"{homework['subject']}\n"
                        f"Pour le <t:{time_marker}:D>"
                    ),
                    description=homework["description"],
                    color=0x1E744F
                )
            )
        print(f"{date} - {new_homework_count} nouveaux devoirs !")

    @commands.command(name="homeworks", aliases=("devoirs",))
    async def change_channel(self, ctx: Context) -> None:
        homeworks: JsonDict = json_wr("devoirs")

        embed = discord.Embed(
            title="Prochains devoirs",
            color=self.client.embed_color
        )

        today = time.time()
        homeworks_dict = {}
        for date, homeworks_list in homeworks.items():

            date_timestamp = int(time.mktime(time.strptime(date, "%Y-%m-%d")))
            if date_timestamp >= today:
                homeworks_dict[date_timestamp] = homeworks_list

        homeworks_dict = {
            key: homeworks_dict[key]
            for key in sorted(homeworks_dict)
        }

        for date, homeworks_list in homeworks_dict.items():
            embed.add_field(
                name=f"Pour le <t:{date}:D>",
                value="\n".join([
                    f"**- {h['subject']} :** {h['description']}"
                    for h in homeworks_list
                ]),
                inline=False
            )

        await ctx.send(embed=embed)


def setup(client) -> None:
    client.add_cog(Pronote(client))
