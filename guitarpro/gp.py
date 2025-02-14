import zipfile
import xml.etree.ElementTree as ET
import datetime
from .base import Song, Track, Measure, Voice, Beat, Note, MeasureHeader, Duration, Tempo, TimeSignature, KeySignature, MeasureClef, NoteType
import os

__all__ = ['parse_gp']

DEBUG = False

def _debug(msg):
    """Print debug messages if DEBUG is enabled."""
    if DEBUG:
        print(f"[DEBUG] {msg}")

def parse_gp(file_path):
    """Parse a Guitar Pro 8 (.gp) file."""
    try:
        # Find the .gpif file
        if file_path.endswith('.gp'):
            # Check if it's a directory or a file
            if os.path.isdir(file_path):
                gpif_path = os.path.join(file_path, 'Content', 'score.gpif')
            else:
                # Assume it's a file in the same directory
                base_path = os.path.dirname(file_path)
                file_name = os.path.basename(file_path)
                dir_name = os.path.splitext(file_name)[0]
                gpif_path = os.path.join(base_path, dir_name, 'Content', 'score.gpif')
        else:
            gpif_path = file_path
        _debug(f"Trying to parse GPIF file: {gpif_path}")

        # Parse the GPIF file
        tree = ET.parse(gpif_path)
        root = tree.getroot()
        _debug("Successfully parsed XML")

        # Create a song
        song = Song()

        # Parse song info
        title = root.find('.//Title')
        if title is not None:
            song.title = title.text
            _debug(f"Found title: {song.title}")

        artist = root.find('.//Artist')
        if artist is not None:
            song.artist = artist.text
            _debug(f"Found artist: {song.artist}")

        album = root.find('.//Album')
        if album is not None:
            song.album = album.text
            _debug(f"Found album: {song.album}")

        tempo = root.find('.//Tempo')
        if tempo is not None:
            song.tempo = int(tempo.text)
            _debug(f"Found tempo: {song.tempo}")

        # Build lookup tables
        notes_by_id = _build_notes_lookup(root)
        _debug(f"Found {len(notes_by_id)} notes")
        rhythms_by_id = _build_rhythms_lookup(root)
        _debug(f"Found {len(rhythms_by_id)} rhythms")

        # Parse tracks
        tracks = root.findall('.//Track')
        _debug(f"Found {len(tracks)} tracks")
        for track_idx, track_elem in enumerate(tracks):
            track = Track()
            
            # Parse track name
            name = track_elem.find('Name')
            if name is not None:
                track.name = name.text
                _debug(f"Found track: {track.name}")

            # Parse tuning
            strings_elem = track_elem.find('.//Property[@name="NumberOfStrings"]/Number')
            if strings_elem is not None:
                track.strings = int(strings_elem.text)
                _debug(f"Track {track.name} has {track.strings} strings")
                
            tuning_elem = track_elem.find('.//Property[@name="Tuning"]/Pitches')
            if tuning_elem is not None:
                track.tuning = [int(p.text) for p in tuning_elem.findall('Integer')]
                _debug(f"Track {track.name} tuning: {track.tuning}")

            # Find bars for this track
            master_bars = root.find('.//MasterBars')
            if master_bars is not None:
                master_bar_refs = master_bars.findall('MasterBar')
                for master_bar_idx, master_bar in enumerate(master_bar_refs):
                    # Create a measure
                    measure = Measure(header=None)  # We'll set the header later
                    
                    # Get the bar references for this track
                    bars_text = master_bar.findtext('Bars', '').strip()
                    if bars_text:
                        bar_indices = [int(idx.strip()) for idx in bars_text.split()]
                        if track_idx < len(bar_indices):
                            bar_idx = bar_indices[track_idx]
                            bar_elem = root.find(f'.//Bar[@id="{bar_idx}"]')
                            
                            if bar_elem is not None:
                                # Parse voices in the bar
                                voices_text = bar_elem.findtext('Voices', '').strip()
                                if voices_text:
                                    voice_ids = [vid.strip() for vid in voices_text.split()]
                                    for voice_id in voice_ids:
                                        voice = Voice()
                                        if voice_id != '-1':
                                            voice_elem = root.find(f'.//Voice[@id="{voice_id}"]')
                                            if voice_elem is not None:
                                                beats_text = voice_elem.findtext('Beats', '').strip()
                                                if beats_text:
                                                    beat_ids = [bid.strip() for bid in beats_text.split()]
                                                    for beat_id in beat_ids:
                                                        beat_elem = root.find(f'.//Beat[@id="{beat_id}"]')
                                                        if beat_elem is not None:
                                                            beat = Beat()
                                                            
                                                            # Get rhythm/duration
                                                            rhythm_ref = beat_elem.find('Rhythm')
                                                            if rhythm_ref is not None:
                                                                rhythm_id = rhythm_ref.get('ref')
                                                                if rhythm_id in rhythms_by_id:
                                                                    beat.duration = rhythms_by_id[rhythm_id]
                                                            
                                                            # Get notes
                                                            notes_text = beat_elem.findtext('Notes', '').strip()
                                                            if notes_text:
                                                                note_ids = notes_text.split()
                                                                for note_id in note_ids:
                                                                    if note_id in notes_by_id:
                                                                        note = Note()
                                                                        note.string = notes_by_id[note_id]['string']
                                                                        note.value = notes_by_id[note_id]['fret']
                                                                        beat.notes.append(note)
                                                            
                                                            voice.beats.append(beat)
                                        measure.voices.append(voice)
                    
                    track.measures.append(measure)
            
            song.tracks.append(track)

        return song

    except Exception as e:
        _debug(f"Error parsing file: {e}")
        return None

def _build_notes_lookup(root):
    """Build a lookup table of notes by ID."""
    notes_by_id = {}
    for note_elem in root.findall('.//Notes/Note'):
        note_id = note_elem.get('id')
        string_elem = note_elem.find('.//Property[@name="String"]/String')
        fret_elem = note_elem.find('.//Property[@name="Fret"]/Fret')
        if string_elem is not None and fret_elem is not None:
            notes_by_id[note_id] = {
                'string': int(string_elem.text),  # 1-based
                'fret': int(fret_elem.text)
            }
    return notes_by_id

def _build_rhythms_lookup(root):
    """Build a lookup table of rhythms by ID."""
    rhythms_by_id = {}
    for rhythm_elem in root.findall('.//Rhythms/Rhythm'):
        rhythm_id = rhythm_elem.get('id')
        note_value = rhythm_elem.find('NoteValue').text
        dots = rhythm_elem.find('AugmentationDot')
        dot_count = int(dots.get('count')) if dots is not None else 0
        
        # Convert note value to duration
        duration_map = {
            'Whole': 1,
            'Half': 2,
            'Quarter': 4,
            'Eighth': 8,
            '16th': 16,
            '32nd': 32,
            '64th': 64
        }
        duration_value = duration_map.get(note_value, 4)  # Default to quarter note
        
        # Apply augmentation dots
        if dot_count > 0:
            duration_multiplier = 1.0
            for i in range(dot_count):
                duration_multiplier += 1.0 / (2 ** (i + 1))
            duration_value = int(duration_value * duration_multiplier)
        
        # Create a Duration object
        duration = Duration()
        duration.value = duration_value
        rhythms_by_id[rhythm_id] = duration
    return rhythms_by_id

# Example usage commented out to avoid circular imports
# file_path = 'guitarpro/Blues.gp'
# song = parse_gp(file_path)
#
# if song:
#     print(f"Title: {song.title}")
#     print(f"Artist: {song.artist}")
#     print(f"Album: {song.album}")
#     print(f"Tempo: {song.tempo} BPM")
#     print(f"Tracks: {len(song.tracks)}")
#
#     for track in song.tracks:
#         print(f"\nTrack: {track.name}")
#         print(f"Strings: {track.strings}")
#         print(f"Measures: {len(track.measures)}")