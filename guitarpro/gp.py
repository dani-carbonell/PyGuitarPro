import os
import zipfile
import xml.etree.ElementTree as ET
import datetime
import logging
from .base import Song, Track, Measure, Voice, Beat, Note, MeasureHeader, Duration, Tempo, TimeSignature, KeySignature, MeasureClef, NoteType, BendEffect, BendType, BendPoint
import tempfile

# Set up logging
logger = logging.getLogger(__name__)

# Set up debug handling
DEBUG = os.environ.get('GP_DEBUG', '0').lower() in ('1', 'true', 'yes', 'on')
if DEBUG:
    logger.setLevel(logging.DEBUG)
    # Add a console handler if none exists
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logger.addHandler(handler)

__all__ = ['parse_gp']

def _debug(msg):
    """Print debug messages if DEBUG is enabled."""
    if DEBUG:
        logger.debug(msg)

def parse_gp(file_path):
    """Parse a Guitar Pro file."""
    song = read_gpif(file_path)
    
    logger.info(f"Title: {song.title}")
    logger.info(f"Artist: {song.artist}")
    logger.info(f"Album: {song.album}")
    logger.info(f"Tempo: {song.tempo}")
    
    for track_index, track in enumerate(song.tracks):
        logger.info(f"Track {track_index + 1}: {track.name}")
        for measure_index, measure in enumerate(track.measures):
            logger.info(f"Measure {measure_index + 1}:")
            logger.info(f"Time Signature: {measure.timeSignature.numerator}/{measure.timeSignature.denominator.value}")
            logger.info(f"Tempo: {measure.tempo}")
            logger.info(f"Number of voices: {len(measure.voices)}")
            
            for voice_index, voice in enumerate(measure.voices):
                logger.info(f"Voice {voice_index + 1}:")
                logger.info(f"Number of beats: {len(voice.beats)}")
                for beat_index, beat in enumerate(voice.beats):
                    logger.info(f"Beat {beat_index + 1} duration: {beat.duration.value}")
                    logger.info(f"Number of notes: {len(beat.notes)}")
                    for note in beat.notes:
                        bend_info = ""
                        if note.effect.bend:
                            bend_info = f" BEND[{note.effect.bend.value/100} steps, points: "
                            for point in note.effect.bend.points:
                                bend_info += f"({point.position}, {point.value/100}), "
                            bend_info = bend_info.rstrip(", ") + "]"
                        
                        logger.info(f"String {note.string}: fret {note.value} [L:{note.leftHandFinger} R:{note.rightHandFinger}]{' PM' if note.effect.palmMute else ''}{bend_info}")
    
    return song

def read_gpif(file_path):
    """Read a Guitar Pro file and return a Song object."""
    # Extract the GPIF file if needed
    if not file_path.endswith('.gpif'):
        gpif_path = extract_gpif(file_path)
    else:
        gpif_path = file_path

    logger.debug(f"Reading GPIF file: {gpif_path}")

    # Parse the GPIF file
    try:
        tree = ET.parse(gpif_path)
        root = tree.getroot()
    except ET.ParseError as e:
        logger.error(f"Failed to parse GPIF XML: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error reading GPIF file: {str(e)}")
        raise

    # Build notes lookup
    notes_by_id = _build_notes_lookup(root)
    logger.info(f"Found {len(notes_by_id)} notes in the GPIF file")

    # Parse rhythms
    rhythms = {}
    rhythms_by_id = {}
    rhythm_refs = {}  # Store rhythm references
    
    # First pass - collect all rhythm definitions
    for rhythm in root.findall('.//Rhythm'):
        rhythm_id = rhythm.get('id')
        if rhythm_id:
            duration = Duration()
            
            # Get duration value
            duration_elem = rhythm.find('.//Duration')
            if duration_elem is not None:
                duration.value = int(duration_elem.text)
            
            # Get dots
            dots_elem = rhythm.find('.//AugmentationDot')
            if dots_elem is not None and dots_elem.text:
                dot_count = int(dots_elem.text)
                duration.isDotted = dot_count == 1
                duration.isDoubleDotted = dot_count == 2
            
            # Get tuplet
            tuplet_elem = rhythm.find('.//PrimaryTuplet')
            if tuplet_elem is not None:
                numerator = int(tuplet_elem.find('Numerator').text)
                denominator = int(tuplet_elem.find('Denominator').text)
                duration.tuplet.enters = numerator
                duration.tuplet.times = denominator
            
            rhythms[rhythm_id] = duration
            rhythms_by_id[rhythm_id] = duration
            
            # Store reference if it exists
            ref_elem = rhythm.find('.//Reference')
            if ref_elem is not None and ref_elem.text:
                rhythm_refs[rhythm_id] = ref_elem.text
    
    # Second pass - resolve references
    for rhythm_id, ref_id in rhythm_refs.items():
        if ref_id in rhythms:
            rhythms[rhythm_id] = rhythms[ref_id]
            rhythms_by_id[rhythm_id] = rhythms[ref_id]
            
    if DEBUG:
        logger.debug("\nRhythm definitions:")
        for rid, duration in rhythms.items():
            dots = "double" if duration.isDoubleDotted else ("single" if duration.isDotted else "none")
            logger.debug(f"  {rid}: value={duration.value}, dots={dots}, tuplet={duration.tuplet.enters}/{duration.tuplet.times}")
        logger.debug("\nRhythm references:")
        for rid, ref in rhythm_refs.items():
            logger.debug(f"  {rid} -> {ref}")

    # Build rhythms lookup
    rhythms_by_id = _build_rhythms_lookup(root)

    # Create song object
    song = Song()
    
    # Parse song properties
    title_elem = root.find('.//Title')
    if title_elem is not None:
        song.title = title_elem.text if title_elem.text else ""
    
    artist_elem = root.find('.//Artist')
    if artist_elem is not None:
        song.artist = artist_elem.text if artist_elem.text else ""
    
    album_elem = root.find('.//Album')
    if album_elem is not None:
        song.album = album_elem.text if album_elem.text else ""
    
    tempo_elem = root.find('.//Property[@name="Tempo"]/Number')
    if tempo_elem is not None:
        try:
            song.tempo = int(tempo_elem.text)
        except (ValueError, TypeError):
            logger.warning("Invalid tempo value found")
            song.tempo = 120  # Default tempo

    # Parse tracks
    track_count = 0
    for track_elem in root.findall('.//Track'):
        track = Track()
        track_count += 1
        logger.debug(f"Processing track {track_count}")
        
        # Parse track name
        name_elem = track_elem.find('.//Name')  # Changed from './/n' to './/Name'
        if name_elem is not None:
            track.name = name_elem.text if name_elem.text else f"Track {track_count}"
        else:
            # Try to get the track name from the instrument
            instr_elem = track_elem.find('.//Properties/Property[@name="Name"]/String')
            if instr_elem is not None and instr_elem.text:
                track.name = instr_elem.text
            else:
                track.name = f"Track {track_count}"
        
        # Parse tuning
        strings_elem = track_elem.find('.//Staff/Properties/Property[@name="Tuning"]/Pitches')
        if strings_elem is not None and strings_elem.text:
            pitches = strings_elem.text.split()
            track.strings = len(pitches)
            # Reverse tuning to match GP5 format
            track.tuning = [int(pitch) for pitch in reversed(pitches)]
            logger.debug(f"Track tuning: {track.tuning}")
        
        # Parse measures
        measures = []
        for master_bar_elem in root.findall('.//MasterBar'):
            # Create measure header
            header = MeasureHeader()
            header.number = len(measures) + 1
            
            # Parse time signature
            time_elem = master_bar_elem.find('.//Time')
            if time_elem is not None and time_elem.text:
                time_parts = time_elem.text.split('/')
                if len(time_parts) == 2:
                    try:
                        header.timeSignature.numerator = int(time_parts[0])
                        header.timeSignature.denominator.value = int(time_parts[1])
                    except ValueError:
                        logger.warning(f"Invalid time signature: {time_elem.text}")
            
            # Parse tempo
            tempo_elem = master_bar_elem.find('.//Property[@name="Tempo"]/Number')
            if tempo_elem is not None and tempo_elem.text:
                try:
                    header.tempo.value = int(tempo_elem.text)
                except ValueError:
                    logger.warning(f"Invalid tempo value: {tempo_elem.text}")
            
            # Create measure with header
            measure = Measure(header=header)
            
            # Get bar index
            bars_text = master_bar_elem.findtext('Bars', '').strip()
            if bars_text:
                try:
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
                                            
                                            # Calculate total beats in measure
                                            total_beats = header.timeSignature.numerator
                                            beats_per_quarter = 4 / header.timeSignature.denominator.value
                                            max_quarter_notes = total_beats / beats_per_quarter
                                            
                                            # Create voice and initialize variables
                                            voice = Voice()
                                            last_regular_beat = None  # For handling grace notes
                                            current_quarter_notes = 0
                                            processed_beats = 0
                                            
                                            if DEBUG:
                                                logger.debug(f"Processing measure {header.number} with {len(beat_ids)} beats")
                                            
                                            for beat_id in beat_ids:
                                                # Stop if we've reached the measure length
                                                if current_quarter_notes >= max_quarter_notes:
                                                    if DEBUG:
                                                        logger.debug(f"Reached measure length at beat {beat_id}")
                                                    break
                                                
                                                beat_elem = root.find(f'.//Beat[@id="{beat_id}"]')
                                                if beat_elem is not None:
                                                    # Check if this is a grace note
                                                    is_grace = False
                                                    grace_elem = beat_elem.find('GraceNotes')
                                                    if grace_elem is not None and grace_elem.text == 'BeforeBeat':
                                                        is_grace = True
                                                    
                                                    if DEBUG:
                                                        logger.debug(f"\nProcessing beat {beat_id}:")
                                                        logger.debug(f"  Is grace note: {is_grace}")
                                                        logger.debug("  Searching for notes in beat:")
                                                        for child in beat_elem:
                                                            logger.debug(f"    {child.tag}: {child.text}")
                                                    
                                                    if is_grace and last_regular_beat is not None:
                                                        # For grace notes, attach to the previous beat
                                                        notes_elem = beat_elem.find('Notes')
                                                        if notes_elem is not None and notes_elem.text:
                                                            note_ids = notes_elem.text.split()
                                                            for note_id in note_ids:
                                                                if DEBUG:
                                                                    logger.debug(f"  Found grace note ID: {note_id}")
                                                                if note_id in notes_by_id:
                                                                    note_data = notes_by_id[note_id]
                                                                    note = Note()
                                                                    note.string = note_data['string']
                                                                    note.value = note_data['fret']
                                                                    note.leftHandFinger = note_data['left_finger']
                                                                    note.rightHandFinger = note_data['right_finger']
                                                                    note.effect.palmMute = note_data['palm_mute']
                                                                    note.isDead = note_data['dead']
                                                                    
                                                                    # Create bend effect if present
                                                                    if note_data['bend'] is not None:
                                                                        bend = BendEffect()
                                                                        bend.type = BendType.bend
                                                                        bend.value = int(note_data['bend']['destination'])
                                                                        
                                                                        # Create bend points
                                                                        points = []
                                                                        
                                                                        # Origin point
                                                                        points.append(BendPoint(
                                                                            int(note_data['bend']['origin_offset'] * 60 / 25),  # Convert offset to position
                                                                            int(note_data['bend']['origin'])
                                                                        ))
                                                                        
                                                                        # Middle points if they exist
                                                                        if note_data['bend']['middle'] is not None and note_data['bend']['middle_offset1'] is not None:
                                                                            points.append(BendPoint(
                                                                                int(note_data['bend']['middle_offset1'] * 60 / 25),
                                                                                int(note_data['bend']['middle'])
                                                                            ))
                                                                        
                                                                        # Destination point
                                                                        points.append(BendPoint(
                                                                            int(note_data['bend']['dest_offset'] * 60 / 25),
                                                                            int(note_data['bend']['destination'])
                                                                        ))
                                                                        
                                                                        bend.points = points
                                                                        note.effect.bend = bend
                                                                    
                                                                    last_regular_beat.notes.append(note)
                                                                    if DEBUG:
                                                                        logger.debug(f"  Attached grace note: string {note.string}, fret {note.value}")
                                                                else:
                                                                    if DEBUG:
                                                                        logger.debug(f"  Grace note {note_id} not found in notes_by_id")
                                                        continue  # Skip further processing of this beat
                                                    
                                                    beat = Beat()
                                                    
                                                    # Parse duration
                                                    rhythm_elem = beat_elem.find('.//Rhythm')
                                                    if rhythm_elem is not None and rhythm_elem.text in rhythms_by_id:
                                                        beat.duration = rhythms_by_id[rhythm_elem.text]
                                                    
                                                    # Parse notes for this beat
                                                    notes_elem = beat_elem.find('Notes')
                                                    if notes_elem is not None and notes_elem.text:
                                                        note_ids = notes_elem.text.split()
                                                        for note_id in note_ids:
                                                            if DEBUG:
                                                                logger.debug(f"  Found note ID: {note_id}")
                                                            if note_id in notes_by_id:
                                                                note_data = notes_by_id[note_id]
                                                                note = Note()
                                                                note.string = note_data['string']
                                                                note.value = note_data['fret']
                                                                note.leftHandFinger = note_data['left_finger']
                                                                note.rightHandFinger = note_data['right_finger']
                                                                note.effect.palmMute = note_data['palm_mute']
                                                                note.isDead = note_data['dead']
                                                                
                                                                # Create bend effect if present
                                                                if note_data['bend'] is not None:
                                                                    bend = BendEffect()
                                                                    bend.type = BendType.bend
                                                                    bend.value = int(note_data['bend']['destination'])
                                                                    
                                                                    # Create bend points
                                                                    points = []
                                                                    
                                                                    # Origin point
                                                                    points.append(BendPoint(
                                                                        int(note_data['bend']['origin_offset'] * 60 / 25),  # Convert offset to position
                                                                        int(note_data['bend']['origin'])
                                                                    ))
                                                                    
                                                                    # Middle points if they exist
                                                                    if note_data['bend']['middle'] is not None and note_data['bend']['middle_offset1'] is not None:
                                                                        points.append(BendPoint(
                                                                            int(note_data['bend']['middle_offset1'] * 60 / 25),
                                                                            int(note_data['bend']['middle'])
                                                                        ))
                                                                    
                                                                    # Destination point
                                                                    points.append(BendPoint(
                                                                        int(note_data['bend']['dest_offset'] * 60 / 25),
                                                                        int(note_data['bend']['destination'])
                                                                    ))
                                                                    
                                                                    bend.points = points
                                                                    note.effect.bend = bend
                                                                
                                                                beat.notes.append(note)
                                                                if DEBUG:
                                                                    logger.debug(f"  Added note: string {note.string}, fret {note.value}")
                                                            else:
                                                                if DEBUG:
                                                                    logger.debug(f"  Note {note_id} not found in notes_by_id")
                                                    
                                                    voice.beats.append(beat)
                                                    last_regular_beat = beat  # Store for potential future grace notes
                                                    current_quarter_notes += 4 / beat.duration.value
                                                    processed_beats += 1
                                                    
                                                    if DEBUG:
                                                        logger.debug(f"Added beat with {len(beat.notes)} notes, total beats: {processed_beats}, total quarters: {current_quarter_notes}")
                                                else:
                                                    if DEBUG:
                                                        logger.debug(f"No rhythm found for beat {beat_id}")
                                            
                                    # Add the voice to the measure
                                    measure.voices.append(voice)
                except ValueError as e:
                    logger.warning(f"Invalid bar index: {bars_text} - {str(e)}")
            
            # Add the measure to the track's measures
            track.measures.append(measure)
            measures.append(measure)
            logger.debug(f"Added measure {len(measures)} to track")
        
        # Add the track to the song
        song.tracks.append(track)
        logger.debug(f"Added track with {len(track.measures)} measures")

    return song

def _build_notes_lookup(root):
    """Build a lookup table of notes by ID."""
    notes_by_id = {}
    if DEBUG:
        logger.debug("\nBuilding notes lookup table:")
    for note_elem in root.findall('.//Notes/Note'):
        note_id = note_elem.get('id')
        if DEBUG:
            logger.debug(f"\nProcessing note element {note_id}:")
            for child in note_elem:
                logger.debug(f"  {child.tag}: {child.text}")
        
        string_elem = note_elem.find('.//Property[@name="String"]/String')
        fret_elem = note_elem.find('.//Property[@name="Fret"]/Fret')
        left_finger_elem = note_elem.find('LeftFingering')
        right_finger_elem = note_elem.find('RightFingering')
        palm_mute_elem = note_elem.find('.//Property[@name="PalmMuted"]/Enable')
        dead_note_elem = note_elem.find('.//Property[@name="Dead"]/Enable')
        muted_note_elem = note_elem.find('.//Property[@name="Muted"]/Enable')
        
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
            if DEBUG:
                logger.debug(f"  Found string: {string_elem.text}, fret: {fret_elem.text}")
            
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
            
            # Convert to GP5-style string numbering (7-based)
            string_number = int(string_elem.text)  # 0-based in GPIF
            string_number = 5 - string_number  # Convert to GP5 style (7-based)
            
            notes_by_id[note_id] = {
                'string': string_number + 1,  # Add 1 to make it 1-based
                'fret': int(fret_elem.text),
                'left_finger': finger_map.get(left_finger_elem.text if left_finger_elem is not None else None, -1),
                'right_finger': finger_map.get(right_finger_elem.text if right_finger_elem is not None else None, -1),
                'palm_mute': palm_mute_elem is not None,
                'dead': dead_note_elem is not None or muted_note_elem is not None,
                'bend': bend_info
            }
            if DEBUG:
                logger.debug(f"  Added note {note_id} to lookup table")
    return notes_by_id

def _build_rhythms_lookup(root):
    """Build a lookup table of rhythms by ID."""
    rhythms_by_id = {}
    if DEBUG:
        logger.debug("\nBuilding rhythm lookup table:")
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
        duration.isDotted = dot_count == 1
        duration.isDoubleDotted = dot_count == 2
        rhythms_by_id[rhythm_id] = duration
        
        if DEBUG:
            logger.debug(f"Rhythm {rhythm_id}: {note_value} (value: {duration_value}, dots: {dot_count})")
    
    if DEBUG:
        logger.debug(f"Total rhythms: {len(rhythms_by_id)}\n")
    return rhythms_by_id

def extract_gpif(file_path):
    """Extract the GPIF file from a Guitar Pro file."""
    try:
        logger.debug(f"Attempting to extract GPIF from: {file_path}")
        # Check if it's a directory or a file
        if os.path.isdir(file_path):
            gpif_path = os.path.join(file_path, 'Content', 'score.gpif')
            if os.path.exists(gpif_path):
                logger.debug(f"Found GPIF in directory: {gpif_path}")
                return gpif_path
        else:
            # Try to open it as a zip file
            try:
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    # Create a unique temporary directory
                    temp_dir = tempfile.mkdtemp(prefix='gp_')
                    logger.debug(f"Created temp directory: {temp_dir}")
                    zip_ref.extractall(temp_dir)
                    gpif_path = os.path.join(temp_dir, 'Content', 'score.gpif')
                    if os.path.exists(gpif_path):
                        logger.debug(f"Extracted GPIF to: {gpif_path}")
                        return gpif_path
                    else:
                        logger.error(f"No score.gpif found in extracted files at {gpif_path}")
                        # List contents of the zip for debugging
                        logger.debug("Zip contents:")
                        for name in zip_ref.namelist():
                            logger.debug(f"  {name}")
            except zipfile.BadZipFile:
                logger.debug("Not a valid zip file, trying directory approach")
                # If not a zip file, try the old directory approach
                base_path = os.path.dirname(file_path)
                file_name = os.path.basename(file_path)
                dir_name = os.path.splitext(file_name)[0]
                gpif_path = os.path.join(base_path, dir_name, 'Content', 'score.gpif')
                if os.path.exists(gpif_path):
                    logger.debug(f"Found GPIF using directory approach: {gpif_path}")
                    return gpif_path
        
        raise FileNotFoundError(f"Could not find GPIF file for {file_path}")
    except Exception as e:
        logger.error(f"Error extracting GPIF file: {str(e)}")
        raise

