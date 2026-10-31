# NinjaNodeEditor — guide d’utilisation détaillé

NinjaNodeEditor permet de construire la logique d’un composant PLC sous forme de graphe, de la simuler localement et d’exporter un fichier source LinuxCNC `.comp`. La simulation ne communique ni avec le HAL actif ni avec le matériel. **Build .so** compile seulement ; installation et chargement sont des opérations distinctes.

## Sommaire

1. Démarrage et langue
2. Interface et édition
3. Projets et modules
4. Types et conversions
5. Nœuds
6. Expressions et références
7. Modèles Math
8. Simulation et diagnostic
9. Export, compilation et intégration HAL
10. Exemples pratiques
11. Dépannage
12. LinuxCNC 2.9 / 2.10

## 1. Démarrage et langue

Sur le Raspberry Pi, depuis le dossier de l’application :

```sh
cd ~/NinjaNodeEditor
./run-eglfs.sh
```

Sur un bureau graphique, utilisez `./run.sh --windowed`. EGLFS nécessite des bibliothèques Qt EGLFS/KMS compatibles et l’accès aux périphériques d’affichage et d’entrée. L’écran peut déjà être occupé par une autre application. Sous DietPi, `bash ./setup-dietpi.sh` installe les paquets système correspondants. Le lanceur EGLFS utilise `/usr/bin/python3` par défaut. Pour sélectionner un autre interpréteur :

```sh
PLC_PYTHON="$PWD/.venv/bin/python" ./run-eglfs.sh
```

| Option | Effet |
| --- | --- |
| `--project path.json` | Ouvrir ce projet à la place du dernier fichier mémorisé. |
| `--no-restore` / `--empty` | Démarrer avec un graphe vide sans lire le projet mémorisé. |
| `--windowed` | Demander un affichage en fenêtre. |
| `--language fr` | Choisir la langue au démarrage. |
| `--screenshot /tmp/preview.png` | Enregistrer une capture puis quitter. |

`--project` et `--no-restore` sont incompatibles. Les langues proposées sont anglais (`en`), hongrois (`hu`), allemand (`de`), français (`fr`), polonais (`pl`), serbe en alphabet latin (`sr`) et espagnol (`es`). Le changement est immédiat et mémorisé. `--language` ou `PLC_LANGUAGE` remplace le choix initial ; sans préférence, l’anglais est utilisé. **Manual** ouvre le guide dans la langue choisie, ou en anglais si le fichier manque.

Les identifiants, formules, noms de modules/modèles et messages saisis ne sont pas traduits. Les préférences sont dans `.state/`, ou le dossier indiqué par `PLC_STATE_DIR`.

## 2. Interface et édition

Les quatre groupes supérieurs sont Projet, Réglages, Modules et Nœuds, dans cet ordre. Ils rassemblent les opérations sur le projet, la langue/le manuel/la simulation, l’organisation en modules et les boutons d’ajout. Le graphe est à gauche, les propriétés à droite.

Les groupes sont **Projet**, **Réglages**, **Modules**, **Nœuds**, dans cet ordre. Le bouton **Plein écran** en bas à droite ou **F11** laisse uniquement la barre Nœuds au-dessus du graphe. Le même bouton ou F11 restaure la vue normale ; sous EGLFS, l’écran physique reste en plein écran. À l’arrêt, les propriétés apparaissent seulement avec un nœud sélectionné ; cliquez sur le fond vide pour les masquer et agrandir le graphe. Pendant la simulation, le moniteur reste visible sans sélection. Le changement de vue conserve le graphe et l’historique.

Projet, Réglages et Modules sont des lignes compactes avec le libellé au début. Nœuds conserve son cadre titré, pour gagner de la place sur les petits écrans.

| Action | Utilisation |
| --- | --- |
| Créer/sélectionner/déplacer un nœud | Bouton `+` correspondant ; cliquer ou faire glisser le corps. |
| Sélection multiple | Ctrl-clic. |
| Connecter | Cliquer sur une sortie puis une entrée, ou faire glisser. |
| Annuler la connexion | Échap. |
| Déplacer la vue / zoomer | Faire glisser le fond vide / molette. |
| Voir tout le graphe | **Fit**. |
| Supprimer / enregistrer | Suppr / Ctrl+S ou boutons correspondants. |

Les ports jaunes reçoivent les signaux, les bleus les fournissent. Une entrée a une seule source ; une nouvelle connexion remplace l’ancienne. **Disconnect inputs** retire les fils entrants ; **Disconnect all** retire tous les fils du nœud.

Un texte est validé à la perte du focus. Dans une expression, Entrée valide et Maj+Entrée ajoute une ligne. Les nombres sont validés à la fin de la saisie, sans exécuter chaque valeur intermédiaire incomplète.

## 3. Projets et modules

Le JSON contient nœuds, paramètres, connexions, positions et modules. Le dernier projet ouvert ou enregistré avec succès est restauré au démarrage ; sans fichier mémorisé, une démonstration apparaît. Les modifications non enregistrées ne sont pas sauvegardées automatiquement. **New** crée un graphe vide sans oublier le dernier fichier. Un fichier absent ou invalide provoque un démarrage vide avec diagnostic ; utilisez **Open** pour récupérer.

Les modules organisent l’édition d’un composant unique. **New module** crée un groupe, **Rename** le renomme et **Move selected** déplace les nœuds. **Remove module** transfère ses nœuds au premier module restant sans perdre les connexions ; il doit rester au moins un module. **All modules** affiche le graphe entier pour éditer les connexions entre modules.

Les connexions masquées restent actives ; l’infobulle du port indique l’autre module et le nœud. Simulation, constantes et noms HAL sont globaux. L’export comprend tous les modules. Un nouveau nœud appartient au module courant, ou au premier dans la vue globale. Le format 4 conserve cette organisation ; les formats 1–3 restent lisibles et placent les anciens nœuds dans Main. Un ancien éditeur peut ne pas lire le format 4.

## 4. Types et conversions

| Type | Signification |
| --- | --- |
| `bit` | 0 ou 1 ; tout nombre non nul est vrai. |
| `float` | Nombre flottant en double précision. |
| `s32` | Entier signé, −2147483648…2147483647. |
| `u32` | Entier non signé, 0…4294967295. |

Les types différents peuvent être reliés. La conversion à l’entrée réceptrice est automatique et indiquée en rouge. La conversion entière tronque vers zéro et limite au domaine du type : `3.9` → s32 `3`, `-2` → u32 `0`.

Antirebond, délais ON/OFF, délai entre messages et filtre D du PID se règlent en millisecondes entières, par pas de 1 ms. Zéro désactive le délai/filtre. La résolution effective dépend de la période d’actualisation ; une simulation à pas de 20 ms ne distingue pas les événements espacés de 1 ms.

## 5. Nœuds

### Input

Entrée HAL externe nommée. Le nom doit être unique, commencer par une minuscule et peut contenir chiffres et tirets, par exemple `pressure` ou `door-closed`. **Simulated input** fournit la valeur brute locale. Un bit peut aussi être basculé en cliquant sur son état simulé dans le nœud.

Pour les bits : inversion, antirebond, puis détection du déclenchement. L’antirebond impose la stabilité pendant la durée choisie. `level` fournit le niveau stable ; `rising`, `falling`, `both` fournissent une impulsion d’une actualisation. Une entrée initialement active peut produire un front montant. L’export lit le vrai pin HAL ; la valeur simulée ne remplace pas le câblage matériel.

### Output

Sortie HAL avec une entrée `in`. Sans connexion, la valeur/l’état initial s’applique. Les délais ON/OFF exigent que la demande persiste ; si elle s’inverse, la transition en attente est annulée. L’inversion s’applique après le délai. L’état initial définit l’état logique mémorisé au démarrage.

### Const

Paramètre nommé, typé, avec valeur par défaut et sans ports. Utilisez `@gain` dans les formules ou le sélecteur de référence des propriétés numériques. Les noms commencent par une minuscule et peuvent contenir chiffres et soulignements. `@speed_limit` devient `<component>.speed-limit`.

Chaque Const est exportée comme **pin d’entrée HAL** avec sa valeur initiale et peut être modifiée par `setp` ou un signal. Sa propre valeur par défaut doit être littérale, pas une autre référence. Supprimez ses utilisations avant de supprimer une Const encore référencée.

### Math et Condition

Les variables de la formule créent automatiquement les entrées. Chacune possède type, source et valeur par défaut. **Input port** crée un port ; **Constant** utilise la valeur configurée sans port. Les valeurs de variables peuvent référencer `@name`.

Math fournit `result`, de type configurable. Condition fournit les bits complémentaires `true` et `false`, pas des branches d’exécution. Les modifications structurelles des formules, types, sources et modèles sont verrouillées tant que le nœud est connecté ; utilisez **Disconnect all**.

### Invert

NON logique d’un bit. Une entrée déconnectée vaut 0 ; la sortie vaut alors 1.

### FIFO

`now` est l’échantillon courant ; `last` celui de l’actualisation précédente. Au premier passage, `last` utilise la valeur initiale. La source connectée détermine les types des ports ; sans connexion, un type de repli est sélectionnable.

Un échantillon est pris à chaque actualisation, même sans changement. C’est un historique de deux valeurs, pas une file push/pop. Les cycles de rétroaction du graphe restent interdits car `now` dépend de l’entrée courante.

### Timer / dépassement de délai

**+ Temporisateur** a les entrées bit `trigger`, `reset` et la sortie bit `out`. **Durée ms** est un entier non négatif, par pas de 1 ms, défaut 1000 ; une Const peut être référencée. Le front montant démarre, y compris un trigger initialement haut au premier passage. Un trigger qui retombe n’annule pas le comptage ; les fronts pendant le comptage sont ignorés. La durée est lue au démarrage et reste fixe pour ce cycle. Le compteur commence à 0 puis avance aux actualisations suivantes. Zéro expire immédiatement.

Mode `level` : après expiration, `out=1` jusqu’au reset, sans nouveau démarrage. `pulse` : 1 pendant une actualisation à l’expiration, puis 0 ; un nouveau front montant peut redémarrer. Reset est actif par niveau et prioritaire : HIGH annule et efface la sortie. Un trigger maintenu haut pendant reset ne redémarre pas au relâchement ; il doit redescendre puis remonter. Reset au cycle d’expiration supprime la sortie. Entrées déconnectées : 0. Simulation : pas de 20 ms ; HAL : période du thread. Les périodes invalides/non positives effacent l’état.

Pour un timeout, reliez le début d’opération à trigger et la réussite à reset. Niveau pour un défaut mémorisé, impulsion pour une notification. [timeout.json](../examples/timeout.json) montre 1000 ms, une sortie HAL timeout et Display. Le démarrage/arrêt de simulation efface l’historique.

### PID

Entrées : `setpoint`, `feedback`, `enable`, `reset`. Sorties float : `out`, `error`. En fonctionnement, `error = setpoint − feedback`.

Kp est proportionnel, Ki intègre dans le temps et Kd dérive la mesure, évitant un pic dû à un saut de consigne. **D filter ms** filtre cette dérivée. **Output min/max** limite la sortie ; l’anti-windup limite l’accumulation de l’intégrale vers l’extérieur.

L’anticipation optionnelle ajoute `FF gain × setpoint`. Si le PID est désactivé ou réinitialisé, les deux sorties valent zéro et l’historique est effacé. Consigne, mesure et activation non connectées utilisent les valeurs des propriétés ; reset vaut 0 par défaut.

### Display

Entrées : `trigger`, `value`, `reset`. Le passage au niveau actif configuré produit une seule émission. **Append value** ajoute la valeur numérique. Les activations pendant le délai minimal sont abandonnées, pas mises en attente ; maintenir le déclencheur actif ne répète rien.

Un front montant de reset contourne le délai et réarme l’émission ; un reset maintenu haut ne répète pas les messages. La simulation affiche le texte dans la barre d’état. L’export émet une erreur RTAPI, sans commande d’arrêt du programme NC.

## 6. Expressions et références

Opérations prises en charge :

```text
+  -  *  /  %  ^  **  <<  >>
==  !=  <  <=  >  >=
and  or  not
```

`^` et `**` sont des puissances, pas XOR. Le reste `%` prend le signe du diviseur ; division/modulo par un diviseur presque nul donne zéro. `pi` et `e` ne créent pas de ports.

`<<` et `>>` sont des décalages logiques sur 32 bits avec remplissage par zéros : `1 << 3` donne 8, `128 >> 3` donne 16. L’opérande gauche est tronqué vers zéro puis réduit aux 32 bits faibles ; les nombres négatifs utilisent leur complément à deux. Les bits sortants sont perdus et le décalage droit ne propage pas le signe. Le nombre de positions doit être entier entre 0 et 31 ; sinon, ou pour un opérande non fini, le résultat est zéro. La conversion du type de résultat s’applique ensuite. L’addition est prioritaire sur les décalages : parenthésez les termes.

Fonctions : `abs`, `min`, `max`, `clamp`, `pow`, `sqrt`, `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `log`, `log10`, `exp`, `floor`, `ceil`. Angles en radians ; min/max attendent deux arguments, clamp trois. Domaine invalide ou résultat non fini : zéro. Aucun code Python arbitraire n’est exécuté.

```text
(n0 << 0) + (n1 << 1) + (n2 << 2) + (n3 << 3)
clamp(x * @gain, 0, @maximum)
abs(actual - requested) < tolerance
sin(angle * pi / 180)
```

`@name` exige une Const existante et ne crée aucun port. Les paramètres numériques, valeurs initiales et activation PID par défaut acceptent des références. Conversion selon le type récepteur ; les temps référencés sont arrondis à la milliseconde entière. Les références d’état initial sont lues au premier passage. Noms inconnus, réservés ou dupliqués : erreur.

## 7. Modèles Math

Enregistrez/chargez un modèle depuis les propriétés Math ou choisissez-le dans la liste. Il contient formule, type du résultat, sources/types/valeurs des variables et nom, mais aucun fil. Son nom devient le titre du nœud.

`templates/` contient AND2, OR2 et assemblage de quatre/huit bits en U32. Les modèles personnels y apparaissent lors de la reconstruction suivante du panneau. Déconnectez toutes les entrées et sorties avant de charger un modèle ou de modifier la structure d’un Math/Condition/FIFO connecté. Les Const référencées doivent déjà exister dans le projet cible.

## 8. Simulation et diagnostic

**Simulate** réinitialise l’historique et démarre les pas de 20 ms ; **Stop** restaure les propriétés. Le timer Qt n’est pas un ordonnanceur temps réel. Le moniteur couvre tous les modules, une ligne par entrée, constante, sortie et signal interne. Entrées et constantes sont modifiables ; les infobulles précisent nom complet, type et module. Une entrée traitée différente du brut est affichée séparément. Modifiez la Const si elle commande la valeur d’une entrée simulée.

Modifier une entrée ou une constante en direct conserve l’historique. Les modifications structurelles ou de configuration peuvent le réinitialiser. Changer de langue/module ne change que la vue. La simulation n’actionne jamais le matériel.

## 9. Export, compilation et intégration HAL

1. Enregistrer le projet JSON.
2. Exporter `.comp` avec un nom commençant par une minuscule et contenant seulement minuscules, chiffres et soulignements, par exemple `machine_plc.comp`.
3. **Build .so** réexporte le graphe au dernier emplacement puis lance `halcompile --compile`.
4. Le résultat est `.so`, le journal `.build.txt`. Les outils de développement LinuxCNC sont nécessaires.

Compilez pour l’architecture cible : une bibliothèque x86 ne se charge pas sur un Pi ARM64. L’éditeur n’installe/charge pas le module et ne raccorde pas le matériel. Une seule fonction `update` contient tous les modules et pins Const. Placez-la dans le servo-thread existant après la lecture et avant l’écriture matérielle.

Illustration pour un composant déjà installé et un thread existant :

```hal
loadrt machine_plc
addf machine-plc.update servo-thread
setp machine-plc.gain 2.5
```

Utilisez les noms réels de votre export et raccordez les pins. Input lit un pin externe ; Const commence à sa valeur par défaut puis peut être modifiée par `setp` ou un signal.

## 10. Exemples pratiques

### Quatre bits en U32

Créez quatre Inputs bit, chargez le modèle quatre bits dans Math et raccordez n0…n3. Pour une formule personnelle, variables bit et résultat u32 :

```text
n0 + n1 * 2 + n2 * 4 + n3 * 8
```

n0=1, n1=0, n2=1, n3=0 donne 5.

### Différence FIFO

Entrée float vers FIFO, puis `now` et `last` vers Math `now - last`. Pour un taux de variation, divisez aussi par la vraie période d’échantillonnage.

### Gain réglable

Const `gain`, float, 2 ; Input `reading`, float ; Math `x * @gain` ; Output `scaled`, float. Reading relié à x. Reading=4 donne 8 ; gain=3 donne 12 sans recâblage.

### Organiser la machine

Créez des modules Entrées, Lubrification et Broche ; déplacez les nœuds puis raccordez-les dans All modules. Le moniteur couvre tout et l’export reste un composant. `examples/circular-direction.json` choisit seulement une direction ; un changeur d’outil complet demande séquence, verrouillage, capteurs, temporisations et gestion des défauts.

## 11. Dépannage

| Symptôme | Vérification |
| --- | --- |
| Port d’expression absent | Source Input port ; Constant et @références n’ont pas de ports. |
| Formule/type/modèle grisé | Disconnect all d’abord. |
| Type rouge | Vérifier la conversion automatique. |
| Nœud/fil invisible | All modules, Fit et infobulles des ports. |
| Const impossible à supprimer / référence inconnue | Retirer les usages / vérifier le nom exact. |
| Délai simulé imprécis | Pas de 20 ms ; HAL a sa propre période. |
| Projet de démarrage invalide | `--no-restore`, puis ouvrir un fichier valide. |
| Compilation échouée | `.build.txt`, halcompile et noms fichier/pins. |
| Rétroaction FIFO refusée | Les cycles du graphe ne sont pas pris en charge. |
| Display n’arrête pas NC | Une erreur affichée n’est pas une commande abort. |

Les diagnostics système/compilateur gardent leur langue propre. Catalogues dans `locales/` ; toute traduction manquante revient à l’anglais.

## 12. LinuxCNC 2.9 / 2.10

L’API 2.10 en développement écrit les sorties avec `pin_set(value)` au lieu de `pin = value`. L’export génère les setters et des macros conditionnelles compatibles avec les anciens halcompile 2.9. Les noms `bit`, `float`, `s32`, `u32` restent acceptés, parfois avec avertissements de dépréciation.

Après une mise à niveau, réexportez et recompilez avec le halcompile de la nouvelle installation. Une ancienne `.so` ne remplace pas cette étape. Vérifications effectuées : compilation 2.9 installée et contrôle C avec générateur/en-têtes HAL/RTAPI 2.10 actuels ; ce n’est pas un essai d’exécution 2.10 installé ni un essai matériel.

## Logger : sauvegarder l’historique sur déclenchement

**+ Logger** propose 1–18 entrées `in1`, `in2`, etc. Le type (bit, float, s32, u32) suit la source ; le module, le symbole et le nom de sortie sont enregistrés. Une entrée non connectée vaut float 0. Le front montant de `trigger` sauvegarde le tampon circulaire dans l’ordre chronologique. HIGH sauvegarde une seule fois ; revenir à LOW avant de redéclencher. La sauvegarde conserve l’historique.

Période : millisecondes entières positives, avec possibilité de `@constant`. Tampon : 1–100000 échantillons. Au plus un échantillon par mise à jour ; simulation à 20 ms. Un trigger entre deux acquisitions sauvegarde les données existantes. Avant le premier échantillon, CSV/TSV contient seulement l’en-tête et JSONL est vide. CSV/TSV indique noms et types dans l’en-tête, JSONL dans chaque ligne ; `time_ms` mesure le temps écoulé. Format numérique : `.0g`–`.17g`, `.0f`–`.17f`, `.0e`–`.17e` ; les entiers restent exacts. Le nom accepte `{timestamp}` (UTC), `{sequence}`, `{node}`. Un nom fixe remplace atomiquement le fichier précédent. Le format choisi détermine le contenu indépendamment de l’extension.

Les chemins relatifs utilisent le dossier du projet sauvegardé, sinon celui de l’éditeur ; sous LinuxCNC, le dossier d’export. L’export produit `.comp`, `.logger.py`, `.logger.json`, `.hal`. Installer le composant avec `halcompile`, puis charger `.hal` après création de `servo-thread`. Ce fichier charge le composant, lance le collecteur Python avec le module LinuxCNC `hal` et ajoute la fonction update. Remplacer les anciennes lignes `loadrt`/`addf`. Garder les fichiers ensemble et réexporter après déplacement : les chemins auxiliaires sont absolus.

Le thread temps réel transmet des enregistrements HAL bornés ; le collecteur garde l’historique et écrit hors temps réel. Il doit rester actif pendant l’acquisition. Un débordement peut perdre des échantillons/triggers. Une nouvelle sauvegarde pendant une sauvegarde du même Logger est signalée et ignorée. Résultats et erreurs apparaissent dans la barre d’état ou sur stderr du collecteur. Les grands tampons consomment plus de mémoire. Exemple : `examples/logger-history.json`.

Cliquer près d’une connexion pour la sélectionner, même avec un zoom réduit. La ligne devient jaune ; Delete supprime la connexion en conservant les nodes. Ctrl-clic permet une sélection multiple.

## E/S globales et débogage Live HAL

**E/S globales** gère les entrées/sorties communes visibles dans tous les modules actuels et futurs. Une définition et un pin exporté par signal ; positions des blocs mémorisées par module. Déplacer par le cadre/titre, double-cliquer dans la liste pour modifier. Input/Output peut devenir global. Supprimer retire toutes ses connexions. Une sortie globale a une source unique : déconnecter avant de changer. Son libellé ou **Aller à la source** ouvre le module et sélectionne le node.

**Choisir un pin / signal HAL** ouvre une recherche avec filtres de type, direction et compatibilité. **Actualiser** lit `halcmd -s show pin` et `halcmd -s show sig` sans bloquer. Valeur, signal HAL, source du projet et autres pins du signal sont visibles. Charger/enregistrer le catalogue permet le travail hors ligne. Le type est repris automatiquement ; effacer la liaison conserve un pin manuel. Une sortie cible un IN ou un signal sans source existante. Les nets existants sont réutilisés ; les pins connectés ne sont pas déplacés. Les conflits sont refusés.

L’export produit `.comp`, `.hal`, `.unload.hal`, `.test.hal`, `.test.unload.hal`, `.hal.json` et les auxiliaires Logger. `.hal` charge le projet, raccorde les E/S, initialise les constantes, démarre Logger et ajoute update à `servo-thread`. Charger après création des pins matériel/GUI et du thread, éventuellement postgui. La configuration motion/matériel reste celle de la machine. `.test.hal` raccorde seulement les entrées. Les fichiers unload correspondent à des chargements réussis ; vérifier un chargement manuel partiellement échoué. Le démarrage live annule automatiquement les étapes réussies en cas d’erreur.

**Debug** exporte les valeurs intermédiaires, dont `name.debug-n12-result`, FIFO `last`/`now`, PID `out`/`error`. IDs stables et manifest assurent la correspondance. L’export normal les omet. **Test HAL live** puis Simulate construit et installe automatiquement un debug via `halcompile --install`, sous `nne_live_<uid>`. Nécessite HAL actif, `servo-thread`, Python `hal` et outils de développement. Il faut le droit d’installation ; `sudo -n` déjà autorisé peut être utilisé, sinon le mot de passe sudo est demandé dans un champ masqué, sans enregistrement ni journalisation. Les erreurs apparaissent dans l’état.

Seules les entrées externes sont raccordées. Le composant compilé calcule en temps réel ; Python HAL fournit l’affichage vers 20 Hz, sans simulation Python parallèle. Les entrées liées sont en lecture seule ; les entrées libres sont réglables. Stop avant modification structurelle. Des impulsions courtes peuvent échapper à l’affichage ; utiliser Logger pour l’historique. L’état montre durée et maximum mesurés en µs, plus `.update.time` natif. Les unités HAL dépendent du backend ; debug mesure aussi des nanosecondes avec `rtapi_get_time()`. La durée concerne le corps update instrumenté, pas tout le servo-thread. Stop/quitter retire le test et ses connexions en préservant les signaux existants. L’empreinte attend une vraie mise à jour RT. Un test par utilisateur Unix ; module installé réutilisé, sources temporaires supprimées. Les valeurs live ne remplacent pas les valeurs de simulation sauvegardées.

Manuellement : `sudo halcompile --install name.comp`, puis `halcmd -f name.hal` ; pour les seules entrées, export debug et `name.test.hal`. Décharger avant de recharger : installer ne remplace pas un module actif. RIP utilise son environnement de compilation. Exemples : `examples/global-io.json`, `examples/hal-catalogue.json` (catalogue fictif).

Une liaison directe Input → Output entre deux affectations HAL externes de même type est exportée comme réseau HAL. Les pins du composant utilisés uniquement pour cette liaison sont omis. Traitement, conversion, pins internes ou signaux HAL existants distincts conservent le passage par le composant. Les entrées alimentant aussi une logique interne restent disponibles. Un projet de liaisons directes uniquement ne nécessite pas loadrt/addf. Debug conserve les pins d’observation ; le test Live des entrées ne connecte aucun destinataire de sortie externe.

Live HAL enregistre les horodatages, sorties de compilation et installation, commandes HAL et erreurs dans `.state/logs/live-hal.log` (ou `PLC_STATE_DIR/logs/live-hal.log`). Le chemin apparaît en cas d’erreur. Rotation : 1 MiB par fichier et trois sauvegardes. Aucun mot de passe n’est enregistré. La compilation utilise le répertoire temporaire des sources, pas le répertoire SSHFS.

## Counter – compteur

**+ Compteur** : entrées `up`, `down`, `enable`, `reset` (`bit`) ; sorties `count` (`s32`), `reached` (`bit`). Les fronts montants ajoutent/retirent 1 ; les fronts simultanés se compensent. HIGH au premier cycle compte comme un front. Valeur initiale, seuil et activation par défaut sont réglables, avec références aux constantes.

Entrées non connectées : LOW, sauf `enable` (activation par défaut, initialement active). Reset HIGH restaure la valeur initiale à chaque cycle, même désactivé. La désactivation conserve la valeur. Les fronts pendant reset/désactivation sont ignorés ; un HIGH maintenu ne compte pas à la réactivation. Saturation : −2147483648 à 2147483647. `reached = count >= seuil` est évalué à chaque cycle, même pendant reset/désactivation, sans mémorisation. Valeur initiale lue au démarrage/reset ; seuil lu à chaque cycle. Redémarrer efface l’historique.

Exemple : [counter.json](../examples/counter.json). En simulation, basculer `pulse-up` trois fois de LOW à HIGH : valeur 3 et seuil actif. `pulse-down` revient à 2 ; `clear-count` remet à 0. JSON, simulation, export `.comp` et moniteurs de débogage prennent en charge les deux types de sortie. Les impulsions physiques rapides nécessitent un compteur matériel/encodeur.
