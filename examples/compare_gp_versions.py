from guitarpro.gp import parse_gp
from guitarpro import parse
from guitarpro.base import NoteType
import os

def get_note_duration_ms(beat, tempo):
    """Calculate note duration in milliseconds."""
    if not beat.duration:
        return 0
    
    # Calculate quarter note duration in ms based on tempo
    quarter_note_ms = (60 / tempo) * 1000
    
    # Calculate this beat's duration based on its relationship to quarter note
    # For example, if duration.value is 8, it's an eighth note (half of quarter note)
    beat_duration_ms = quarter_note_ms * (4 / beat.duration.value)
    
    # Apply dot multiplier if present
    if beat.duration.isDotted:
        beat_duration_ms *= 1.5
    
    # Apply double dot multiplier if present
    if beat.duration.isDoubleDotted:
        beat_duration_ms *= 1.75
    
    return beat_duration_ms

def is_dead_note(note):
    """Check if a note is a dead note in a format-independent way."""
    if hasattr(note, 'isDead'):
        return note.isDead
    elif hasattr(note, 'type'):
        return note.type == NoteType.dead
    return False

def print_measure_info(measure, measure_type="GP"):
    """Print detailed information about a measure."""
    print(f"\n{measure_type} Measure {measure.number}:")
    print(f"Time Signature: {measure.timeSignature.numerator}/{measure.timeSignature.denominator.value}")
    print(f"Tempo: {measure.tempo.value if measure.tempo else 'Unknown'} BPM")
    
    total_measure_duration = 0
    total_notes = 0
    grace_notes = 0
    
    for voice_idx, voice in enumerate(measure.voices):
        if not voice.beats:
            continue
            
        print(f"\nVoice {voice_idx + 1}:")
        for beat_idx, beat in enumerate(voice.beats):
            if not beat.notes:
                continue
                
            duration_ms = get_note_duration_ms(beat, measure.tempo.value if measure.tempo else 120)
            total_measure_duration += duration_ms
            
            # Check if this is a grace note beat
            is_grace = hasattr(beat, 'isGrace') and beat.isGrace
            
            print(f"\nBeat {beat_idx + 1}:")
            print(f"Duration: 1/{beat.duration.value} note ({duration_ms:.2f}ms)")
            if is_grace:
                print("*** GRACE NOTE BEAT ***")
                grace_notes += len(beat.notes)
            
            for note in beat.notes:
                total_notes += 1
                effects = []
                if note.effect.palmMute:
                    effects.append("PM")
                if is_dead_note(note):
                    effects.append("X")
                if note.effect.bend:
                    effects.append(f"Bend {note.effect.bend.value/100:.1f}")
                
                effect_str = " ".join(effects)
                print(f"String {note.string + 1}: fret {note.value} " + 
                      (f"[{effect_str}] " if effect_str else "") +
                      ("(Grace Note)" if is_grace else ""))
    
    print(f"\nTotal measure duration: {total_measure_duration:.2f}ms")
    print(f"Total notes: {total_notes} (Regular: {total_notes - grace_notes}, Grace: {grace_notes})")
    return total_measure_duration

def get_track_tuning(track):
    """Get track tuning in a format-independent way."""
    if hasattr(track, 'tuning'):
        return track.tuning
    elif hasattr(track, 'strings'):
        return [string.value for string in track.strings]
    return None

def compare_files(gp_path, gp5_path):
    """Compare a GP file with a GP5 file."""
    print(f"Comparing {os.path.basename(gp_path)} with {os.path.basename(gp5_path)}")
    
    # Parse both files
    gp_song = parse_gp(gp_path)
    gp5_song = parse(gp5_path)
    
    print("\n=== Song Information ===")
    print(f"GP Title: {gp_song.title}")
    print(f"GP5 Title: {gp5_song.title}")
    
    # Compare tracks
    print(f"\nGP Tracks: {len(gp_song.tracks)}")
    print(f"GP5 Tracks: {len(gp5_song.tracks)}")
    
    # Compare first track in detail
    if gp_song.tracks and gp5_song.tracks:
        gp_track = gp_song.tracks[0]
        gp5_track = gp5_song.tracks[0]
        
        print(f"\n=== Comparing Track 1 ===")
        print(f"GP Track: {gp_track.name}")
        print(f"GP5 Track: {gp5_track.name}")
        
        # Compare tuning
        gp_tuning = get_track_tuning(gp_track)
        gp5_tuning = get_track_tuning(gp5_track)
        print(f"\nGP Tuning: {gp_tuning}")
        print(f"GP5 Tuning: {gp5_tuning}")
        
        # Focus on first measure only
        if gp_track.measures and gp5_track.measures:
            print("\n=== Detailed First Measure Comparison ===")
            gp_duration = print_measure_info(gp_track.measures[0], "GP")
            gp5_duration = print_measure_info(gp5_track.measures[0], "GP5")
            
            duration_diff = abs(gp_duration - gp5_duration)
            if duration_diff > 1:  # Allow 1ms tolerance
                print(f"\n⚠️ Duration mismatch: {duration_diff:.2f}ms difference")
            else:
                print("\n✓ Durations match")

def main():
    # Get the path to the test files
    base_dir = os.path.dirname(os.path.dirname(__file__))
    gp_path = os.path.join(base_dir, "tests", "Effects.gp")
    gp5_path = os.path.join(base_dir, "tests", "Effects.gp5")
    
    if not os.path.exists(gp_path):
        print(f"Error: {gp_path} not found")
        return
    if not os.path.exists(gp5_path):
        print(f"Error: {gp5_path} not found")
        return
    
    compare_files(gp_path, gp5_path)

if __name__ == "__main__":
    main() 