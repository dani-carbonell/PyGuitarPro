from guitarpro.gp import parse_gp
import os

def main():
    # Use the Funky.gp file which is GP8 format
    file_path = os.path.join(os.path.dirname(__file__), "..", "guitarpro", "Funky.gp")
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
            
            # Show first measure as example
            if track.measures:
                measure = track.measures[0]
                print(f"\nFirst measure:")
                for voice in measure.voices:
                    if voice.beats:  # Only process if there are beats
                        for beat in voice.beats:
                            if beat.notes:  # Only process if there are notes
                                notes = [f"String {n.string}: fret {n.value}" for n in beat.notes]
                                duration = f"1/{beat.duration.value}" if beat.duration else "?"
                                print(f"Duration: {duration}, Notes: {notes}")
                            else:
                                print("Beat contains no notes")
                    else:
                        print("Voice contains no beats")
    else:
        print("Failed to parse song")

if __name__ == "__main__":
    main() 