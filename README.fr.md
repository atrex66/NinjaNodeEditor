# NinjaNodeEditor

[English](README.md) · [Magyar](README.hu.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Polski](README.pl.md) · [Srpski](README.sr.md) · [Español](README.es.md)

Éditeur visuel de logique PLC et générateur de composants HAL LinuxCNC, écrit en Python avec PySide6. Créez des graphes typés, simulez-les localement et exportez le projet complet en `.comp`. L’éditeur fonctionne sans LinuxCNC, sur un bureau ou directement sur l’écran d’un Raspberry Pi avec Qt EGLFS/KMS. L’interface est prévue pour 800 × 600.

[Guide français détaillé](docs/USER_GUIDE.fr.md) · [Licence MIT](LICENSE)

## Fonctionnalités

- Counter: Comptage/décomptage sur front montant, reset, activation, valeur s32 et sortie de seuil. [counter.json](examples/counter.json).
- Timer : déclenchement sur front, reset, durée entière en ms et sortie niveau/impulsion ; voir le guide.
- Types `bit`, `float`, `s32`, `u32`, conversions automatiques indiquées en rouge.
- Entrées détectées dans les expressions, fonctions mathématiques, comparaisons, logique et décalages `<<`/`>>`.
- Antirebond et fronts en entrée ; délais ON/OFF et inversion en sortie.
- FIFO `last`/`now` avec héritage automatique du type.
- PID avec limites, anti-windup, filtre D, anticipation optionnelle et sortie error.
- Messages d’erreur déclenchés, délai minimal et réarmement reset.
- Paramètres `@name`, exportés en pins d’entrée HAL réglables.
- Modèles Math, modules d’édition et moniteur de simulation groupé.
- Sept langues avec guides ; restauration du dernier projet.
- Groupes Project, Settings, Modules, Nodes ; plein écran en bas à droite et propriétés selon la sélection.

## Installation et démarrage

Python 3 et PySide6 selon [requirements.txt](requirements.txt). L’environnement de développement actuel utilise Python 3.13. LinuxCNC n’est pas nécessaire pour éditer ou simuler.

Après téléchargement ou clonage :

```sh
cd NinjaNodeEditor
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./run.sh --windowed
```

Interpréteur explicite : `PLC_PYTHON="$PWD/.venv/bin/python" ./run.sh --windowed`.

Sur DietPi, avec les paquets système Qt/PySide6 compatibles :

```sh
cd ~/NinjaNodeEditor
bash ./setup-dietpi.sh
./run-eglfs.sh
```

Le script met à jour apt et installe les paquets avec sudo. EGLFS choisit `/usr/bin/python3` par défaut, indépendamment d’un venv activé. Démarrez depuis une console locale avec écran disponible et droits sur les périphériques. `QT_QPA_EGLFS_KMS_CONFIG` choisit un profil personnalisé ; card1 dépend de la disposition DRM réelle.

## Utilisation

```sh
./run.sh --windowed --project examples/bit-to-u32.json
```

Ajoutez des nœuds dans Nodes, configurez-les puis reliez sorties et entrées. Pendant Simulate, le panneau droit surveille tous les modules ; entrées et paramètres sont modifiables. À l’arrêt, les propriétés apparaissent seulement pour un nœud sélectionné. Le bouton inférieur droit ou F11 active le plein écran, avec seulement Nodes au-dessus du graphe.

Ctrl+S enregistre, Suppr efface ; molette pour zoomer, fond vide pour déplacer la vue. Déconnectez les Math/Condition avant d’en modifier la structure.

`--project path.json` choisit un fichier, `--no-restore`/`--empty` démarre vide, `--language fr` choisit le français. Les options projet et démarrage vide s’excluent. Préférences dans `.state/`, ou `PLC_STATE_DIR`. Les modifications non enregistrées ne sont pas sauvegardées automatiquement.

## Export et compatibilité

Export produit `.comp`. Build .so, ou :

```sh
halcompile --compile machine_plc.comp
```

Outils de développement LinuxCNC et compilateur C requis. Ni installation ni chargement automatiques. Compilez pour l’architecture cible, puis ajoutez `update` au servo-thread HAL. Tous les modules forment un seul composant.

L’export utilise `pin_set(...)` de 2.10 avec repli pour les anciens générateurs 2.9. Vérifié : compilation 2.9 installée et générateur/en-têtes 2.10 actuels ; pas de test d’exécution avec 2.10 installé. Réexportez et recompilez après changement de version.

## Exemples et développement

[examples](examples) couvre bits→U32, conversions, direction circulaire, différence FIFO, PID/anticipation et messages. La direction circulaire n’est pas un changeur d’outil complet. [templates](templates) : modèles Math ; [locales](locales) : catalogues UTF-8.

Tests avec PySide6 et compilateur `cc` :

```sh
QT_QPA_PLATFORM=offscreen python3 -m unittest test_model test_session test_ui test_i18n
```

La simulation ne pilote pas le matériel. Éditeur expérimental de flux fini : cycles, mouvements et surveillance HAL active ne sont pas implémentés. Display n’émet pas d’ordre abort NC. Le guide détaille installation, nœuds et dépannage.

## Licence

[MIT License](LICENSE), © 2026 NinjaNodeEditor contributors. Python, PySide6/Qt et LinuxCNC conservent leurs licences propres.

## Logger : sauvegarder l’historique sur déclenchement

**+ Logger** propose 1–18 entrées `in1`, `in2`, etc. Le type (bit, float, s32, u32) suit la source ; le module, le symbole et le nom de sortie sont enregistrés. Une entrée non connectée vaut float 0. Le front montant de `trigger` sauvegarde le tampon circulaire dans l’ordre chronologique. HIGH sauvegarde une seule fois ; revenir à LOW avant de redéclencher. La sauvegarde conserve l’historique.

## E/S globales et débogage Live HAL

**E/S globales** gère les entrées/sorties communes visibles dans tous les modules actuels et futurs. Une définition et un pin exporté par signal ; positions des blocs mémorisées par module. Déplacer par le cadre/titre, double-cliquer dans la liste pour modifier. Input/Output peut devenir global. Supprimer retire toutes ses connexions. Une sortie globale a une source unique : déconnecter avant de changer. Son libellé ou **Aller à la source** ouvre le module et sélectionne le node.
