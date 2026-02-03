Editor
======

Small helper to edit epub files metadatas

Usage (from repository root):

```console
$ uv run editor <root-dir-containing-volume-dirs>
```


Supported metadata

# ✅ standard Dublin Core

* dc:title → Titre
* dc:creator → Auteur(s)
* dc:identifier (avec id="isbn") → ISBN
* dc:publisher → Éditeur
* dc:language → Langue
* dc:date → Date de publication
* dc:description → Description/Résumé

# ✅ calibre custom metadata

* calibre:series → Série
* calibre:series_index → Position dans la série
* calibre:rating → Note
* calibre:tags → Tags

# TODOs

- [ ] 1 file def per volumes ?
- [ ] 1 file def per serie ?
- [ ] file def format is: `yaml`, `other` (what ?)
- [ ] option to force overwrite existing meta
- [ ] option to dump existing meta from epub to yaml file
