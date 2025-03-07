''' An extention allowing for music playback functionality '''

import logging
import discord

from discord import app_commands
from discord.ext import commands

import data
import player
import subsonic
import ui

from typing import Union

from submeister import SubmeisterClient

logger = logging.getLogger(__name__)

class MusicCog(commands.Cog):
    ''' A Cog containing music playback commands '''

    bot : SubmeisterClient

    def __init__(self, bot: SubmeisterClient):
        self.bot = bot

    async def get_voice_client(self, interaction: discord.Interaction, *, should_connect: bool=False) -> discord.VoiceClient:
        ''' Returns a voice client instance for the current guild '''

        # Get the voice client for the guild
        voice_client = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)

        # Connect to a voice channel
        if voice_client is None and should_connect:
            try:
                voice_client = await interaction.user.voice.channel.connect()
            except AttributeError:
                await ui.ErrMsg.cannot_connect_to_voice_channel(interaction)

        return voice_client

    @app_commands.command(name="play", description="Plays a specified track")
    @app_commands.describe(query="Enter a search query")
    async def play(self, interaction: discord.Interaction, query: str=None) -> None:
        ''' Play a track matching the given title/artist query '''

        # Check if user is in voice channel
        print(interaction.user.voice)
        if interaction.user.voice is None:
            return await ui.ErrMsg.user_not_in_voice_channel(interaction)

        # Get a valid voice channel connection
        voice_client = await self.get_voice_client(interaction, should_connect=True)

        # Don't attempt playback if the bot is already playing
        if voice_client.is_playing() and query is None:
            return await ui.ErrMsg.already_playing(interaction)

        # Get the guild's player
        player = data.guild_data(interaction.guild_id).player

        # Check queue if no query is provided
        if query is None:

            # Display error if queue is empty & autoplay is disabled
            if player.queue == [] and data.guild_properties(interaction.guild_id).autoplay_mode == data.AutoplayMode.NONE:
                return await ui.ErrMsg.queue_is_empty(interaction)

            # Begin playback of queue
            await ui.SysMsg.starting_queue_playback(interaction)
            await player.play_audio_queue(interaction, voice_client)
            return

        # Send our query to the subsonic API and retrieve a list of 1 song
        songs = subsonic.search(query, artist_count=0, album_count=0, song_count=1)

        # Display an error if the query returned no results
        if len(songs) == 0:
            await ui.ErrMsg.msg(interaction, f"No result found for **{query}**.")
            return
        
        # Add the first result to the queue and handle queue playback
        player.queue.append(songs[0])

        await ui.SysMsg.added_to_queue(interaction, songs[0])
        await player.play_audio_queue(interaction, voice_client)

    class SelectionHandler:
        ''' A callable to implement the callback across all three song selection UI types '''
        def __init__(self, selection: list[Union[subsonic.Song, subsonic.Album, subsonic.Artist]], selector: discord.ui.Select, owner):
            self._items = selection
            self._selector = selector
            self._owner = owner

        async def __call__(self, interaction: discord.Interaction) -> None:
            item = self._items[int(self._selector.values[0])]

            if isinstance(item, subsonic.Song):
                # Song selected: Queue it
                voice_client = await self._owner.get_voice_client(interaction)

                # Don't allow users who aren't in a voice channel with the bot to queue tracks
                if voice_client is not None and interaction.user.status is None:
                    return await ui.ErrMsg.user_not_in_voice_channel(interaction)

                # Get the guild's player
                player = data.guild_data(interaction.guild_id).player

                # Add the selected song to the queue
                player.queue.append(item)

                # Let the user know a track has been added to the queue
                await ui.SysMsg.added_to_queue(interaction, item)

                # Fetch the cover art in advance
                subsonic.get_album_art_file(item.cover_id)

                # Attempt to play the audio queue, if the bot is in the voice channel
                if voice_client is not None:
                    await player.play_audio_queue(interaction, voice_client)
                
            if isinstance(item, subsonic.Album):
                # Album selected: launch album UI
                await self._owner.album_ui(interaction, item)
            if isinstance(item, subsonic.Artist):
                # Artist selected: launch artist UI
                await self._owner.artist_ui(interaction, item)


    async def album_ui(self, interaction: discord.Interaction, album: subsonic.Album) -> None:
        ''' Album UI: lists an album's tracks, and alllows queueing them all '''
        songs = subsonic.get_album_songs(album)

        # Dispaly an error if we obtain no results
        if len(songs) == 0:
            await ui.ErrMsg.msg(interaction, f"No tracks found for album **{album.name}")
            return

        # Create a view for our response
        view = discord.ui.View()

        # Create a select menu option for each of our results
        select_options = ui.parse_subsonic_items_as_selection_options(songs)

        # Create a select menu, populated with our options
        song_selector = discord.ui.Select(placeholder="Select a track", options=select_options)
        view.add_item(song_selector)
        
        # Instantiate a selection handler for this selection
        song_selector.callback = self.SelectionHandler(songs, song_selector, self)

        # Add a button to queue all songs at once
        play_all_button = discord.ui.Button(label="Play All", style=discord.ButtonStyle.primary, custom_id="play_all_button")
        view.add_item(play_all_button)

        # Add a handler for this button
        async def play_all(interaction: discord.Interaction) -> None:
            voice_client = await self.get_voice_client(interaction)

            # Don't allow users who aren't in a voice channel with the bot to queue tracks
            if voice_client is not None and interaction.user.status is None:
                return await ui.ErrMsg.user_not_in_voice_channel(interaction)

            # Get the guild's player
            player = data.guild_data(interaction.guild_id).player

            # Add the selected album to the queue
            for song in songs:
                player.queue.append(song)

            # Let the user know a track has been added to the queue
            await ui.SysMsg.added_album_to_queue(interaction, album)

            # Fetch the cover art in advance
            subsonic.get_album_art_file(album.cover_id)

            # Attempt to play the audio queue, if the bot is in the voice channel
            if voice_client is not None:
                await player.play_audio_queue(interaction, voice_client)

        play_all_button.callback = play_all

        # Generate a formatted embed for the current search results
        song_list = ui.parse_subsonic_items_as_selection_embed(songs, f"{album.artist} - **{album.name}**", "")

        # Show our song selection menu
        await interaction.response.send_message(embed=song_list, view=view, ephemeral=True)

    async def artist_ui(self, interaction: discord.Interaction, artist: subsonic.Artist) -> None:
        ''' Artist UI: lists an artist's albums, and allows queueing all their tracks '''
        albums = subsonic.get_artist_albums(artist)

        # Dispaly an error if we obtain no results
        if len(albums) == 0:
            await ui.ErrMsg.msg(interaction, f"No albums found for artist **{artist.name}")
            return

        # Create a view for our response
        view = discord.ui.View()

        # Create a select menu option for each of our results
        select_options = ui.parse_subsonic_items_as_selection_options(albums)

        # Create a select menu, populated with our options
        album_selector = discord.ui.Select(placeholder="Select an album", options=select_options)
        view.add_item(album_selector)
        
        # Instantiate a selection handler for this selection
        album_selector.callback = self.SelectionHandler(albums, album_selector, self)

        # Add a button to queue all albums at once
        play_all_button = discord.ui.Button(label="Play All", style=discord.ButtonStyle.primary, custom_id="play_all_button")
        view.add_item(play_all_button)

        # Add a handler for this button
        async def play_all(interaction: discord.Interaction) -> None:
            voice_client = await self.get_voice_client(interaction)

            # Don't allow users who aren't in a voice channel with the bot to queue tracks
            if voice_client is not None and interaction.user.status is None:
                return await ui.ErrMsg.user_not_in_voice_channel(interaction)

            # Get the guild's player
            player = data.guild_data(interaction.guild_id).player

            # Add all albums to the queue
            for album in albums:
                for song in subsonic.get_album_songs(album):
                    player.queue.append(song)
                await ui.SysMsg.added_album_to_queue(interaction, album)
                subsonic.get_album_art_file(album.cover_id)

            # Attempt to play the audio queue, if the bot is in the voice channel
            if voice_client is not None:
                await player.play_audio_queue(interaction, voice_client)

        play_all_button.callback = play_all

        # Generate a formatted embed for the current search results
        album_list = ui.parse_subsonic_items_as_selection_embed(albums, f"**{artist.name}**", "")

        # Show our album selection menu
        await interaction.response.send_message(embed=album_list, view=view, ephemeral=True)

    async def search_ui(self, interaction: discord.Interaction, query: str, header: str, max_artists = None, max_albums = None, max_songs = None) -> None:
        ''' Generic Search UI to implement search for Songs, Albums or Artists or mixed results '''
        max_results = 10
        artists_seen = 0
        albums_seen = 0
        songs_seen = 0

        # Compute how many of each type of result to obtain
        max_artist_results = max_results if max_artists is None else min(max_results, max(0, max_artists - artists_seen))
        max_album_results = max_results if max_albums is None else min(max_results, max(0, max_albums - albums_seen))
        max_song_results = max_results if max_songs is None else min(max_results, max(0, max_songs - songs_seen))
        
        # Query subsonic
        results = subsonic.search(query, artist_count = max_artist_results, artist_offset = artists_seen, album_count = max_album_results, album_offset = albums_seen, song_count = max_song_results, song_offset = songs_seen)[:max_results]

        # Create a view for our response
        view = discord.ui.View()

        # Create a select menu option for each of our results
        select_options = ui.parse_subsonic_items_as_selection_options(results)

        # Create a select menu, populated with our options
        result_selector = discord.ui.Select(placeholder="Select a result", options=select_options)
        view.add_item(result_selector)

        result_selector.callback = self.SelectionHandler(results, result_selector, self)

        # Create page navigation buttons
        prev_button = discord.ui.Button(label="<", custom_id="prev_button")
        next_button = discord.ui.Button(label=">", custom_id="next_button")
        view.add_item(prev_button)
        view.add_item(next_button)

        # Callback to handle interactions with page navigator buttons
        async def page_changed(interaction: discord.Interaction) -> None:
            nonlocal max_results, artists_seen, albums_seen, songs_seen, results, result_selector

            # Determine by how much to adjust the "seen" amounts
            artists_in_result = len([e for e in results if isinstance(e, subsonic.Artist)])
            albums_in_result = len([e for e in results if isinstance(e, subsonic.Album)])
            songs_in_result = len([e for e in results if isinstance(e, subsonic.Song)])

            # Adjust the search offset according to the button pressed
            if interaction.data["custom_id"] == "prev_button":
                if artists_seen <= 0 and albums_seen <= 0 and songs_seen <= 0:
                    await interaction.response.defer()
                    return
                artists_seen -= artists_in_result
                albums_seen -= albums_in_result
                songs_seen -= songs_in_result
            elif interaction.data["custom_id"] == "next_button":
                artists_seen += artists_in_result
                albums_seen += albums_in_result
                songs_seen += songs_in_result

            # Back up previous results before making a new query
            results_lastpage = results

            # Compute how many of each type of result to obtain
            max_artist_results = max_results if max_artists is None else min(max_results, max(0, max_artists - artists_seen))
            max_album_results = max_results if max_albums is None else min(max_results, max(0, max_albums - albums_seen))
            max_song_results = max_results if max_songs is None else min(max_results, max(0, max_songs - songs_seen))
            
            # Query subsonic
            results = subsonic.search(query, artist_count = max_artist_results, artist_offset = artists_seen, album_count = max_album_results, album_offset = albums_seen, song_count = max_song_results, song_offset = songs_seen)[:max_results]

            # If there are no results on this page, go back one page and don't update the response
            if len(results) == 0:
                artists_seen -= artists_in_result
                albums_seen -= albums_in_result
                songs_seen -= songs_in_result
                results = results_lastpage
                await interaction.response.defer()
                return

            # Generate a new embed containing this page's search results
            result_list = ui.parse_subsonic_items_as_selection_embed(results, header, f"Page: {((artists_seen + albums_seen + songs_seen) // max_results) + 1}")

            # Create a selection menu, populated with our new options
            select_options = ui.parse_subsonic_items_as_selection_options(results)

            # Update the selector in the existing view
            view.remove_item(result_selector)
            result_selector = discord.ui.Select(placeholder="Select a result", options=select_options)
            result_selector.callback = self.SelectionHandler(results, result_selector, self)
            view.add_item(result_selector)

            # Update the message to show the new search results
            await interaction.response.edit_message(embed=result_list, view=view)


        # Assign the page_changed callback to the page navigation buttons
        prev_button.callback = page_changed
        next_button.callback = page_changed

        # Generate a formatted embed for the current search results
        result_list = ui.parse_subsonic_items_as_selection_embed(results, header, f"Page: {((artists_seen + albums_seen + songs_seen) // max_results) + 1}")

        # Show our song selection menu
        await interaction.response.send_message(embed=result_list, view=view, ephemeral=True)



    @app_commands.command(name="search", description="Search for a track, album or artist")
    @app_commands.describe(query="Enter a search query")
    async def search(self, interaction: discord.Interaction, query: str) -> None:
        ''' Search across artists, titles and tracks, limiting the number of artist and album results '''
        await self.search_ui(interaction, query, f"**Search Results:** {query}", 2, 3, None)

    @app_commands.command(name="search-song", description="Search for a track")
    @app_commands.describe(query="Enter a search query")
    async def search_song(self, interaction: discord.Interaction, query: str) -> None:
        ''' Search for a track and list results '''
        await self.search_ui(interaction, query, f"**Track Search:** {query}", 0, 0, None)

    @app_commands.command(name="search-album", description="Search for an album")
    @app_commands.describe(query="Enter a search query")
    async def search_album(self, interaction: discord.Interaction, query: str) -> None:
        ''' Search for albums and list results '''
        await self.search_ui(interaction, query, f"**Album Search:** {query}", 0, None, 0)

    @app_commands.command(name="search-artist", description="Search for an artist")
    @app_commands.describe(query="Enter a search query")
    async def search_artist(self, interaction: discord.Interaction, query: str) -> None:
        ''' Search for artists and list results '''
        await self.search_ui(interaction, query, f"**Artist Search:** {query}", None, 0, 0)


    @app_commands.command(name="stop", description="Stop playing the current track")
    async def stop(self, interaction: discord.Interaction) -> None:
        ''' Disconnect from the active voice channel '''

        # Get the voice client instance for the current guild
        voice_client = await self.get_voice_client(interaction)

        # Check if our voice client is connected
        if voice_client is None:
            await ui.ErrMsg.bot_not_in_voice_channel(interaction)
            return

        # Disconnect the voice client
        await interaction.guild.voice_client.disconnect()

        # Display disconnect confirmation
        await ui.SysMsg.disconnected(interaction)


    @app_commands.command(name="show-queue", description="View the current queue")
    async def show_queue(self, interaction: discord.Interaction) -> None:
        ''' Show the current queue '''

        # Get the audio queue for the current guild
        queue = data.guild_data(interaction.guild_id).player.queue

        # Create a string to store the output of our queue
        output = ""

        # Loop over our queue, adding each song into our output string
        for i, song in enumerate(queue):
            output += f"{i+1}. **{song.title}** - *{song.artist}*\n{song.album} ({song.duration_printable})\n\n"

        # Check if our output string is empty & update it accordingly
        if output == "":
            output = "Queue is empty!"

        # Show the user their queue
        await ui.SysMsg.msg(interaction, "Queue", output)


    @app_commands.command(name="clear-queue", description="Clear the queue")
    async def clear_queue(self, interaction: discord.Interaction) -> None:
        '''Clear the queue'''
        queue = data.guild_data(interaction.guild_id).player.queue
        queue.clear()

        # Let the user know that the queue has been cleared
        await ui.SysMsg.queue_cleared(interaction)


    @app_commands.command(name="skip", description="Skip the current track")
    async def skip(self, interaction: discord.Interaction) -> None:
        ''' Skip the current track '''

        # Get the voice client instance
        voice_client = await self.get_voice_client(interaction)

        # Check if the bot is connected to a voice channel
        if voice_client is None:
            await ui.ErrMsg.bot_not_in_voice_channel(interaction)
            return

        # Check if the bot is playing music
        if not voice_client.is_playing():
            await ui.ErrMsg.not_playing(interaction)
            return

        # Stop the current song
        voice_client.stop()

        # Display confirmation message
        await ui.SysMsg.skipping(interaction)


    @app_commands.command(name="autoplay", description="Toggles autoplay")
    @app_commands.describe(mode="Determines the method to use when autoplaying")
    @app_commands.choices(mode=[
        app_commands.Choice(name="None", value="none"),
        app_commands.Choice(name="Random", value="random"),
        app_commands.Choice(name="Similar", value="similar"),
    ])
    async def autoplay(self, interaction: discord.Interaction, mode: app_commands.Choice[str]) -> None:
        ''' Toggles autoplay '''

        # Update the autoplay properties
        match mode.value:
            case "none":
                data.guild_properties(interaction.guild_id).autoplay_mode = data.AutoplayMode.NONE
            case "random":
                data.guild_properties(interaction.guild_id).autoplay_mode = data.AutoplayMode.RANDOM
            case "similar":
                data.guild_properties(interaction.guild_id).autoplay_mode = data.AutoplayMode.SIMILAR

        # Display message indicating new status of autoplay
        if mode.value == "none":
            await ui.SysMsg.msg(interaction, f"Autoplay disabled by {interaction.user.display_name}")
        else:
            await ui.SysMsg.msg(interaction, f"Autoplay enabled by {interaction.user.display_name}", f"Autoplay mode: **{mode.name}**")

        # If the bot is connected to a voice channel and autoplay is enabled, start queue playback
        voice_client = await self.get_voice_client(interaction)
        if voice_client is not None and not voice_client.is_playing():
            player = data.guild_data(interaction.guild_id).player
            await player.play_audio_queue(interaction, voice_client)

async def setup(bot: SubmeisterClient):
    ''' Setup function for the music.py cog '''

    await bot.add_cog(MusicCog(bot))
