from guitarpro.gp import parse_gp

def main():
    # Replace with path to your .gp file
    file_path = "guitarpro/Funky.gp"
    
    song = parse_gp(file_path)
    
    if song:
        print("=== Song Information ===")
        print(f"Title: {song.title}")
        print(f"Artist: {song.artist}")
        print(f"Album: {song.album}")
        print(f"Tempo: {song.tempo} BPM")
        
        print("\n=== Tracks ===")
        for i, track in enumerate(song.tracks, 1):
            print(f"\nTrack {i}: {track.name}")
            print(f"Number of strings: {len(track.strings)}")
            print(f"Tuning: {track.strings}")
            
            print(f"Number of measures: {len(track.measures)}")
            for j, measure in enumerate(track.measures[:2], 1):  # Show first 2 measures
                print(f"\nMeasure {j}:")
                for voice in measure.voices:
                    for beat in voice.beats:
                        notes = [f"String {n.string}: fret {n.value}" for n in beat.notes]
                        print(f"Duration: {beat.duration}, Notes: {notes}")

if __name__ == "__main__":
    main() 