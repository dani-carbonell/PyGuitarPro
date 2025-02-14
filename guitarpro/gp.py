import os
import zipfile
import xml.etree.ElementTree as ET
import datetime
from .base import Song, Track, Measure, Voice, Beat, Note, MeasureHeader, Duration, Tempo, TimeSignature, KeySignature, MeasureClef, NoteType, BendEffect, BendType, BendPoint
import tempfile

__all__ = ['parse_gp']

DEBUG = False

def _debug(msg):
    """Print debug messages if DEBUG is enabled."""
    if DEBUG:
        print(f"[DEBUG] {msg}")

def parse_gp(file_path):
    """Parse a Guitar Pro file."""
    song = read_gpif(file_path)
    
    print(f"Title: {song.title}")
    print(f"Artist: {song.artist}")
    print(f"Album: {song.album}")
    print(f"Tempo: {song.tempo}\n")
    
    for track_index, track in enumerate(song.tracks):
        print(f"Track {track_index + 1}: {track.name}")
        for measure_index, measure in enumerate(track.measures):
            print(f"\nMeasure {measure_index + 1}:")
            print(f"Time Signature: {measure.timeSignature.numerator}/{measure.timeSignature.denominator.value}")
            print(f"Tempo: {measure.tempo}")
            print(f"Number of voices: {len(measure.voices)}")
            
            for voice_index, voice in enumerate(measure.voices):
                print(f"Voice {voice_index + 1}:")
                print(f"Number of beats: {len(voice.beats)}")
                for beat_index, beat in enumerate(voice.beats):
                    print(f"Beat {beat_index + 1} duration: {beat.duration.value}")
                    print(f"Number of notes: {len(beat.notes)}")
                    for note in beat.notes:
                        bend_info = ""
                        if note.effect.bend:
                            bend_info = f" BEND[{note.effect.bend.value/100} steps, points: "
                            for point in note.effect.bend.points:
                                bend_info += f"({point.position}, {point.value/100}), "
                            bend_info = bend_info.rstrip(", ") + "]"
                        
                        print(f"String {note.string}: fret {note.value} [L:{note.leftHandFinger} R:{note.rightHandFinger}]{' PM' if note.effect.palmMute else ''}{bend_info}")
    
    return song

def read_gpif(file_path):
    """Read a Guitar Pro file and return a Song object."""
    # Extract the GPIF file if needed
    if not file_path.endswith('.gpif'):
        gpif_path = extract_gpif(file_path)
    else:
        gpif_path = file_path

    # Parse the GPIF file
    tree = ET.parse(gpif_path)
    root = tree.getroot()

    # Build notes lookup
    notes_by_id = _build_notes_lookup(root)
    print(f"Found {len(notes_by_id)} notes in the GPIF file")

    # Create song object
    song = Song()
    
    # Parse song properties
    title_elem = root.find('.//Title')
    if title_elem is not None:
        song.title = title_elem.text
    
    artist_elem = root.find('.//Artist')
    if artist_elem is not None:
        song.artist = artist_elem.text
    
    album_elem = root.find('.//Album')
    if album_elem is not None:
        song.album = album_elem.text
    
    tempo_elem = root.find('.//Property[@name="Tempo"]/Number')
    if tempo_elem is not None:
        song.tempo = int(tempo_elem.text)

    # Parse tracks
    for track_elem in root.findall('.//Track'):
        track = Track()
        
        # Parse track name
        name_elem = track_elem.find('.//n')
        if name_elem is not None:
            track.name = name_elem.text
        
        # Parse tuning
        strings_elem = track_elem.find('.//Staff/Properties/Property[@name="Tuning"]/Pitches')
        if strings_elem is not None:
            track.strings = len(strings_elem.text.split())
            track.tuning = [int(pitch) for pitch in strings_elem.text.split()]
        
        # Parse measures
        for master_bar_idx, master_bar_elem in enumerate(root.findall('.//MasterBar')):
            # Create measure header
            header = MeasureHeader()
            header.number = master_bar_idx + 1  # 1-based measure numbers
            
            # Parse time signature
            time_elem = master_bar_elem.find('.//Time')
            if time_elem is not None:
                time_parts = time_elem.text.split('/')
                if len(time_parts) == 2:
                    header.timeSignature.numerator = int(time_parts[0])
                    header.timeSignature.denominator = Duration(int(time_parts[1]))
            
            # Parse tempo
            tempo_elem = master_bar_elem.find('.//Property[@name="Tempo"]/Number')
            if tempo_elem is not None:
                header.tempo.value = int(tempo_elem.text)
            
            # Create measure with header
            measure = Measure(header=header)
            
            # Get bar index
            bars_text = master_bar_elem.findtext('Bars', '').strip()
            if bars_text:
                bar_idx = int(bars_text)
                bar_elem = root.find(f'.//Bar[@id="{bar_idx}"]')
                
                if bar_elem is not None:
                    # Parse voices
                    voices_text = bar_elem.findtext('Voices', '').strip()
                    if voices_text:
                        voice_ids = [vid.strip() for vid in voices_text.split()]
                        for voice_id in voice_ids:
                            if voice_id != '-1':
                                voice = Voice()
                                voice_elem = root.find(f'.//Voice[@id="{voice_id}"]')
                                if voice_elem is not None:
                                    beats_text = voice_elem.findtext('Beats', '').strip()
                                    if beats_text:
                                        beat_ids = [bid.strip() for bid in beats_text.split()]
                                        for beat_id in beat_ids:
                                            beat_elem = root.find(f'.//Beat[@id="{beat_id}"]')
                                            if beat_elem is not None:
                                                beat = Beat()
                                                
                                                # Parse duration
                                                rhythm_elem = beat_elem.find('.//Rhythm')
                                                if rhythm_elem is not None:
                                                    duration_elem = rhythm_elem.find('.//Duration')
                                                    if duration_elem is not None:
                                                        beat.duration = Duration(int(duration_elem.text))
                                                
                                                # Parse notes
                                                notes_text = beat_elem.findtext('Notes', '').strip()
                                                if notes_text:
                                                    note_ids = notes_text.split()
                                                    for note_id in note_ids:
                                                        if note_id in notes_by_id:
                                                            note = Note()
                                                            note.string = notes_by_id[note_id]['string']
                                                            note.value = notes_by_id[note_id]['fret']
                                                            note.leftHandFinger = notes_by_id[note_id]['left_finger']
                                                            note.rightHandFinger = notes_by_id[note_id]['right_finger']
                                                            note.effect.palmMute = notes_by_id[note_id]['palm_mute']
                                                            
                                                            # Create bend effect if present
                                                            if notes_by_id[note_id]['bend'] is not None:
                                                                bend = BendEffect()
                                                                bend.type = BendType.bend
                                                                bend_info = notes_by_id[note_id]['bend']
                                                                bend.value = int(bend_info['destination'])
                                                                
                                                                # Add bend points with proper timing
                                                                points = []
                                                                # Origin point
                                                                points.append(BendPoint(
                                                                    int(bend_info['origin_offset'] * 60 / 25),  # Convert offset to position
                                                                    int(bend_info['origin'])
                                                                ))
                                                                
                                                                # Middle points if they exist
                                                                if bend_info['middle'] is not None and bend_info['middle_offset1'] is not None:
                                                                    points.append(BendPoint(
                                                                        int(bend_info['middle_offset1'] * 60 / 25),
                                                                        int(bend_info['middle'])
                                                                    ))
                                                                
                                                                # Destination point
                                                                points.append(BendPoint(
                                                                    int(bend_info['dest_offset'] * 60 / 25),
                                                                    int(bend_info['destination'])
                                                                ))
                                                                
                                                                bend.points = points
                                                                note.effect.bend = bend
                                                            
                                                            beat.notes.append(note)
                                                
                                                voice.beats.append(beat)
                                
                                measure.voices.append(voice)
            
            track.measures.append(measure)
        
        song.tracks.append(track)

    return song

def _build_notes_lookup(root):
    """Build a lookup table of notes by ID."""
    notes_by_id = {}
    for note_elem in root.findall('.//Notes/Note'):
        note_id = note_elem.get('id')
        string_elem = note_elem.find('.//Property[@name="String"]/String')
        fret_elem = note_elem.find('.//Property[@name="Fret"]/Fret')
        left_finger_elem = note_elem.find('LeftFingering')
        right_finger_elem = note_elem.find('RightFingering')
        palm_mute_elem = note_elem.find('.//Property[@name="PalmMuted"]/Enable')
        
        # Get bend information
        bend_elem = note_elem.find('.//Property[@name="Bended"]/Enable')
        bend_origin = note_elem.find('.//Property[@name="BendOriginValue"]/Float')
        bend_middle = note_elem.find('.//Property[@name="BendMiddleValue"]/Float')
        bend_dest = note_elem.find('.//Property[@name="BendDestinationValue"]/Float')
        bend_origin_offset = note_elem.find('.//Property[@name="BendOriginOffset"]/Float')
        bend_middle_offset1 = note_elem.find('.//Property[@name="BendMiddleOffset1"]/Float')
        bend_middle_offset2 = note_elem.find('.//Property[@name="BendMiddleOffset2"]/Float')
        bend_dest_offset = note_elem.find('.//Property[@name="BendDestinationOffset"]/Float')
        
        # Convert letter-based fingering to numbers
        finger_map = {
            'T': 0,  # Thumb
            'I': 1,  # Index
            'M': 2,  # Middle
            'C': 3,  # Ring (Corazon)
            'A': 4,  # Pinky (Anular)
            None: -1  # No fingering
        }
        
        if string_elem is not None and fret_elem is not None:
            bend_info = None
            if bend_elem is not None and bend_origin is not None and bend_dest is not None:
                bend_info = {
                    'origin': float(bend_origin.text),
                    'middle': float(bend_middle.text) if bend_middle is not None else None,
                    'destination': float(bend_dest.text),
                    'origin_offset': float(bend_origin_offset.text) if bend_origin_offset is not None else 0.0,
                    'middle_offset1': float(bend_middle_offset1.text) if bend_middle_offset1 is not None else None,
                    'middle_offset2': float(bend_middle_offset2.text) if bend_middle_offset2 is not None else None,
                    'dest_offset': float(bend_dest_offset.text) if bend_dest_offset is not None else 25.0
                }
            
            notes_by_id[note_id] = {
                'string': int(string_elem.text),  # 1-based
                'fret': int(fret_elem.text),
                'left_finger': finger_map.get(left_finger_elem.text if left_finger_elem is not None else None, -1),
                'right_finger': finger_map.get(right_finger_elem.text if right_finger_elem is not None else None, -1),
                'palm_mute': palm_mute_elem is not None,
                'bend': bend_info
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

def extract_gpif(file_path):
    """Extract the GPIF file from a Guitar Pro file."""
    try:
        # Check if it's a directory or a file
        if os.path.isdir(file_path):
            gpif_path = os.path.join(file_path, 'Content', 'score.gpif')
            if os.path.exists(gpif_path):
                return gpif_path
        else:
            # Try to open it as a zip file
            try:
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    # Extract to a temporary directory
                    temp_dir = os.path.join(os.path.dirname(file_path), os.path.splitext(os.path.basename(file_path))[0])
                    if not os.path.exists(temp_dir):
                        os.makedirs(temp_dir)
                    zip_ref.extractall(temp_dir)
                    return os.path.join(temp_dir, 'Content', 'score.gpif')
            except zipfile.BadZipFile:
                # If not a zip file, try the old directory approach
                base_path = os.path.dirname(file_path)
                file_name = os.path.basename(file_path)
                dir_name = os.path.splitext(file_name)[0]
                gpif_path = os.path.join(base_path, dir_name, 'Content', 'score.gpif')
                if os.path.exists(gpif_path):
                    return gpif_path
        
        raise FileNotFoundError(f"Could not find GPIF file for {file_path}")
    except Exception as e:
        raise Exception(f"Error extracting GPIF file: {e}")

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