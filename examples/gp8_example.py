from guitarpro.gp import parse_gp
import os

def _get_finger_name(finger_value):
    """Convert finger value to human-readable name."""
    finger_map = {
        -1: "x",  # no finger specified
        0: "T",   # thumb
        1: "1",   # index
        2: "2",   # middle
        3: "3",   # ring
        4: "4"    # pinky
    }
    return finger_map.get(finger_value, "?")

def main():
    # Use the Funky.gp file which is GP8 format
    file_path = os.path.join(os.path.dirname(__file__), "..", "tests", "fin1.gp")
    print(f"Trying to open file: {file_path}")

    song = parse_gp(file_path)
    
    if song:
        print("=== Song Information ===")
        print(f"Title: {song.title}")
        print(f"Artist: {song.artist}")
        print(f"Album: {song.album}")
        print(f"Tempo: {song.tempo} BPM")
        
        print("\n=== Tracks ===") # Show first 2 tracks as example
        for track_idx, track in enumerate(song.tracks[:2], 1): 
            print(f"\nTrack {track_idx}: {track.name}")
            print(f"Number of strings: {track.strings}")
            print(f"Tuning: {track.tuning}")
            print(f"Number of measures: {len(track.measures)}")
            
            # Show a maximum of 10 measures as example
            if track.measures:
                for measure in track.measures[:10]:
                    print(f"\nMeasure {measure.number}:")
                    if measure.timeSignature:
                        print(f"Time Signature: {measure.timeSignature.numerator}/{measure.timeSignature.denominator.value}")
                    if measure.tempo:
                        print(f"Tempo: {measure.tempo.value} BPM")
                    for voice in measure.voices:
                        if voice.beats:  # Only process if there are beats
                            for beat in voice.beats:
                                if beat.notes:  # Only process if there are notes
                                    notes = []
                                    for n in beat.notes:
                                        note_str = f'String {n.string}: fret {n.value} F:{_get_finger_name(n.leftHandFinger)}'
                                        if n.effect.palmMute:
                                            note_str += ' PM'
                                        if n.isDead:
                                            note_str += ' X'
                                        if n.effect.bend:
                                            note_str += f' Bend {n.effect.bend.value/100:.1f}'
                                        notes.append(note_str)
                                    duration = f"1/{beat.duration.value}" if beat.duration else "?"
                                    print(f"Duration: {duration}, Notes: {notes}")
                                else:
                                    print("Beat contains no notes")
                        else:
                            print("Measure contains no voices")
    else:
        print("Failed to parse song")

if __name__ == "__main__":
    main() 