# manga_creator

Une collection de petits scripts pour me faciliter la vie dans le management de ma librarie de mangas pour ma Kobo.

Pour le moment on fait ca en python c'est plus speedy avec les LLM. Et vive le vibe-coding assité.

## packer

Un script qui me permet de créer des repertoirs correspondant au volume d'une serie.

The script prend en parametre :
    - le repertoir racine de la serie
      Path vers le reprtoir racine de la serie.
    - le target volume a build
      Numeros du volume de la serie a generer
    - la range numerique des chapitres correspondant au volumes
      Range de chapitre correspondant au volume
    - un chapter cbz naming convention
      Naming convetion pour les chapitre au format cbz

En cas de probelme a acceder le reeprtoire racine, une erreur explicit est yield avant d'exit.
Le repertoir racine correspond a la serie passé en parametre d'input.
Le reprtoir racine contiens defaut les chapitre sourcé de maniere externe.
Les chapitre sont au format `.cbz` (comicbook zip).
Les chapitres au seine d'une meme serie respecte la meme naming convention.
Exemple de conventions pour un chapitre as `cbz`:
    - `Chapter 374.cbz` (Bersek)
    - `Chapter 100 The Forbidden Door.cbz` (Full metal alchemist)
    - `Ch.001.cbz` (Mashle)
Au seine du reprtoir racine, un nouveaux reprtoir correspondant au volume est crée au format `[nom serie]` v[numeros serie]`.
Un extra `0` est ajouter avant les decimal des volume 1 à 9, afin de permettre un trie part default quand `ls` est run dans le root directory.
Pour chaque chapitre correspondant au volume, le script `mv` le `cbz` au seine du reportoir volume avant de l'extraire dans un sous-repertoir nomé apres le chapitre.

Afin de speed our life, le script peut aussi prendre en option les parametres suivant:

    - nb worker, nomber max de worker parallel (threads)
      un thread a pour responsabilité un chapiter (mv du cbz + creation du chapter dir + extraction du cbz dans le chapter dir)




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
