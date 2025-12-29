''' Submeister - A Discord bot that streams music from your personal Subsonic server. '''

import logging
import os

import atexit
import discord

from discord.ext import commands

import data

from util import env
from util import logs

class SubmeisterClient(commands.Bot):
    ''' An instance of the submeister client '''

    test_guild: int

    def __init__(self, logger, test_guild: int=None) -> None:
        self.test_guild = test_guild
        self.logger = logger

        super().__init__(command_prefix=commands.when_mentioned, intents=discord.Intents.all())

    async def load_extensions(self) -> None:
        ''' Auto-loads all extensions present within the `./extensions` directory. '''

        for ext_name in ["music", "owner"]:
                try:
                    await self.load_extension(f"extensions.{ext_name}")
                except commands.errors.ExtensionError as err:
                    if isinstance(err, commands.errors.ExtensionNotFound):
                        self.logger.warning("Failed to load extension '%s'. Extension was not found.", ext_name)
                    if isinstance(err, commands.errors.ExtensionAlreadyLoaded):
                        self.logger.warning("Failed to load extension '%s'. Extension was already loaded.", ext_name)
                    if isinstance(err, commands.errors.NoEntryPointError):
                        self.logger.error("Failed to load extension '%s'. No entry point was found in the file.", ext_name, exc_info=err)
                    if isinstance(err, commands.errors.ExtensionFailed):
                        self.logger.error("Failed to load extension '%s'. Extension setup failed.", ext_name, exc_info=err)
                else:
                    self.logger.info("Extension '%s' loaded successfully.", ext_name)

    async def sync_command_tree(self) -> None:
        ''' Synchronizes the command tree with the guild used for testing. '''

        guild = discord.Object(self.test_guild)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def setup_hook(self) -> None:
        ''' Setup done after login, prior to events being dispatched. '''

        await self.load_extensions()

        if self.test_guild:
            await self.sync_command_tree()

    async def on_ready(self) -> None:
        ''' Event called when the client is done preparing. '''

        self.logger.info("Logged as: %s | Connected Guilds: %s | Loaded Extensions: %s", self.user, len(self.guilds), list(self.extensions))

def exit_handler():
    ''' Function ran on application exit. '''

    data.save_guild_properties_to_disk()

def run():
    logs.setup_logging()
    logger = logging.getLogger(__name__)

    data.load_guild_properties_from_disk()
    atexit.register(exit_handler)

    client = SubmeisterClient(logger, test_guild=env.DISCORD_TEST_GUILD)
    client.run(env.DISCORD_BOT_TOKEN, log_handler=None)

