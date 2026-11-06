# Audio Dataset Attributions & Sources

The audio files used for benchmarking `hushcheck` are derived from open-access recordings hosted on Wikimedia Commons and public corpora.

### Source Files

1. **Speech Excerpt: Mike Peters on Politics and Emotion (Interview 1984)**
   - Source: [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Mike_Peters_on_Politics_and_Emotion_(Interview_1984).mp3)
   - Speaker: Mike Peters (The Alarm)
   - License: Creative Commons Attribution 3.0 Unported (CC BY 3.0)

2. **Spoken Wikipedia: Felix James McCool**
   - Source: [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:FelixJMcCool(spoken_Wikipedia_En).ogg)
   - Voice: Human volunteer contributor to Spoken Wikipedia
   - License: Creative Commons Attribution-ShareAlike 3.0 Unported (CC BY-SA 3.0)

3. **Spoken Wikipedia: Hogettes**
   - Source: [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Spoken_Wikipedia_en_Hogettes.ogg)
   - Voice: Human volunteer contributor to Spoken Wikipedia
   - License: Creative Commons Attribution-ShareAlike 3.0 Unported (CC BY-SA 3.0)

4. **Spoken Wikipedia: Chiptune**
   - Source: [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Spoken_Wikipedia_-_English_-_chiptune.oga)
   - Voice: Arlo Barnes (human volunteer reader)
   - License: Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)

5. **Chopin: Waltz in D-flat major, Op. 64, No. 1 ("Minute Waltz")**
   - Source: [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Chopin_-_Waltz_in_D-flat_Op-64_No-1_(Minute)_(Piano_Performance_by_eld%C3%BCendes%C3%BCarez).wav)
   - Performance: eldüendesüarez (Piano)
   - License: Creative Commons Attribution 3.0 Unported (CC BY 3.0)

6. **Chopin: Waltz in E minor, Op. posth.**
   - Source: [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Chopin_-_Waltz_in_E_Op-Posth_(Piano_Performance_by_eld%C3%BCendes%C3%BCarez).wav)
   - Performance: eldüendesüarez (Piano)
   - License: Creative Commons Attribution 3.0 Unported (CC BY 3.0)

### Authentic Evaluation Dataset (eval_data/)

7. **Chopin: Nocturne No. 2 in E-flat major, Op. 9 No. 2**
   - Source: [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Chopin_-_Nocturne_No._2_in_E-flat_major,_Op._9_No._2_(Frank_Levy).flac)
   - Performance: Frank Levy (Piano)
   - License: Creative Commons Attribution 3.0 Unported (CC BY 3.0)

8. **Claude Debussy: Suite bergamasque - Clair de lune**
   - Source: [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Clair_de_lune_(Claude_Debussy)_Suite_bergamasque.ogg)
   - License: Public Domain

9. **Chopin: Nocturne No. 1 in B-flat minor, Op. 9 No. 1**
   - Source: [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Chopin_-_Nocturne_No._1_in_B-flat_minor,_Op._9_No._1_(Olga_Gurevich).flac)
   - Performance: Olga Gurevich (Piano)
   - License: Creative Commons Attribution 3.0 Unported (CC BY 3.0)

10. **Nature Recording: Rain, Thunder, and Birds**
    - Source: [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Rain_thunder_and_birds.ogg)
    - License: Creative Commons Attribution-ShareAlike 3.0 Unported (CC BY-SA 3.0)

11. **Field Recording: Rain on Concrete during Thunderstorm**
    - Source: [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Rain_on_Concrete_during_storm_with_thunder.wav)
    - License: Creative Commons CC0 1.0 Universal Public Domain Dedication

12. **Historical Dialogue: Rep. Edward Boland Questions Caspar Weinberger (Iran-Contra Hearings)**
    - Source: [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Rep._Edward_Boland_Questions_Secretary_of_Defense_Caspar_Weinberger_During_the_Iran-Contra_Hearings.ogg)
    - License: Public Domain

13. **AMI Meeting Corpus (Meetings ES2002a, IS1000a, TS3003a)**
    - Source: [AMI Meeting Corpus Mirror](https://groups.inf.ed.ac.uk/ami/corpus/) / University of Edinburgh
    - Description: Multi-speaker natural meetings recorded with individual and mixed headset microphones, complete with manual word-level time-aligned annotations.
    - License: Creative Commons Attribution 4.0 International (CC BY 4.0)
    - Citation: Carletta et al., "The AMI Meeting Corpus: A Pre-announcement", In Proc. MLMI 2005.

### Reproduction

The audio files are generated locally via `python scripts/curate_audio_dataset.py`. Binary audio files are kept local and excluded from git version control.

