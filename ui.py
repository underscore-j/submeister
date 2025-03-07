''' For complex UI-related tasks '''

import discord

import data
import subsonic
import logging

from typing import Union

logger = logging.getLogger(__name__)



class SysMsg:
    ''' A class for sending system messages '''

    @staticmethod
    async def msg(interaction: discord.Interaction, header: str, message: str=None, thumbnail: str=None) -> None:
        ''' Generic message function. Creates a message formatted as an embed '''

        embed = discord.Embed(color=discord.Color.orange(), title=header, description=message)
        file = discord.utils.MISSING

        # Attach a thumbnail if one was provided (as a local file)
        if thumbnail is not None:
            file = discord.File(thumbnail, filename="image.png")
            embed.set_thumbnail(url="attachment://image.png")

        # Attempt to send the error message, up to 3 times
        attempt = 0
        while attempt < 3:
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(file=file, embed=embed)
                else:
                    await interaction.response.send_message(file=file, embed=embed)
                return
            except discord.NotFound:
                logger.warning("Attempt %d at sending a system message failed...", attempt+1)
                attempt += 1


    @staticmethod
    async def playing(interaction: discord.Interaction) -> None:
        ''' Sends a message containing the currently playing song '''
        player = data.guild_data(interaction.guild_id).player
        song = player.current_song
        cover_art = subsonic.get_album_art_file(song.cover_id)
        desc = f"**{song.title}** - *{song.artist}*\n{song.album} ({song.duration_printable})"
        await __class__.msg(interaction, "Playing:", desc, cover_art)

    @staticmethod
    async def playback_ended(interaction: discord.Interaction) -> None:
        ''' Sends a message indicating playback has ended '''
        await __class__.msg(interaction, "Playback ended")

    @staticmethod
    async def disconnected(interaction: discord.Interaction) -> None:
        ''' Sends a message indicating the bot disconnected from voice channel '''
        await __class__.msg(interaction, "Disconnected from voice channel")

    @staticmethod
    async def starting_queue_playback(interaction: discord.Interaction) -> None:
        ''' Sends a message indicating queue playback has started '''
        await __class__.msg(interaction, "Started queue playback")

    @staticmethod
    async def added_to_queue(interaction: discord.Interaction, song: subsonic.Song) -> None:
        ''' Sends a message indicating the selected song was added to queue '''
        desc = f"**{song.title}** - *{song.artist}*\n{song.album} ({song.duration_printable})"
        await __class__.msg(interaction, f"{interaction.user.display_name} added track to queue", desc)

    @staticmethod
    async def added_album_to_queue(interaction: discord.Interaction, album:subsonic.Album) -> None:
        desc = f"**{album.name}**\n{album.artist}({album.song_count} tracks, {album.duration_printable})"
        await __class__.msg(interaction, f"{interaction.user.display_name} added album to queue", desc)

    @staticmethod
    async def queue_cleared(interaction: discord.Interaction) -> None:
        ''' Sends a message indicating a user cleared the queue '''
        await __class__.msg(interaction, f"{interaction.user.display_name} cleared the queue")

    @staticmethod
    async def skipping(interaction: discord.Interaction) -> None:
        ''' Sends a message indicating the current song was skipped '''
        await __class__.msg(interaction, "Skipped track")


class ErrMsg:
    ''' A class for sending error messages '''

    @staticmethod
    async def msg(interaction: discord.Interaction, message: str) -> None:
        ''' Generic message function. Creates an error message formatted as an embed '''
        embed = discord.Embed(color=discord.Color.orange(), title="Error", description=message)

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @staticmethod
    async def user_not_in_voice_channel(interaction: discord.Interaction) -> None:
        ''' Sends an error message indicating user is not in a voice channel '''
        await __class__.msg(interaction, "You are not connected to a voice channel.")

    @staticmethod
    async def bot_not_in_voice_channel(interaction: discord.Interaction) -> None:
        ''' Sends an error message indicating bot is connect to a voice channel '''
        await __class__.msg(interaction, "Not currently connected to a voice channel.")

    @staticmethod
    async def cannot_connect_to_voice_channel(interaction: discord.Interaction) -> None:
        ''' Sends an error message indicating bot is unable to connect to a voice channel '''
        await __class__.msg(interaction, "Cannot connect to voice channel.")

    @staticmethod
    async def queue_is_empty(interaction: discord.Interaction) -> None:
        ''' Sends an error message indicating the queue is empty '''
        await __class__.msg(interaction, "Queue is empty.")

    @staticmethod
    async def already_playing(interaction: discord.Interaction) -> None:
        ''' Sends an error message indicating that music is already playing '''
        await __class__.msg(interaction, "Already playing.")

    @staticmethod
    async def not_playing(interaction: discord.Interaction) -> None:
        ''' Sends an error message indicating nothing is playing '''
        await __class__.msg(interaction, "No track is playing.")



def parse_subsonic_items_as_selection_embed(items: list[Union[subsonic.Song, subsonic.Album, subsonic.Artist]], header: str, footer: str) -> list[discord.SelectOption]:
    ''' Takes a list of items from the Subsonic API and parses them into a Discord embed suitable for selection '''
    options_str = ""

    for item in items:
        if isinstance(item, subsonic.Song):
            # Trim displayed tags to fit neatly within the embed
            tr_title = item.title
            tr_artist = item.artist
            tr_album = (item.album[:68] + "...") if len(item.album) > 68 else item.album

            # Only trim the longest tag on the first line
            top_str_length = len(item.title + " - " + item.artist)
            if top_str_length > 71:
                
                if tr_title > tr_artist:
                    tr_title = item.title[:(68 - top_str_length)] + '...'
                else:
                    tr_artist = item.artist[:(68 - top_str_length)] + '...'

            # Add each of the results to our output string
            options_str += f"**{tr_title}** - *{tr_artist}* \n*{tr_album}* ({item.duration_printable})\n\n"
        if isinstance(item, subsonic.Album):
            options_str += f"**{item.name}**\n*{item.artist}* ({item.song_count} tracks, {item.duration_printable})\n\n"
        if isinstance(item, subsonic.Artist):
            options_str += f"**{item.name}**\n{item.album_count} albums\n\n"

    # Append the footer
    options_str += footer

    # Return a discord embed for the items
    return discord.Embed(color=discord.Color.orange(), title=header, description=options_str)

def parse_subsonic_items_as_selection_options(items: list[Union[subsonic.Song, subsonic.Album, subsonic.Artist]]) -> list[discord.SelectOption]:
    ''' Takes a list of items from the Subsonic API and parses them into a Discord selection list '''
    select_options = []
    for i, item in enumerate(items):
        select_label = ""
        select_desc = ""
        if isinstance(item, subsonic.Song):
            select_label = item.title
            select_desc = f"song by {item.artist}"
        if isinstance(item, subsonic.Album):
            select_label = item.name
            select_desc = f"album by {item.artist}"
        if isinstance(item, subsonic.Artist):
            select_label = item.name
            select_desc = f"artist"
        select_option = discord.SelectOption(label=select_label, description=select_desc, value=i)
        select_options.append(select_option)
    return select_options
