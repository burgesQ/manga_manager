# manga_creator

Une collection de petits scripts pour me faciliter la vie dans le management de ma librarie de mangas pour ma Kobo.

Pour le moment on fait ca en python c'est plus speedy avec les LLM. Et vive le vibe-coding assité.

## packer

Un script qui me permet de créer des repertoirs correspondant au volume d'une serie.

The script prend en parametre :
 - `src-root`
   Path vers le reprtoir racine de la serie.
 - `volume` 
   Numeros du volume de la serie a generer
 - `range`
   Range numerique des chapitrez correspondant au volume
 - `convention`
   Naming convetion des chapitres au format cbz

En cas de tout probelme fatal, une erreur explicit est yield avant d'exit.
Le repertoir racine correspond a la serie passé en parametre d'input.
il contient les chapitre au fomat cbz sourcé de maniere externe.
Le format `.cbz` (comicbook zip) et un zip avec des images au foamt jpg ainsi qu'un comicbook.xml (metadata file) .
Les chapitres au sein d'une meme serie respecte la convention de nomage.
Exemple de conventions pour un chapitre as `cbz`:
    - `Chapter 001.cbz`...`Chapter 374.cbz` (Bersek)
    - `Chapter 100 The Forbidden Door.cbz` (Full metal alchemist)
    - `Ch.1.cbz` (Mashle)

certaine serie peuvent contenur des chapitres "extra" (example ...).

Au seine du repertoir racine, un nouveaux reprtoir correspondant au volume est crée au format `[nom serie] v[numeros serie]`.
Un leadibg `0` est ajouter avant les decimal des volume 1 à 9 / 2 leading `0` pour les chapitres, afin de permettre un trie part default quand `ls` est run dans le root directory / volumr directory.
Pour chaque chapitre correspondant au volume, le script `mv` le `cbz` au seine du reportoir volume avant de l'extraire dans un sous-repertoir nomé apres le chapitre.

Afin de speed our life, le script peut aussi prendre en option les parametres suivant:

 - `nb_worker`
   Nomber max de worker parallel (threads).
   Un worker a pour responsibility un chapiter (mv du cbz + creation du chapter dir + extraction du cbz dans le chapter dir)




Example:

Pour un input comme ceci:

```console
$ tree Serie_A
Serie
├── Chapter 1.tgz
├── Chapter 2.tgz
└── Chaptre 3.tgz
$ uv run packer --path ./Serie_A --serie Berserk --volume 1 --chapter-range 0..3
 Processing Berserk volume 1 (chapter 1, 2, 3)...
 Done !
$ tree Serie_A
Serie_A
└── Berserk v01
    ├── Chapter 1.tgz
    ├── Chapter 1
    │   ├── 001.jpg
    │   ├── 002.jpg
    │   ├── 003.jpg
    │   └── ComicInfo.xml
    ├── Chapter 2.tgz
    ├── Chapter 2
    │   ├── 001.jpg
    │   ├── 002.jpg
    │   ├── 003.jpg
    │   └── ComicInfo.xml
    ├── Chapter 3.tgz
    └── Chapter 3
        ├── 001.jpg
        ├── 002.jpg
        ├── 003.jpg
        └── ComicInfo.xml
```

## meta_editor

Given

Then, kindle comic converted is invoked from the CLI, generating a Serie_A_Volume_1.epub.
