# Visuels du README de l'organisation

`build.py` génère les SVG de `profile/assets/` (variantes `-dark` et `-light`), avec les polices Sora et DM Sans embarquées en sous-ensemble.

```bash
pip install fonttools
mkdir -p ../fonts
curl -sfLo ../fonts/Sora.ttf "https://github.com/google/fonts/raw/main/ofl/sora/Sora%5Bwght%5D.ttf"
curl -sfLo ../fonts/DMSans.ttf "https://github.com/google/fonts/raw/main/ofl/dmsans/DMSans%5Bopsz%2Cwght%5D.ttf"
python3 build.py ../../profile/assets
```

Les textes (services, chiffres, témoignages) sont en dur dans `build.py`. `icons.json` contient les icônes Lucide et Simple Icons utilisées.
