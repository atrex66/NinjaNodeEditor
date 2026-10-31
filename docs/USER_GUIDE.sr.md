# NinjaNodeEditor — detaljno uputstvo

NinjaNodeEditor omogućava uređivanje logike celog PLC komponenta kao grafa čvorova, lokalnu simulaciju i izvoz LinuxCNC izvornog fajla `.comp`. Simulator nije povezan sa aktivnim HAL-om ni hardverom. **Build .so** samo prevodi; instaliranje i učitavanje su odvojeni koraci.

## Sadržaj

1. Pokretanje i jezik
2. Interfejs i uređivanje
3. Projekti i moduli
4. Tipovi i konverzija
5. Čvorovi
6. Izrazi i reference
7. Math šabloni
8. Simulacija i dijagnostika
9. Izvoz, prevođenje i HAL integracija
10. Primeri
11. Rešavanje problema
12. LinuxCNC 2.9 / 2.10

## 1. Pokretanje i jezik

Na Raspberry Pi računaru, iz direktorijuma aplikacije:

```sh
cd ~/NinjaNodeEditor
./run-eglfs.sh
```

Na grafičkoj radnoj površini koristite `./run.sh --windowed`. EGLFS zahteva usklađene Qt EGLFS/KMS biblioteke i pristup ekranu i ulaznim uređajima. Druga aplikacija možda već koristi ekran. Na DietPi sistemu `bash ./setup-dietpi.sh` instalira odgovarajuće sistemske pakete. EGLFS skripta podrazumevano koristi `/usr/bin/python3`. Drugi interpreter izaberite izričito:

```sh
PLC_PYTHON="$PWD/.venv/bin/python" ./run-eglfs.sh
```

| Opcija | Dejstvo |
| --- | --- |
| `--project path.json` | Otvara navedeni projekat umesto zapamćenog. |
| `--no-restore` / `--empty` | Pokreće prazan graf bez čitanja poslednjeg projekta. |
| `--windowed` | Zahteva prikaz u prozoru. |
| `--language sr` | Bira početni jezik. |
| `--screenshot /tmp/preview.png` | Čuva snimak prozora i završava rad. |

`--project` i `--no-restore` se međusobno isključuju. Jezici: engleski (`en`), mađarski (`hu`), nemački (`de`), francuski (`fr`), poljski (`pl`), srpski latinicom (`sr`) i španski (`es`). Promena važi odmah i pamti se. `--language` ili `PLC_LANGUAGE` menja početni izbor; podrazumevan je engleski. **Manual** otvara uputstvo na izabranom jeziku, odnosno englesko ako odgovarajući fajl nedostaje.

Identifikatori, formule, nazivi modula/šablona i sopstvene poruke se ne prevode. Podešavanja su u `.state/`; `PLC_STATE_DIR` bira drugi direktorijum.

## 2. Interfejs i uređivanje

Gornje grupe su Projekat, Podešavanja, Moduli i Čvorovi, tim redom. Sadrže rad sa projektom, jezik/uputstvo/simulaciju, organizaciju modula i dodavanje čvorova. Graf je levo, svojstva desno.

Grupe alata su **Projekat**, **Podešavanja**, **Moduli**, **Čvorovi**, tim redom. Dugme **Ceo ekran** dole desno ili **F11** ostavlja samo traku Čvorovi iznad grafa. Isto dugme ili F11 vraća običan pogled; na EGLFS fizički ekran ostaje preko celog ekrana. Kada simulacija ne radi, svojstva se prikazuju samo za izabrani čvor; klik na praznu pozadinu ih sakriva i širi graf. Tokom simulacije monitor ostaje vidljiv bez izbora. Promena pogleda čuva graf i istoriju.

Projekat, Podešavanja i Moduli su sažeti redovi sa oznakom na početku. Čvorovi zadržavaju okvir sa naslovom, uz više mesta na malom ekranu.

| Radnja | Upotreba |
| --- | --- |
| Kreiranje/izbor/pomeranje čvora | Odgovarajuće dugme `+`; klik ili prevlačenje tela čvora. |
| Izbor više čvorova | Ctrl i klik. |
| Povezivanje | Klik na izlaz, zatim ulaz; moguće je i prevlačenje. |
| Odustajanje od veze | Escape. |
| Pomeranje pogleda / uvećanje | Prevlačenje prazne pozadine / točkić miša. |
| Ceo graf u pogledu | **Fit**. |
| Brisanje / čuvanje | Delete / Ctrl+S ili odgovarajuća dugmad. |

Žuti ulazi primaju, plavi izlazi daju signal. Ulaz ima jedan izvor; nova veza zamenjuje prethodnu. **Disconnect inputs** uklanja ulazne veze, **Disconnect all** sve veze čvora.

Tekst se potvrđuje kada polje izgubi fokus. U izrazu Enter potvrđuje, Shift+Enter dodaje red. Brojevi se potvrđuju po završetku unosa, a ne posle svake nepotpune međuvrednosti.

## 3. Projekti i moduli

JSON čuva čvorove, parametre, veze, pozicije i module. Običan start vraća poslednji uspešno otvoren ili sačuvan projekat; bez zapamćenog fajla prikazuje se demonstracija. Nesačuvane izmene se ne čuvaju automatski. **New** otvara prazan graf bez brisanja zapamćene putanje. Nedostajući ili neispravan fajl daje prazan graf i obaveštenje; koristite **Open**.

Moduli organizuju uređivanje jedne komponente. **New module** pravi grupu, **Rename** menja ime, **Move selected** premešta čvorove. **Remove module** premešta njegove čvorove u prvi preostali modul, uz očuvanje veza; najmanje jedan modul ostaje. **All modules** prikazuje ceo graf za povezivanje između modula.

Skrivene međumodulske veze i dalje rade. Objašnjenje porta navodi drugi modul i čvor. Simulacija, konstante i HAL imena su globalni; izvoz obuhvata sve module. Novi čvor pripada izabranom modulu, a u zajedničkom pogledu prvom. Format 4 čuva organizaciju; formati 1–3 se čitaju i stari čvorovi pripadaju Main modulu. Stariji editor možda ne čita format 4.

## 4. Tipovi i konverzija

| Tip | Značenje |
| --- | --- |
| `bit` | 0 ili 1; svaki broj različit od nule je tačan. |
| `float` | Broj dvostruke preciznosti sa pokretnim zarezom. |
| `s32` | Sa znakom, −2147483648…2147483647. |
| `u32` | Bez znaka, 0…4294967295. |

Različiti tipovi se mogu povezati. Konverzija se automatski vrši na prijemnom ulazu i označava crveno. Celobrojna konverzija odseca prema nuli i ograničava opseg: `3.9` → s32 `3`, `-2` → u32 `0`.

Debounce, ON/OFF kašnjenja, razmak poruka i PID D filter koriste cele milisekunde u koracima od 1 ms. Nula isključuje kašnjenje/filter. Stvarna rezolucija zavisi od perioda ažuriranja; simulacija sa korakom 20 ms ne razdvaja pojedinačne događaje od 1 ms.

## 5. Čvorovi

### Input

Imenovani spoljni HAL ulaz. Ime mora biti jedinstveno, počinjati malim slovom i može sadržati cifre i crtice, npr. `pressure`, `door-closed`. **Simulated input** daje lokalnu sirovu vrednost. Bit se može prebaciti i klikom na tekst simuliranog stanja u čvoru.

Obrada bita ide redom: invertovanje, debounce, okidanje. Promenjeni nivo mora biti stabilan zadato vreme. `level` daje stabilan nivo; `rising`, `falling`, `both` daju impuls od jednog ažuriranja. Početno aktivan ulaz može dati rastući impuls. Izvoz čita pravi HAL pin; simulirana vrednost ne zamenjuje hardversku vezu.

### Output

Spoljni HAL izlaz sa ulazom `in`. Bez veze važi početna vrednost/stanje. ON/OFF kašnjenja zahtevaju trajanje zahteva; povratak zahteva otkazuje prelaz koji čeka. Invertovanje sledi posle kašnjenja. Početno stanje postavlja sačuvano logičko stanje na startu.

### Const

Imenovani parametar sa tipom i podrazumevanom vrednošću, bez portova. U formulama koristite `@gain`, u brojčanim poljima izbor reference. Imena počinju malim slovom, uz cifre i donje crte. `@speed_limit` se izvozi kao `<component>.speed-limit`.

Svaka Const postaje HAL **ulazni pin** sa podrazumevanom vrednošću, promenljiv preko `setp` ili signala. Njena sopstvena vrednost mora biti literal, ne druga referenca. Uklonite sve upotrebe pre brisanja korišćene Const.

### Math i Condition

Promenljive izraza automatski stvaraju ulaze; svaka ima tip, izvor i početnu vrednost. **Input port** stvara port; **Constant** koristi vrednost bez porta. Vrednost promenljive može upućivati na `@name`.

Math daje `result` izabranog tipa. Condition daje komplementarne bitove `true` i `false`, ne grane izvršavanja. Povezani čvorovi zaključavaju strukturne izmene formula, tipova, izvora i šablona dok se ne upotrebi **Disconnect all**.

### Invert

Logičko NE za bit. Nepovezan ulaz je 0, pa je izlaz 1.

### FIFO

`now` je trenutni uzorak; `last` uzorak prethodnog ažuriranja. Pri prvom ažuriranju `last` koristi početnu vrednost. Povezani izvor određuje tipove svih portova; bez veze postoji izbor rezervnog tipa.

Uzorkuje se jednom po ažuriranju, čak i bez promene vrednosti. Ovo je istorija dva uzorka, ne push/pop red. Ciklusi povratne sprege ostaju zabranjeni jer `now` zavisi od trenutnog ulaza.

### Timer / prekoračenje vremena

**+ Tajmer** ima bit ulaze `trigger`, `reset` i bit izlaz `out`. **Trajanje ms** je nenegativan ceo broj, korak 1 ms, podrazumevano 1000; dozvoljena je Const referenca. Rastuća ivica pokreće, uključujući početno visok trigger pri prvom ažuriranju. Pad triggera ne prekida; ivice tokom rada se ignorišu. Trajanje se očitava na početku i ostaje isto za taj ciklus. Brojač kreće od 0, sledeća ažuriranja dodaju period. Nula ističe odmah.

`level`: posle isteka `out=1` do reset-a, bez novih pokretanja. `pulse`: 1 tokom jednog ažuriranja pri isteku, zatim 0; nova rastuća ivica može ponovo pokrenuti. Reset je aktivan nivoom i ima prednost: HIGH prekida i briše izlaz. Trigger visok kroz reset ne pokreće pri oslobađanju; mora pasti i ponovo porasti. Reset u ciklusu isteka potiskuje izlaz. Nepovezani ulazi su 0. Simulacija ima korak 20 ms; HAL koristi period thread-a. Nevažeći/nepozitivni period briše stanje.

Za timeout povežite početak radnje na trigger, uspešan završetak na reset. Nivo za zapamćenu grešku, impuls za jednu poruku. [timeout.json](../examples/timeout.json) pokazuje 1000 ms, HAL timeout izlaz i Display. Start/stop simulacije briše istoriju.

### PID

Ulazi: `setpoint`, `feedback`, `enable`, `reset`. Float izlazi: `out`, `error`. Kada radi, `error = setpoint − feedback`.

Kp je proporcionalan, Ki integriše po vremenu, Kd diferencira merenu povratnu vrednost umesto skoka zadate vrednosti. **D filter ms** filtrira izvod. **Output min/max** ograničava rezultat; anti-windup ograničava rast integrala ka spolja.

Opcioni feedforward dodaje `FF gain × setpoint`. Isključen ili resetovan regulator daje nulu na oba izlaza i briše istoriju. Nepovezani setpoint, feedback i enable koriste vrednosti svojstava; reset je podrazumevano 0.

### Display

Ulazi: `trigger`, `value`, `reset`. Ulazak u podešeni aktivni nivo šalje jednu poruku. **Append value** dodaje brojčanu vrednost. Aktivacije tokom blokade se odbacuju, ne čekaju u redu; držanje triggera aktivnim ne ponavlja poruku.

Rastuća ivica reset zaobilazi blokadu i ponovo omogućava poruku; stalno visok reset ne ponavlja ispis. Simulacija prikazuje tekst u statusnoj liniji. Izvoz emituje RTAPI grešku, bez komande za prekid NC programa.

## 6. Izrazi i reference

Podržane operacije:

```text
+  -  *  /  %  ^  **  <<  >>
==  !=  <  <=  >  >=
and  or  not
```

`^` i `**` su stepenovanje, ne XOR. Ostatak `%` ima znak delioca; deljenje/modulo skoro nulom daje nulu. `pi` i `e` ne stvaraju portove.

`<<` i `>>` su logička 32-bitna pomeranja sa dopunom nulama: `1 << 3` daje 8, `128 >> 3` daje 16. Levi operand se odseca prema nuli i svodi na donja 32 bita; negativni brojevi koriste dvojni komplement. Izbačeni bitovi se gube, pomeranje udesno ne proširuje znak. Broj mesta mora biti ceo od 0 do 31; druge vrednosti ili nekonačni operandi daju nulu. Posle toga važi uobičajena konverzija rezultata. Sabiranje ima prednost nad pomeranjem: koristite zagrade oko pomerenih članova.

Funkcije: `abs`, `min`, `max`, `clamp`, `pow`, `sqrt`, `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `log`, `log10`, `exp`, `floor`, `ceil`. Uglovi su u radijanima; min/max uzimaju dva argumenta, clamp tri. Nevažeći domen ili nekonačan rezultat funkcije daje nulu. Proizvoljan Python kod se ne izvršava.

```text
(n0 << 0) + (n1 << 1) + (n2 << 2) + (n3 << 3)
clamp(x * @gain, 0, @maximum)
abs(actual - requested) < tolerance
sin(angle * pi / 180)
```

`@name` traži postojeću Const i ne stvara port izraza. Reference su dostupne brojčanim parametrima, početnim vrednostima i podrazumevanom PID enable. Konverzija prati tip prijemnika; vremenske reference se zaokružuju na cele milisekunde. Početna stanja se u izvozu čitaju tokom prvog ažuriranja. Nepoznata, rezervisana i duplirana imena se odbijaju.

## 7. Math šabloni

Šablone čuvajte/učitavajte kroz Math svojstva ili birajte iz liste. Sadrže formulu, tip rezultata, izvore/tipove/vrednosti promenljivih i ime, bez veza. Ime se prikazuje kao naslov čvora.

`templates/` sadrži AND2, OR2 i pakovanje četiri/osam bitova u U32. Sopstveni šabloni se pojavljuju posle ponovne izgradnje panela. Pre učitavanja šablona ili promene strukture povezanog Math/Condition/FIFO čvora odvojite sve ulaze i izlaze. Referencirane Const moraju već postojati u ciljnom projektu.

## 8. Simulacija i dijagnostika

**Simulate** vraća istoriju na početak i pokreće korake modela od 20 ms; **Stop** vraća svojstva. Qt tajmer nije realtime raspoređivač. Monitor obuhvata sve module, po jedan red za ulaz, konstantu, izlaz i unutrašnji signal. Ulazi i konstante se menjaju uživo; objašnjenja prikazuju puna imena, tipove i module. Obrađena vrednost različita od sirove prikazuje se posebno. Ako Const upravlja simuliranim ulazom, menjajte Const.

Promena ulaza/konstante uživo čuva istoriju. Strukturne i druge konfiguracione izmene mogu je resetovati. Jezik i modul menjaju samo pogled. Simulacija ne upravlja hardverom.

## 9. Izvoz, prevođenje i HAL integracija

1. Sačuvajte JSON projekat.
2. Izvezite `.comp`: ime počinje malim slovom i sadrži samo mala slova, cifre i donje crte, npr. `machine_plc.comp`.
3. **Build .so** ponovo izvozi graf na poslednju putanju i pokreće `halcompile --compile`.
4. Rezultat je `.so`, dnevnik `.build.txt`. Potrebni su LinuxCNC razvojni alati.

Prevodite za ciljnu arhitekturu: x86 modul ne radi na ARM64 Pi računaru. Editor ne instalira/učitava modul niti povezuje hardver. Jedna funkcija `update` sadrži sve module i Const ulaze. Stavite je u postojeći servo-thread posle hardverskog čitanja i pre hardverskog pisanja.

Ilustracija za već instaliranu komponentu i postojeći thread:

```hal
loadrt machine_plc
addf machine-plc.update servo-thread
setp machine-plc.gain 2.5
```

Koristite prava imena iz izvoza i povežite pinove. Input čita spoljni HAL pin; Const kreće od podrazumevane vrednosti i menja se preko `setp` ili signala.

## 10. Primeri

### Četiri bita u U32

Četiri bit ulaza povežite na n0…n3 četvorobitnog Math šablona. Za sopstvenu formulu izaberite bit promenljive i u32 rezultat:

```text
n0 + n1 * 2 + n2 * 4 + n3 * 8
```

n0=1, n1=0, n2=1, n3=0 daje 5.

### FIFO razlika

Float ulaz na FIFO, `now`/`last` na Math `now - last`. Za brzinu promene podelite i stvarnim periodom uzorkovanja.

### Podesivo pojačanje

Const `gain`, float, 2; Input `reading`, float; Math `x * @gain`; Output `scaled`, float. Reading povežite na x. Reading=4 daje 8; gain=3 daje 12 bez novih veza.

### Podela mašinske logike

Napravite module Ulazi, Podmazivanje i Vreteno, premestite čvorove i povežite ih u All modules. Monitor obuhvata sve, izvoz ostaje jedna komponenta. `examples/circular-direction.json` bira samo smer; potpuna izmena alata zahteva sekvencu, pamćenje stanja, senzore, kašnjenja i obradu grešaka.

## 11. Rešavanje problema

| Problem | Provera |
| --- | --- |
| Nema porta izraza | Izvor mora biti Input port; Constant i @reference nemaju portove. |
| Formula/tip/šablon zaključan | Prvo Disconnect all. |
| Crveno ime tipa | Proverite automatsku konverziju. |
| Čvor/veza se ne vidi | All modules, Fit i objašnjenje porta. |
| Const se ne briše / nepoznata referenca | Uklonite upotrebe / proverite tačno ime. |
| Netačno kašnjenje u simulaciji | Korak je 20 ms; HAL ima zaseban period. |
| Neispravan početni projekat | `--no-restore`, zatim ispravan fajl. |
| Prevođenje neuspešno | `.build.txt`, halcompile, imena fajlova/pinova. |
| FIFO povratna sprega odbijena | Ciklusi grafa nisu podržani. |
| Display ne zaustavlja NC | Poruka greške nije abort komanda. |

Sistemska/kompajlerska dijagnostika koristi svoj jezik. Katalozi su u `locales/`; nedostajući prevodi koriste engleski.

## 12. LinuxCNC 2.9 / 2.10

Trenutni razvojni API 2.10 piše izlaze pomoću `pin_set(value)` umesto `pin = value`. Izvoz pravi settere i uslovne makroe za starije 2.9 halcompile verzije. `bit`, `float`, `s32`, `u32` su još prihvaćeni, uz moguća upozorenja o zastarelim imenima.

Posle nadogradnje LinuxCNC ponovo izvezite i prevedite njegovim halcompile alatom. Stara `.so` to ne zamenjuje. Provere obuhvataju instalirano 2.9 prevođenje i C proveru sa trenutnim 2.10 generatorom/HAL/RTAPI zaglavljima; to nije test rada instaliranog 2.10 ni hardverski test.

## Logger: čuvanje istorije pomoću trigger ulaza

**+ Logger** ima 1–18 ulaza `in1`, `in2` itd. Tip (bit, float, s32, u32) automatski prati izvor; čuvaju se modul, simbol i naziv izlaza. Nepovezan ulaz daje float 0. Rastuća ivica `trigger` ulaza čuva kružni bafer, od najstarijeg uzorka. HIGH čuva jednom; pre novog okidanja vratite LOW. Čuvanje ne briše istoriju.

Period je pozitivan ceo broj milisekundi, može biti i `@constant`; bafer ima 1–100000 uzoraka. Najviše jedan uzorak po ažuriranju; simulacija radi na 20 ms. Trigger između uzorkovanja čuva postojeću istoriju. Bez uzoraka CSV/TSV ima samo zaglavlje, JSONL je prazan. CSV/TSV navodi nazive i tipove u zaglavlju, JSONL u svakom redu; `time_ms` je proteklo vreme. Format brojeva: `.0g`–`.17g`, `.0f`–`.17f`, `.0e`–`.17e`; celi brojevi ostaju tačni. Ime podržava `{timestamp}` (UTC), `{sequence}`, `{node}`. Fiksno ime atomski zamenjuje prethodnu datoteku. Izabrani format određuje sadržaj nezavisno od nastavka.

Relativne putanje koriste direktorijum sačuvanog projekta, inače direktorijum editora; u LinuxCNC direktorijum izvoza. Izvoz pravi `.comp`, `.logger.py`, `.logger.json`, `.hal`. Instalirajte komponentu kroz `halcompile`, pa učitajte `.hal` posle stvaranja `servo-thread`. On učitava komponentu, pokreće Python sakupljač sa LinuxCNC `hal` modulom i dodaje update. Zamenite ranije `loadrt`/`addf` redove. Držite datoteke zajedno; posle premeštanja ponovo izvezite zbog apsolutnih putanja.

Realtime nit šalje ograničene HAL zapise; sakupljač drži istoriju i piše van realtime niti. Mora raditi tokom uzorkovanja. Preliv može izgubiti uzorke/triggere; dodatno čuvanje tokom postojećeg čuvanja istog Loggera prijavljuje se i preskače. Rezultati/greške se vide u statusu simulacije ili na stderr sakupljača. Veći bafer troši više memorije. Primer: `examples/logger-history.json`.

Klik blizu veze bira žutu liniju, i pri udaljenom prikazu. Delete briše veze bez brisanja node-ova. Ctrl-klik bira više veza.

## Globalni I/O i Live HAL debug

**Globalni I/O** upravlja zajedničkim ulazima/izlazima u svim postojećim i novim modulima. Jedna definicija i jedan izvezeni pin po signalu. Položaj bloka pamti se po modulu; pomerajte okvir/naslov, uređujte dvostrukim klikom u listi. Običan Input/Output može postati globalan. Uklanjanje briše sve njegove veze. Globalni izlaz ima jedan izvor; raskinite staru vezu pre promene. Oznaka izvora ili **Idi do izvora** otvara modul i bira node.

**Izaberi HAL pin / signal** nudi pretragu i filtere tipa, smera i kompatibilnosti. **Osveži** asinhrono čita `halcmd -s show pin` i `halcmd -s show sig`. Prikazuje vrednost, HAL signal, izvor u projektu i ostale pinove signala. Katalog može da se učita/sačuva za offline rad. Tip se preuzima; uklanjanje dodele ostavlja pin za ručno povezivanje. Izlaz zahteva IN pin ili signal bez izvora. Postojeći netovi se koriste, povezani pinovi se ne premeštaju. Konflikti se odbijaju.

Izvoz pravi `.comp`, `.hal`, `.unload.hal`, `.test.hal`, `.test.unload.hal`, `.hal.json` i Logger pomoćnike. `.hal` učitava projekat, povezuje I/O, postavlja konstante, pokreće Logger i dodaje update u `servo-thread`. Učitajte posle stvaranja hardverskih/GUI pinova i niti, može i postgui. Motion/hardver ostaje u konfiguraciji mašine. `.test.hal` povezuje samo ulaze. Unload datoteke služe uspešno učitanim konfiguracijama; delimično neuspešan ručni start treba proveriti. Live greška starta automatski vraća završene korake.

**Debug** izvozi međupinove: `name.debug-n12-result`, FIFO `last`/`now`, PID `out`/`error`. Stabilni ID i manifest čuvaju mapiranje; normalan izvoz ih nema. **Live HAL test** i Simulate automatski grade/instaliraju debug kroz `halcompile --install` kao `nne_live_<uid>`. Potrebni su aktivan HAL, `servo-thread`, Python `hal` i razvojni alati. Instalacija traži dozvolu; već dozvoljen `sudo -n` može se koristiti, inače se sudo lozinka traži u skrivenom polju, bez čuvanja ili upisivanja u dnevnik. Greške su u statusu.

Samo ulazi su povezani sa mašinom. Komponenta računa realtime; Python HAL čita oko 20 Hz, bez paralelne Python simulacije. Dodeljeni ulazi su samo za čitanje; slobodni se podešavaju. Stop pre promene strukture. Kratki impulsi mogu izostati sa ekrana; Logger služi istoriji. Status prikazuje vreme i maksimum u µs i originalni `.update.time`. HAL jedinice zavise od backend-a; debug meri i nanosekunde preko `rtapi_get_time()`. Merenje obuhvata instrumentovano update telo, ne celu servo nit. Stop/izlaz uklanja test i njegove veze, postojeći signali ostaju. Otisak čeka pravi RT ciklus. Jedan test po Unix korisniku; instalirani modul se ponovo koristi, privremeni izvori se brišu. Live vrednosti ne prepisuju sačuvane simulacione vrednosti.

Ručno: `sudo halcompile --install name.comp`, zatim `halcmd -f name.hal`; za ulazni test debug izvoz i `name.test.hal`. Uklonite raniju instancu pre novog učitavanja; instalacija ne zamenjuje aktivni modul. RIP koristi svoje build okruženje. Primeri: `examples/global-io.json`, `examples/hal-catalogue.json` (primer kataloga).

Direktna Input → Output veza između spoljnih HAL veza istog tipa izvozi se kao HAL mreža. Pinovi komponente korišćeni samo za tu vezu se izostavljaju. Obrada, konverzija, unutrašnji pinovi ili različiti postojeći HAL signali zadržavaju prolaz kroz komponentu. Ulazi koji napajaju i unutrašnju logiku ostaju. Projekat sa samo direktnim vezama ne zahteva loadrt/addf. Debug zadržava pinove za posmatranje; Live test ulaza ne povezuje spoljne izlazne ciljeve.

Live HAL beleži vreme, rezultate izgradnje i instalacije, HAL komande i greške u `.state/logs/live-hal.log` (ili `PLC_STATE_DIR/logs/live-hal.log`). Putanja se prikazuje pri grešci. Rotacija: 1 MiB po datoteci, tri kopije. Lozinke se ne beleže. Izgradnja koristi privremeni direktorijum izvora umesto SSHFS direktorijuma.

## Counter – brojač

**+ Brojač**: ulazi `up`, `down`, `enable`, `reset` (`bit`); izlazi `count` (`s32`), `reached` (`bit`). Rastuće ivice dodaju/oduzimaju 1; istovremene ivice se poništavaju. HIGH u prvom ciklusu računa se kao ivica. Početna vrednost, prag i podrazumevana dozvola su podesivi, uključujući reference na konstante.

Nepovezani ulazi su LOW, osim `enable` (podrazumevana dozvola, početno uključena). Reset HIGH vraća početnu vrednost u svakom ciklusu, čak i kada je isključen. Isključenje zadržava vrednost. Ivice tokom reseta/isključenja se odbacuju; zadržan HIGH ne broji pri ponovnom uključenju. Zasićenje: −2147483648 do 2147483647. `reached = count >= prag` računa se svakog ciklusa, uključujući reset/isključenje, bez zadržavanja signala. Početna vrednost se čita pri pokretanju/resetu, prag svakog ciklusa. Ponovno pokretanje briše istoriju.

Primer: [counter.json](../examples/counter.json). U simulaciji prebacite `pulse-up` tri puta LOW/HIGH: vrednost 3, prag aktivan. `pulse-down` smanjuje na 2; `clear-count` vraća na 0. JSON, simulacija, `.comp` izvoz i debug monitori podržavaju oba tipa izlaza. Brzi fizički impulsi zahtevaju hardverski brojač/enkoder.
