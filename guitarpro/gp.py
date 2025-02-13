import zipfile
import xml.etree.ElementTree as ET
import datetime
from .base import Song, Track, Measure, Voice, Beat, Note

__all__ = ['parse_gp']

def parse_gp(file_path):
    """Parse a Guitar Pro 8 (.gp) file."""
    try:
        # Try to open the file as a ZIP archive (GP8 XML format)
        with zipfile.ZipFile(file_path, 'r') as gp_zip:
            candidates = [name for name in gp_zip.namelist() if name.endswith('.gpif')]
            if candidates:
                xml_file = candidates[0]

                with gp_zip.open(xml_file) as gpif_file:
                    # Parse the XML content
                    tree = ET.parse(gpif_file)
                    root = tree.getroot()

                    # If the XML does not have a 'Score' element, use the root directly
                    score_node = root.find('Score')
                    if score_node is None:
                        score_node = root

                    # Create a Song object and extract basic information robustly
                    song = Song()
                    title_node = score_node.find('Title')
                    artist_node = score_node.find('Artist')
                    album_node = score_node.find('Album')

                    # Extract date from the XML; adjust the date format as needed.
                    date_node = score_node.find('Date')
                    if date_node is not None and date_node.text:
                        date_str = date_node.text.strip()
                        try:
                            # Try to convert to a date object (e.g., format "YYYY-MM-DD")
                            song.date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                        except Exception:
                            song.date = date_str
                    else:
                        song.date = "Unknown Date"

                    song.title = title_node.text.strip() if title_node is not None and title_node.text else "Unknown Title"
                    song.artist = artist_node.text.strip() if artist_node is not None and artist_node.text else "Unknown Artist"
                    song.album = album_node.text.strip() if album_node is not None and album_node.text else "Unknown Album"

                    # Extract tempo: try <Tempo> in <Score>; if missing, fallback to MasterTrack Automations
                    tempo_node = score_node.find('Tempo')
                    if tempo_node is not None and tempo_node.text and tempo_node.text.strip():
                        try:
                            song.tempo = int(float(tempo_node.text.strip()))
                        except Exception:
                            song.tempo = 120
                    else:
                        master_track_node = root.find('MasterTrack')
                        if master_track_node is not None:
                            automations_node = master_track_node.find('Automations')
                            if automations_node is not None:
                                tempo_found = False
                                for automation in automations_node.findall('Automation'):
                                    type_node = automation.find('Type')
                                    if type_node is not None and type_node.text and type_node.text.strip().lower() == "tempo":
                                        value_node = automation.find('Value')
                                        if value_node is not None and value_node.text:
                                            # Example value: "87 2" --> take the first number
                                            tempo_value = value_node.text.strip().split()[0]
                                            try:
                                                song.tempo = int(float(tempo_value))
                                            except Exception:
                                                song.tempo = 120
                                            tempo_found = True
                                            break
                                if not tempo_found:
                                    song.tempo = 120
                            else:
                                song.tempo = 120
                        else:
                            song.tempo = 120

                    # Extract track information: try <Tracks> in <Score>; if not present, use MasterTrack/Tracks
                    tracks_node = score_node.find('Tracks')
                    if tracks_node is not None and len(tracks_node):
                        for track_node in tracks_node:
                            track = Track()
                            name_node = track_node.find('Name')
                            track.name = name_node.text.strip() if name_node is not None and name_node.text else "Unnamed Track"
                            strings_node = track_node.find('Strings')
                            if strings_node is not None:
                                track.strings = [int(s.text.strip()) for s in strings_node if s.text and s.text.strip().isdigit()]
                            # If no strings were defined, try to set them based on tuning info.
                            if not track.strings:
                                staves_node = track_node.find('Staves')
                                if staves_node is not None:
                                    staff_node = staves_node.find('Staff')
                                    if staff_node is not None:
                                        props = staff_node.find('Properties')
                                        if props is not None:
                                            tuning_prop = props.find("./Property[@name='Tuning']")
                                            if tuning_prop is not None:
                                                pitches = tuning_prop.find('Pitches')
                                                if pitches is not None and pitches.text:
                                                    pitch_list = [s for s in pitches.text.strip().split() if s.isdigit()]
                                                    try:
                                                        track.strings = list(map(int, pitch_list))
                                                    except Exception:
                                                        track.strings = []
                            song.tracks.append(track)
                    else:
                        master_tracks_node = root.find('MasterTrack/Tracks')
                        if master_tracks_node is not None and master_tracks_node.text:
                            track_indices = master_tracks_node.text.strip().split()
                            for t in track_indices:
                                track = Track()
                                track.name = f"Track {t}"
                                song.tracks.append(track)

                    # Parse measures, voices, beats, and notes
                    measures_node = score_node.find('Measures')
                    if measures_node is not None:
                        for measure_node in measures_node:
                            measure = Measure()
                            track.measures.append(measure)

                            voices_node = measure_node.find('Voices')
                            if voices_node is not None:
                                for voice_node in voices_node:
                                    voice = Voice()
                                    measure.voices.append(voice)

                                    beats_node = voice_node.find('Beats')
                                    if beats_node is not None:
                                        for beat_node in beats_node:
                                            beat = Beat()
                                            duration_node = beat_node.find('Duration')
                                            beat.duration = int(duration_node.text.strip()) if duration_node is not None and duration_node.text and duration_node.text.strip().isdigit() else 0
                                            voice.beats.append(beat)

                                            notes_node = beat_node.find('Notes')
                                            if notes_node is not None:
                                                for note_node in notes_node:
                                                    note = Note()
                                                    string_node = note_node.find('String')
                                                    value_node = note_node.find('Value')
                                                    note.string = int(string_node.text.strip()) if string_node is not None and string_node.text and string_node.text.strip().isdigit() else 0
                                                    note.value = int(value_node.text.strip()) if value_node is not None and value_node.text and value_node.text.strip().isdigit() else 0
                                                    beat.notes.append(note)

                    return song
            else:
                # If no GPIF file is found, assume it's a legacy GP file
                from . import parse as legacy_parse
                return legacy_parse(file_path)
    except zipfile.BadZipFile:
        # Not a ZIP archive: fallback to legacy parser for older GP formats
        from . import parse as legacy_parse
        return legacy_parse(file_path)
    except Exception as e:
        print(f"An error occurred while parsing the .gp file: {e}")
        return None

# Example usage
# file_path = 'guitarpro/Blues.gp'
# song = parse_gp(file_path)

# if song:
#     print(f"Title: {song.title}")
#     print(f"Artist: {song.artist}")
#     print(f"Album: {song.album}")
#     print(f"Tempo: {song.tempo} BPM")
#     print(f"Tracks: {len(song.tracks)}")

#     for track in song.tracks:
#         print(f"\nTrack: {track.name}")
#         print(f"Strings: {track.strings}")
#         print(f"Measures: {len(track.measures)}")