# NinjaNodeEditor – részletes használati útmutató

Ez az útmutató a jelenlegi `NinjaNodeEditor` alkalmazást ismerteti. A programban egy teljes PLC-komponens logikája szerkeszthető node-okkal, helyben szimulálható, majd LinuxCNC `.comp` forrássá exportálható.

A szerkesztő szimulációja nem kapcsolódik élő HAL-hoz és nem vezérel hardvert. A **Build .so** csak fordít; nem tölti be és nem telepíti a komponenst.

## Tartalom

1. Indítás és nyelvválasztás
2. A felület és a szerkesztés
3. Projektek és modulok
4. Típusok és konverzió
5. Node-ok részletesen
6. Kifejezések és konstansok
7. Math sablonok
8. Szimuláció és hibakeresés
9. Export, fordítás és HAL-integráció
10. Gyakorlati példák
11. Hibakeresési ellenőrzőlista

## 1. Indítás és nyelvválasztás

A Raspberry Pi-n, az alkalmazás könyvtárából:

```sh
cd ~/NinjaNodeEditor
./run-eglfs.sh
```

Asztali grafikus környezetben használható a `./run.sh`. Az EGLFS közvetlenül a kijelzőt használja, megfelelő Qt EGLFS/KMS támogatással. A megjelenítőt más grafikus alkalmazás is foglalhatja.

Ha a launcher más Python-környezetet használna:

```sh
PLC_PYTHON="$PWD/.venv/bin/python" ./run-eglfs.sh
```

Indítási kapcsolók:

| Kapcsoló | Működés |
|---|---|
| `--project utvonal.json` | Megadott projekt betöltése az utolsó projekt helyett. |
| `--no-restore` vagy `--empty` | Üres projekt; az utolsó projektet sem olvassa be. |
| `--windowed` | Ablakos megjelenítés. |
| `--language hu` | Az induló felület nyelvének megadása. |
| `--screenshot /tmp/preview.png` | Képernyőkép készítése, majd kilépés. |

A projektkapcsoló és a `--no-restore` egymást kizárják.

A **Language / Nyelv** választó hét nyelvet kínál: angol (`en`), magyar (`hu`), német (`de`), francia (`fr`), lengyel (`pl`), szerb latin betűkkel (`sr`) és spanyol (`es`). A váltás azonnali, a választás a következő indulásra is megmarad. A `--language` vagy a `PLC_LANGUAGE` környezeti változó felülírhatja az induló nyelvet. Mentett választás nélkül az alapnyelv angol.

A nyelvváltás a feliratokra vonatkozik. Nem fordítja át a pinek, konstansok, változók, modulok és felhasználói sablonok nevét, a képleteket vagy a Display üzenetének szövegét. A **Manual / Útmutató** gomb az aktuális nyelvhez tartozó útmutatót nyitja meg; hiányzó fájlnál angolra vált.

## 2. A felület és a szerkesztés

Legfelül a projektműveletek vannak, alattuk a beállítások, a modulok, végül a node-hozzáadó gombok. A gráf balra, a tulajdonságpanel jobbra található.

A felső sávok sorrendje **Projekt**, **Beállítások**, **Modulok**, **Node-ok**. A jobb alsó **Teljes képernyő** gomb vagy **F11** csak a Nodes/node-hozzáadó sávot hagyja a gráf felett. Ugyanazzal a gombbal vagy F11-gyel visszatérhetsz a normál munkaterülethez; EGLFS-en a fizikai megjelenítés teljesképernyős marad. Leállított szimulációnál a tulajdonságpanel csak kijelölt node esetén jelenik meg; az üres háttérre kattintva elrejtőzik és a vászon kitágul. Futó szimulációnál az állapotmonitor kijelölés nélkül is látható. A nézetváltás nem törli a gráfot és a szimuláció előzményeit.

A Projekt, Beállítások és Modulok tömör sorok: a felirat a sor elején van, külön címsor nélkül. A Node-ok feliratos kerete megmarad, így kis képernyőn nagyobb a gráf helye.

| Művelet | Használat |
|---|---|
| Node létrehozása | Kattints a megfelelő `+` gombra. |
| Node kiválasztása | Kattints a node testére. |
| Node mozgatása | Húzd a node testét. |
| Több node kijelölése | Ctrl mellett kattints a node-okra. |
| Összekötés | Kimeneti pontra kattintás, majd bemeneti pontra kattintás; húzással is működik. |
| Bekötés megszakítása | Escape. |
| Nézet mozgatása | Az üres hátteret húzd. |
| Nagyítás/kicsinyítés | Egérgörgő. |
| Gráf nézetbe illesztése | Fit / Illesztés. |
| Node törlése | Delete billentyű vagy Delete / Törlés gomb. |
| Mentés | Save / Mentés vagy Ctrl+S. |

A bal oldali sárga bemeneti pont fogadja a jelet, a kék kimeneti pont adja. Egy bemenetnek egy jeladója lehet. Új bekötés ugyanarra a bemenetre a régit helyettesíti.

A property panelen a szövegmező módosítása fókuszvesztéskor mentődik. Az expression mezőben Enter véglegesít, Shift+Enter sort tör. A számmezők értéke a bevitel véglegesítésekor változik; nem minden begépelt részérték fut le.

A **Disconnect inputs / Bemenetek bontása** a kiválasztott node bemeneti vezetékeit bontja. A **Disconnect all / Minden kapcsolat bontása** a node összes kapcsolatát eltávolítja.

## 3. Projektek és modulok

A projekt `.json` fájl tartalmazza a node-okat, paramétereket, vezetékeket, pozíciókat és szerkesztési modulokat. A normál indulás az utolsó sikeresen megnyitott vagy mentett projektet tölti be. Mentett projekt hiányában demonstrációs gráf jelenik meg. A mentetlen módosításokat a program nem menti automatikusan.

A **New / Új** üres gráfot nyit. A megjegyzett fájl csak sikeres megnyitáskor vagy mentéskor változik. Hibás vagy hiányzó korábbi fájlnál üres indulás és státuszjelzés történik. Ilyenkor az Open / Megnyitás segítségével választható másik fájl.

### Modulok

A modul a szerkesztés csoportosítása, nem külön futó komponens.

- **New module / Új modul:** elnevezett, üres szerkesztési nézet létrehozása.
- **Rename / Átnevezés:** az aktuális modul nevének módosítása.
- **Move selected / Áthelyezés:** a kijelölt node-ok másik modulba helyezése.
- **Remove module / Modul törlése:** a csoport eltávolítása; a node-ok az első megmaradó modulba kerülnek, a kapcsolatok megmaradnak. Legalább egy modul szükséges.
- **All modules / Minden modul:** az egész gráf közös nézete, modulok közötti bekötéshez is.

A csak másik modulban látható node-ra vezető kapcsolat nem tűnik el. A port súgója jelzi a másik modult és a node azonosítóját. A szimuláció és az export minden modult tartalmaz. A konstansok és HAL-pinnevek az egész projektben közösek.

Új node az aktuális modulban jön létre; Minden modul nézetben az első modulhoz tartozik. A modulnevek és tagság a projektben megmaradnak. A régi projektformátumok node-jai a Main modulba kerülnek. A jelenlegi mentés 4-es formátumú; régebbi szerkesztő nem feltétlenül tudja beolvasni.

## 4. Típusok és konverzió

| Típus | Jelentés |
|---|---|
| `bit` | Logikai 0 vagy 1. Nullától eltérő szám igaznak számít. |
| `float` | Lebegőpontos szám. |
| `s32` | Előjeles egész, −2147483648…2147483647. |
| `u32` | Előjel nélküli egész, 0…4294967295. |

Eltérő típusok összeköthetők. A fogadó bemenet automatikusan konvertál; ezt piros felirat jelzi. Egész típusra váltáskor a törtrész nullához közelítve levágódik, a tartományon kívüli érték a típus határán korlátozódik. Például float `3.9` → s32 `3`, float `-2` → u32 `0`.

Minden időmező egész milliszekundumban, 1 ms-os lépéssel állítható: debounce, ON/OFF delay, Display cooldown és PID D-szűrő. A 0 kikapcsolja az adott késleltetést/szűrőt. A tényleges időfelbontást az update periódusa határozza meg: a szerkesztő 20 ms-os szimulációs lépése nem tud 1 ms-os eseményeket külön megjeleníteni.

## 5. Node-ok részletesen

### Input / Bemenet

A komponens külső HAL input pinje. Neve egyedi, kisbetűből indul; számot és kötőjelet tartalmazhat. Példa: `pressure`, `door-closed`.

Szimulációban a Simulated input mező adja a nyers értéket. Bitnél a node alsó állapotfeliratára is kattinthatsz. Az Invert a bemeneti bitet fordítja meg; a debounce ezután szűr, a Trigger pedig a szűrt állapotból állít elő jelet.

| Trigger | Kimenet |
|---|---|
| `level` | A stabil bemeneti szint. |
| `rising` | Egy update hosszú jel a felfutó élen. |
| `falling` | Egy update hosszú jel a lefutó élen. |
| `both` | Egy update hosszú jel bármely élre. |

A debounce azt az időt kéri, amelyen át a megváltozott bemenetnek stabilnak kell maradnia. Exportáláskor a nyers érték az Input saját HAL pinjéről érkezik; a szimulált érték beállítása nem helyettesíti az élő HAL-bekötést.

### Output / Kimenet

A komponens külső HAL output pinje. Egy `in` bemenete van. Bekötetlenül az Initial value/state alapértéket használja. Bitnél ON és OFF késleltetés állítható, majd az Invert a késleltetett eredményt fordítja meg.

Az ON delay a kívánt bekapcsolási állapot tartósságát figyeli, az OFF delay a kikapcsolásét. A késleltetés alatt visszaváltó jel nem viszi végig a korábbi átmenetet. Az Initial state az induló tárolt kimeneti állapotot adja.

### Const / Névvel hivatkozható konstans

Nincs vezetékkel bekötendő portja. Van neve, típusa és alapértéke. Például `gain`, float, `2.5`. Kifejezésben `@gain`, property mezőben a Value / @név választóval használható.

A név kisbetűből indul, számot és aláhúzást tartalmazhat. A `@speed_limit` exportált HAL pinje `<komponens>.speed-limit`. Minden konstans HAL **input pin**, alapértékkel; élő HAL-ban változtatható, ezért futás közbeni paraméterként működik. A konstans saját alapértéke csak konkrét érték lehet, másik konstanshivatkozás nem.

### Math

Az expression változóiból jönnek létre a bemenetek. A kimenet neve `result`, a típusa külön állítható. Minden változóhoz típus, forrás és alapérték tartozik.

- **Input port:** a változó beköthető; bekötetlenül a megadott alapértéket használja.
- **Constant:** a változó értékét a property adja, vezetéke nincs.

Ez a változónkénti Constant forrás különbözik a névvel hivatkozható Const node-tól. A változó értékmezője ugyanakkor `@név` hivatkozást is fogadhat.

### Condition / Feltétel

A Math-hoz hasonló változókezelés, két bit kimenettel: `true` és `false`. Ezek az érték és annak logikai inverze; nem programvégrehajtási ágak. Példa: `pressure >= minimum and door_closed`.

### Invert / Invertálás

Egy bit bemenet logikai negálása. Bekötetlen bemenet 0, ezért ilyenkor a kimenet 1.

### FIFO

Két mintát tart: `now` az aktuális bemeneti érték, `last` az előző update értéke. Az első update során a `last` az Initial value. A bekötött jel típusa határozza meg a FIFO be- és kimeneteinek típusát; bekötetlenül külön típus választható.

A mintavétel minden update során egyszer történik. Ez nem több elemes üzenetsor. A FIFO jelenlegi adatfolyam-modellben nem oldja fel a visszacsatolt gráfkör tiltását: a `now` az aktuális bemenettől függ.

### Timer / timeout időzítő

A **+ Időzítő** node-nak két bit bemenete van: `trigger` és `reset`; kimenete bit `out`. Az **Időtartam ms** nemnegatív egész, 1 ms-os lépéssel, alapból 1000; Const-hivatkozást is fogad. A trigger felfutó éle indít, induláskor az eleve magas jel is trigger. A trigger visszaesése nem szakítja meg; futás közbeni új éleket figyelmen kívül hagy. Az időtartamot az indítás élén mintavételezi, ezért a hivatkozott paraméter változtatása csak a következő futásra érvényes. Indításkor a számláló 0, utána az update-periódusok növelik. A 0 ms azonnali lejárat.

**Kimeneti mód:** `level`/szint esetén lejárat után `out=1` marad a resetig, további indítás nélkül. `pulse`/impulzus esetén a kimenet lejáratkor egy update-ciklusra 1, aztán 0; új felfutó él újraindíthatja. A reset szintérzékeny és elsőbbséget élvez: HIGH alatt törli a kimenetet és megszakítja a futást. Reseten át magas trigger nem indul újra a reset elengedésekor; le-, majd felfutás szükséges. A lejárat ciklusában aktív reset elnyomja a kimenetet. Bekötetlen bemenet 0. Szimulációban 20 ms-os lépés, HAL-ban az update-periódus határozza meg az időzítést; hibás/nempozitív periódus törli az időzítő állapotát.

Timeout: a művelet indítása trigger, a sikeres befejezés reset. Reteszelt hibához szintkimenetet, egyszeri jelzéshez impulzust használj. A [timeout.json](../examples/timeout.json) 1000 ms-os időzítőt, timeout HAL-kimenetet és Display üzenetet mutat. A szimuláció indítása/leállítása törli az előzményeket.

### PID

Bemenetek: `setpoint`, `feedback`, `enable`, `reset`. Kimenetek: `out`, `error`, mindkettő float. Az `error = setpoint − feedback` közvetlenül használható hibakereséshez.

A Kp az arányos tag, a Ki az időarányos integráló tag, a Kd a differenciáló tag. A D tag a mért feedback változására működik, nem az alapjel ugrására. A D filter ms szűri ezt a tagot. Az Output min/max korlátozza a kimenetet; az integráló tag kifelé növekedése korlátozott.

A Feedforward kapcsolóval `FF gain × setpoint` tag adható a kimenethez. Tiltott PID vagy aktív reset esetén a kimenet és a hibakimenet 0, az előzmények törlődnek. Bekötetlen setpoint, feedback és enable esetén a property alapértékei érvényesek; a reset alapból 0.

### Display / Üzenet

Bemenetek: `trigger`, `value`, `reset`. A beállított aktív trigger szintre lépéskor egyszer küldi az üzenetet. Az Append value hozzáfűzi a value bemenet számértékét. A cooldown alatt érkező új aktiválások elmaradnak, nem sorba állnak.

A reset felfutó éle felülírja a cooldown tiltást és újraélesíti az üzenetet. Tartósan 1-en tartott reset nem ismétli folyamatosan az üzenetet. Szimulációban a státuszsorban látszik a szöveg.

Az export RTAPI hibaüzenetet ír. Nincs benne külön NC abort parancs: a hibaüzenet önmagában nem garantálja az NC-program megállítását. Ez a fogadó rendszer integrációjának külön feladata.

## 6. Kifejezések és paraméterhivatkozások

Támogatott műveletek:

```text
+  -  *  /  %  ^  **  <<  >>
==  !=  <  <=  >  >=
and  or  not
```

A `<<` és `>>` 32 bites, nullával feltöltő biteltolás. Például `1 << 3 = 8`, illetve `128 >> 3 = 16`. A bal operandus törtrésze levágódik, majd az alsó 32 bitje marad meg; negatív számnál a kettes komplemens bitmintája számít. A balra kilépő bitek elvesznek, a jobbra eltolás nem terjeszti ki az előjelbitet. Az eltolás 0–31 közötti egész lehet; más eltolás vagy nem véges operandus 0-t ad. Az eredményre ezután a node szokásos típuskonverziója vonatkozik. Az összeadás megelőzi a biteltolást, ezért összetett képletnél használj zárójeleket: `(n0 << 0) + (n1 << 1) + (n2 << 2) + (n3 << 3)`.

A `^` hatványozás, nem XOR. A zárójelek a szokásos műveleti sorrendet módosítják. A `%` maradék előjele az osztóhoz igazodik. Nulla közeli osztó esetén az osztás és modulo 0-t ad. Beépített konstansok: `pi`, `e`.

Függvények: `abs`, `min`, `max`, `clamp`, `pow`, `sqrt`, `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `log`, `log10`, `exp`, `floor`, `ceil`. A trigonometrikus szögek radiánban értendők. A min/max két argumentumot, a clamp hármat vár. Érvénytelen függvénytartomány vagy nem véges függvényeredmény 0-t ad.

Példák:

```text
n0 * 1 + n1 * 2 + n2 * 4 + n3 * 8
clamp(x * @gain, 0, @maximum)
abs(actual - requested) < tolerance
sin(angle * pi / 180)
```

Az `@név` nem hoz létre külön expression bemeneti portot. A névnek már létező Const node-ra kell mutatnia. Egy normál változónév viszont portot hoz létre, ha a forrása Input port.

A referenciaválasztó a számszerű paramétereknél és kezdeti értékeknél, valamint a PID alapértelmezett enable mezőjénél használható. A konverzió a fogadó típushoz igazodik; időmezőben a hivatkozott érték egész milliszekundumra kerekül. A kezdeti állapotot adó HAL-referenciákat az export az első update során mintavételezi.

Használatban lévő Const node nem törölhető. Először szüntesd meg a rá mutató expression- és paraméterhivatkozásokat. A duplikált, fenntartott és ismeretlen nevek hibát adnak.

## 7. Math sablonok

A Math property panelen sablon menthető és betölthető, illetve a legördülőből kiválasztható. A sablon a képletet, eredménytípust, változók forrását, típusát, értékét és a sablon nevét tartalmazza. A vezetékeket nem menti.

A sablon neve a Math node fejlécében jelenik meg. A beépített sablonok a `templates` könyvtárban vannak: AND2, OR2, valamint 4 és 8 bites u32 összeállítás. Saját sablon ebbe a könyvtárba menthető, hogy a választóban is megjelenjen. A választó a property panel újraépítésekor frissül.

Bekötött Math/Condition/FIFO node képlete és típusa védett; Math sablonváltáshoz is bontani kell a be- és kimeneti kapcsolatokat. A Disconnect all után szerkeszthető, majd újra beköthető. Ha egy sablon `@név` referenciát tartalmaz, a célprojektben a megfelelő Const node-nak már léteznie kell.

## 8. Szimuláció és hibakeresés

A Simulate / Szimuláció indítja a futást; induláskor az előzmények alaphelyzetbe kerülnek. Stop / Leállítás megállítja és visszahozza a property panelt. A szimuláció modellezett lépése 20 ms; a Qt megjelenítési időzítő nem realtime ütemező.

Futás közben a jobb panel minden modul jeleit mutatja:

- Bemenetek: bit kapcsoló vagy számszerű szerkesztő.
- Konstansok: élőben állítható globális paraméterek.
- Kimenetek: aktuális értékek.
- Belső jelek: Math, Condition, FIFO, PID és Display állapotok.

Egy jel egy sor; a hosszú név rövidülhet, a súgó teljes névvel, típussal és modullal segít. Ha a feldolgozott bemenet eltér a nyers értéktől, külön jelérték jelenik meg. Const által vezérelt szimulált Input értéke közvetlenül nem szerkeszthető; a Const értékét módosítsd.

A bemeneti értékek és konstansok élő módosítása nem indítja újra a szimuláció előzményeit. Szerkezeti vagy más konfigurációs módosítás viszont alaphelyzetbe állíthatja azokat. Modul- és nyelvváltás csak a nézetet alakítja át, nem újraindítás.

## 9. Export, fordítás és HAL-integráció

1. Mentsd a projektet JSON-fájlba.
2. Az Export gombbal készíts `.comp` fájlt. A fájlnév kisbetűből induljon, csak kisbetűt, számot és aláhúzást tartalmazzon; például `machine_plc.comp`.
3. A Build .so a jelenlegi gráfot újraexportálja a legutóbbi exporthelyre és meghívja a `halcompile --compile` parancsot.
4. Az eredmény `.so`, a fordítási napló `.build.txt`. A fordításhoz LinuxCNC fejlesztői környezet és halcompile szükséges.

A céleszközön fordíts: az x86 számítógépen készített `.so` nem tölthető be ARM64 Raspberry Pi-n. A szerkesztő nem hoz létre élő hardverbekötést; a telepítés és betöltés külön művelet.

A generált komponens egyetlen `update` függvényt exportál. A teljes projekt, minden modulja és minden Const input pinje benne van. A HAL-integrációban ezt a meglévő servo-thread megfelelő helyére kell tenni: hardverbeolvasás után, hardverkimenetek kiküldése előtt.

A következő csak illusztráció egy már telepített komponens és már létező servo-thread esetére:

```hal
loadrt machine_plc
addf machine-plc.update servo-thread
setp machine-plc.gain 2.5
```

A tényleges neveket és bekötéseket a saját exportod alapján add meg. Normál Input node-nál a külső HAL pin szolgáltatja az értéket. Const esetén a megadott alapérték az input pin kezdőértéke, és `setp`-vel vagy bekötött jellel változtatható.

## 10. Gyakorlati példák

### Négy bitből u32

Hozz létre négy bit Inputot és egy Math node-ot. Töltsd be a 4-bit-to-u32 sablont, és kösd a bemeneteket n0…n3-ra. Ha saját képletet írsz, a négy változó típusát állítsd bitre, az eredményt u32-re. A képlet:

```text
n0 + n1 * 2 + n2 * 4 + n3 * 8
```

Szimulációban n0=1, n1=0, n2=1, n3=0 esetén az eredmény 5.

### FIFO különbség

A mért float Inputot kösd a FIFO `in` portjára. Math expression: `now - last`. A FIFO `now` és `last` kimenetét kösd a megfelelő Math bemenetre. Ez két egymást követő minta különbsége; sebességhez még a tényleges mintaperiódussal is osztani kell.

### Állítható erősítés

Const neve `gain`, típusa float, értéke 2. Input neve `reading`, típusa float. Math: `x * @gain`, x bemenetére a reading. Output: float `scaled`. Szimulációban reading=4 esetén scaled=8; gain=3-ra állítva scaled=12, vezetékek módosítása nélkül.

### Modulokra bontott géplogika

Hozz létre Bemenetek, Kenés és Főorsó modulokat. Helyezd át a node-okat, majd Minden modul nézetben készítsd el a szükséges keresztkapcsolatokat. A szimulációs panel mindhárom modul értékeit mutatja, az export egyetlen komponens marad.

A körirány-választás példája a `examples/circular-direction.json`. Ez irányválasztás; teljes szerszámcseréhez további állapotok, reteszelés, érzékelők, késleltetés és hibakezelés kell.

## 11. Hibakeresési ellenőrzőlista

| Jelenség | Mit ellenőrizz? |
|---|---|
| Nem jön létre expression bemenet | A változó Source mezője Input port legyen; az @referencia és Constant forrás nem hoz létre portot. |
| Szürke képlet/típus/sablon | A node még be van kötve. Disconnect all szükséges. |
| Piros típusfelirat | Automatikus konverzió; ellenőrizd a forrás és fogadó típusát. |
| Node nem látszik | Másik modulban lehet. Válaszd a Minden modul nézetet vagy Fit-et. |
| Bekötés csak egy modulban nem látszik | A másik vége más modulban van; port súgó és Minden modul nézet segít. |
| Const nem törölhető | Még használja egy képlet, alapérték vagy paraméter. |
| Ismeretlen @név | A Const node létrehozva van? Pontosan egyezik a név? |
| Késleltetés pontatlan a szimulációban | A modellezett lépés 20 ms; a HAL update periódusa külön időalap. |
| Nem indul az utolsó projekt | Indíts `--no-restore` kapcsolóval, majd nyiss meg érvényes projektet. |
| Build hibás | Nézd meg a `.build.txt` naplót, a halcompile elérhetőségét és a fájl/pin nevét. |
| FIFO-val sem enged visszacsatolást | A gráfkörök jelenleg nem támogatottak. |
| Display üzenet nem állítja meg az NC-t | Az export csak hibaüzenetet ír, abort funkciót nem hív. |

A fordítási és operációs rendszerből származó diagnosztikák nyelve a külső eszköztől függ. A nyelvi JSON-fájlok a `locales` könyvtárban vannak; új felirat hiányzó fordításánál az angol szöveg marad látható.

## LinuxCNC 2.9 / 2.10 kompatibilitás

A 2.10 fejlesztői HAL API kimenetíráskor `pin_set(ertek)` hívást használ a korábbi `pin = ertek` helyett. Az exportáló settereket generál, a régebbi 2.9-es `halcompile` számára pedig feltételes hozzárendelési makrót biztosít. A `bit`, `float`, `s32` és `u32` deklarációkat a jelenlegi 2.10 fordító még elfogadja, de elavulási figyelmeztetést adhat.

LinuxCNC verzióváltás után exportáld és fordítsd újra a komponenst az új telepítés `halcompile` eszközével. A korábbi `.so` fájl átvitele nem helyettesíti az újrafordítást. A kompatibilitást telepített 2.9-es fordítással, valamint a jelenlegi 2.10 generátorral és HAL/RTAPI fejlécekkel végzett C ellenőrzéssel vizsgáltuk; telepített 2.10-es futáspróbát és hardvertesztet ez nem jelent.

## Logger: előzmények mentése triggerrel

A **+ Logger** gombbal hozz létre naplózót, állíts be 1–18 adatbemenetet, és kösd a jeleket az `in1`, `in2` stb. pontokra. A bemenet automatikusan átveszi a forrás bit, float, s32 vagy u32 típusát. A minta a modul, a szimbólum és a kimenet nevét is tárolja. A bekötetlen bemenet float nullát ad. A `trigger` bit bemenet felfutó éle menti az aktuális ringbuffert, a legrégebbi mintától kezdve. Tartós HIGH csak egyszer ment; új mentéshez előbb LOW szükséges. A mentés nem törli az előzményeket.

A **Mintavétel ms** pozitív egész ezredmásodperc, `@konstans` is lehet. A **Ringbuffer hossza** 1–100000 minta. Egy frissítésben legfeljebb egy minta készül: a felbontást a futtatási periódus korlátozza, a szerkesztő szimulátora 20 ms-os. Két mintavétel közötti trigger a már meglévő mintákat menti; az első minta előtt CSV/TSV esetén csak fejléc, JSONL esetén üres fájl készül.

CSV, TSV vagy JSONL választható. A CSV/TSV fejlécében, a JSONL minden sorában szerepel a bemenet, a szimbólum és a típus; minden formátum tartalmaz eltelt `time_ms` időt. A **Számformátum** `.0g`–`.17g`, `.0f`–`.17f` vagy `.0e`–`.17e` lehet, például `.10g`, `.3f`. Az egész jelek értéke pontos marad. A **Kimeneti fájl** neve használhatja a `{timestamp}` (UTC), `{sequence}` és `{node}` helyettesítőket: `logs/position-{timestamp}.csv`. Fix fájlnév esetén az előző fájl atomikusan lecserélődik. A tartalmat a kiválasztott formátum határozza meg, a kiterjesztéstől függetlenül.

Szimulációban a relatív út a mentett projekt könyvtárára, mentetlen projektnél a szerkesztő könyvtárára vonatkozik. LinuxCNC-ben az export könyvtárára. Exportkor `.comp`, `.logger.py`, `.logger.json` és `.hal` keletkezik. A komponenst a szokásos `halcompile` paranccsal telepítsd, majd a `servo-thread` létrehozása után töltsd be a generált `.hal` fájlt. Ez betölti a komponenst, elindítja a gyűjtőt a rendszer Pythonjával és LinuxCNC `hal` moduljával, és hozzáadja az update függvényt. A korábbi, ugyanerre a komponensre vonatkozó `loadrt`/`addf` sorokat cseréld le, hogy ne legyen dupla betöltés. A generált fájlokat tartsd együtt; költöztetés után exportálj újra, mert a HAL fájl abszolút segédfájl-utakat tartalmaz.

A realtime szál csak korlátos HAL stream rekordokat továbbít. Az előzményeket a gyűjtő tárolja, és a fájlírás realtime-on kívül fut. Mintavétel közben a gyűjtőnek futnia kell. A transport túlcsordulása minták vagy mentési triggerek elvesztését okozhatja; folyamatban lévő mentés közben ugyanahhoz a Loggerhez új mentés kimarad, jelzéssel. Szimulációban az eredmény és a hiba a státuszsorban, LinuxCNC-ben a gyűjtő stderr kimenetén jelenik meg. Nagy buffer több memóriát és nagyobb fájlt igényel. Példa: `examples/logger-history.json`.

A vezeték a vonal közelében kattintva, kizoomolva is kijelölhető; a kijelölt vonal sárga. Delete törli a kijelölt vezetékeket a node-ok megtartásával. Ctrl-kattintással több vezeték is kijelölhető.

## Globális I/O, HAL-hozzárendelés és Live HAL debug

A **Globális I/O** ablakban bemenetek és kimenetek adhatók hozzá és távolíthatók el. A közös bemeneti/kimeneti blokkok minden meglévő és új modulban megjelennek; minden jelnek egy definíciója és egy exportált pinje van. A blokk a kereténél/fejlécénél mozgatható, helye modulonként megmarad. A listában dupla kattintással nyitható meg a jel property oldala. Sima Input/Output is globálissá tehető a **Globális (minden modulban)** kapcsolóval. Az eltávolítás minden modulból törli a jel kapcsolatait. Globális kimenetnek egy meghajtója lehet: másik bekötés előtt bontsd a korábbit. A forrás modulnevére vagy az **Ugrás a meghajtóhoz** gombra kattintva a forrásmodul és a kijelölt meghajtó node jelenik meg középre igazítva.

Minden Input/Output rendelkezik **HAL pin / signal választása** gombbal. A külön ablak **Frissítés** gombja aszinkron `halcmd -s show pin` és `halcmd -s show sig` lekérdezést végez. Kereshető a pin/komponens neve; fajta, típus, irány és kompatibilitás szerint szűrhető. A táblázat értéket, meglévő HAL-signalt és projektbeli meghajtót mutat, a részletekben a signal többi pinje is látszik. A **Katalógus betöltése/mentése** offline tervezéshez használható. Az `examples/hal-catalogue.json` mintakatalógus, nem valódi gépkiosztás. A választás átveszi a típust; a **HAL-hozzárendelés törlése** után a node kézzel beköthető HAL pin marad. Output célként IN pin vagy meghajtó nélküli signal használható. Típusütközés és több meghajtó nem engedett. Exportkor a meglévő netet használja, már bekötött külső pint nem helyez át másik signalra.

Exportkor `nev.comp`, `nev.hal`, `nev.unload.hal`, `nev.test.hal`, `nev.test.unload.hal` és `nev.hal.json` készül, Logger esetén a segédfájlokkal együtt. A `nev.hal` a projekt teljes betöltése: komponens, I/O-bekötések, konstansok, Logger és update a `servo-thread` szálban. A hardver/GUI pinek és a szál létrejötte után töltsd be; postgui fájlként is használható. A gép motion/hardver konfigurációját továbbra is a meglévő HAL adja. A tesztfájl csak a bemeneteket köti be. Az unload fájlok a sikeresen betöltött párjukhoz valók; kézzel végzett részleges hibás betöltésnél az aktuális állapotot ellenőrizni kell. A szerkesztő Live HAL munkafolyamata a már sikerült lépéseket hiba esetén automatikusan visszabontja.

A **Debug** kapcsolóval típusos köztes kimenetek is exportálódnak: például `nev.debug-n12-result`, FIFO `last`/`now`, PID `out`/`error`. A stabil node-azonosító miatt modulátnevezéskor is megmarad a név. A manifest tárolja a node–pin megfeleltetést és a fordítás ujjlenyomatát. Normál buildben ezek a pinek kimaradnak. A kapcsoló a következő Export/Fordítás műveletre hat.

Válaszd a **Live HAL teszt** módot, majd indítsd a Szimuláció gombbal. Ebben a módban mindig debug komponens készül: a program `halcompile --install` paranccsal telepíti, majd elkülönített `nne_live_<uid>` néven tölti be. Futó LinuxCNC/HAL, `servo-thread`, Python `hal` modul és fejlesztői fordítóeszközök szükségesek. A telepítéshez írási jogosultság kell; a munkafolyamat használhat már engedélyezett, jelszókérés nélküli `sudo -n` telepítést. Ha szükséges, rejtett mezős ablakban bekéri a sudo jelszót. Nem menti és nem naplózza a jelszót; jogosultsághibát a státuszsorban jelez. A helyi szimuláció LinuxCNC nélkül is használható.

Live HAL tesztben csak a külső bemenetek kapcsolódnak; a projekt gép felé menő kimeneti céljai bekötetlenek maradnak. A lefordított komponens számol realtime-ban, a szerkesztő kb. 20 Hz-cel olvassa a debug pineket a Python HAL interfészen. A Python-szimulátor közben nem fut. A hozzárendelt bemenet csak olvasható; a szabad bit/szám bemenet állítható. Szerkezeti szerkesztéshez előbb Stop kell. A kijelzett kimenetek, FIFO-előzmény és PID error a valódi komponensből jönnek. Rövid impulzus két kijelzőfrissítés között kimaradhat; mintatörténethez a Logger való.

A státuszsor mutatja a komponens mért futásidejét és maximumát µs-ban, továbbá az eredeti LinuxCNC `.update.time` értéket. A natív `.time`/`.tmax` órajel-egysége backendfüggő, ezért a debug kód `rtapi_get_time()` alapú nanomásodperces mérést is készít. A µs érték az instrumentált update törzsének ideje, nem a GUI periódusa vagy a teljes servo-thread ideje. Stop/kilépés eltávolítja a tesztkomponenst és visszabontja annak kapcsolatait, megtartva a korábbi signalokat. Az ujjlenyomat ellenőrzése megvár egy valódi RT-frissítést; álló/hibás szál esetén hibát jelez. Unix-felhasználónként egy Live HAL teszt futhat. A telepített privát tesztmodult következő tesztnél újra használja; az ideiglenes forráscsomagot törli. Az élő értékek nem írják felül a mentett szimulációs alapértékeket. Példa: `examples/global-io.json`.

Kézi telepítés és betöltés továbbra is lehetséges:

```bash
sudo halcompile --install nev.comp
halcmd -f nev.hal
```

Csak bemenetes kézi teszthez debug export után a `nev.test.hal` használható. Új betöltés előtt bontsd a korábbi példányt; az újratelepítés nem cseréli a memóriában futó modult. RIP telepítésnél a hozzá tartozó buildkörnyezet és telepítési jogosultság érvényes.

A két külső HAL-hozzárendelés közötti, azonos típusú közvetlen Input → Output kapcsolat HAL netként exportálódik, a kizárólag erre használt végpontok komponenspinei kimaradnak. Invertálás, élfigyelés, debounce, késleltetés, konverzió, köztes node vagy saját, külső HAL-hoz nem rendelt komponenspin esetén megmarad a komponensen belüli feldolgozás. Ha az input belső logikát is táplál, a bemeneti komponenspin megmarad. Külön meglévő HAL signalokat nem von össze: ilyenkor a komponens továbbítja az értéket. Kizárólag közvetlen kapcsolatoknál nincs loadrt/addf. Debugban megmaradnak a megfigyelő pinek; a csak bemeneteket bekötő Live teszt továbbra sem kapcsol külső kimeneteket.

A Live HAL teszt időbélyeggel naplózza a fordítás és telepítés kimenetét, a HAL-parancsokat és a hibákat az editor könyvtárának `.state/logs/live-hal.log` fájljába (vagy `PLC_STATE_DIR/logs/live-hal.log`). Hiba esetén a státuszsor mutatja az útvonalat. A napló legfeljebb 1 MiB-os fájlokra forgatódik, három korábbi példánnyal. Jelszó és hitelesítési válaszüzenet nem kerül bele. A fordítás az ideiglenes forráskönyvtárból fut, így sudo alatt sem kell hozzáférni az SSHFS munkakönyvtárhoz.

## Counter – számláló

A **+ Számláló** gombbal adható hozzá. Bemenetei: `up`, `down`, `enable`, `reset` (`bit`); kimenetei: `count` (`s32`), `reached` (`bit`). Az `up` mintavett felfutó éle 1-et hozzáad, a `down` éle 1-et kivon. Az egyidejű felfutó élek kioltják egymást. Az első ciklusban HIGH bemenet is élnek számít.

A tulajdonságoknál a **Kezdeti érték**, **Küszöb** és az alapértelmezett engedélyezés állítható; a számértékek név szerinti konstansra is hivatkozhatnak. Bekötés nélkül az `up`, `down`, `reset` LOW; az `enable` az alapbeállítást használja (kezdetben bekapcsolva). A HIGH reset minden ciklusban visszaállítja a kezdőértéket, letiltott számlálónál is. Letiltáskor az érték megmarad. Reset és letiltás alatt az élek elvesznek: a végig HIGH bemenet feloldáskor nem ad új számlálást.

A `count` −2147483648 / 2147483647 határokon megáll, nem fordul át. A `reached = count >= küszöb` minden ciklusban kiértékelődik, reset és letiltás alatt is; nem reteszelt. A kezdőértéket induláskor és resetkor, a küszöböt minden ciklusban olvassa. A szimuláció újraindítása vagy a komponens újratöltése törli az előzményeket.

Nyisd meg a [counter.json](../examples/counter.json) példát, indíts helyi szimulációt, és kapcsold a `pulse-up` bemenetet háromszor ki/be: a `count-value` eléri a 3-at, a `threshold-reached` bekapcsol. Egy `pulse-down` felfutó él 2-re csökkenti az értéket és kikapcsolja a jelzést. A `clear-count` nulláz. A JSON mentés, a szimulátor, a `.comp` export és a debug monitorok mindkét kimenettípust kezelik. A node a beállított ciklusidővel mintavett éleket számolja; gyors fizikai impulzusokhoz hardveres számláló/enkóder szükséges.


## Feldolgozás és visszacsatoló memória

SR/RS tároló, hiszterézis, watchdog, rámpa, aluláteresztő/átlag/medián szűrő, állapotgép és egyciklusos memóriapár: a **Feldolgozás…** menüben. [Részletes működés, példák és mérés](../PROCESSING.hu.md).
