## 2026-08-15 - Checksum filter
Ipoteza: majoritatea numerelor de 9 cifre gasite pe pagini web nu pot fi VAT-uri reale, deci pot filtra local.
Am rulat: vat_checksum.py pe 100.000 de numere consecutive.
Rezultat: 2.066 trec (2,1%).
Concluzie: checksum-ul elimina ~98% (mai exact 97.9%) din candidati gratuit, inainte de orice cerere la HMRC. Il aplic ca prim filtru in scriptul 03.


Greseli:
Una dintre greselile mele pe care ma bucur ca am observat-o relativ repede. In loc de coduri, am scris date calendaristice, deoarece am gresit coloana de pe care am cititi. Asta e exact tipul de bug care nu ma anunta niciodata. Daca nu m-as fi uitat la valori, ci doar la faptul ca „a mers", duceam numarul gresit pana in documentul final. De fapt, bug-ul era ca am folosit "names" in loc de use cols"

Din pacate codurile postale nu sunt mai "discriminante" decat numele. Presupunerea mea fiind exacr invers. Unele coduri postale au zeci de mii de firme, astea sunt adrese de firme de inregistrari si birouri virtuale. Insa nu totul a fost facut degeaba, nu abandonez codul postal, o sa il ponderez. Cod postal cu 1-20 de firme -> potrivire puternica, aproape decisiva, cod postal cu mii de firme-> ignora-l, decizia se ia doar pe nume


## 2026-08-15

De retinut:(ora 1:27) -> 
Cea mai utila constatare de pana acum: distributia codurilor postale.
E specifica, masurata, si schimba un pas din design (pasul 5).

3.893.238 companii in registru (snapshot Companies House 2026-08-01), dintre care 3.547.675 (91,1%) cu status "Active"
69,3% sunt dormante, micro sau n-au depus conturi -> prag TVA £90k,deci majoritatea n-au cum sa fie inregistrate
Top 20 coduri postale = 7,1% din registru; unul singur are 59.168 firme -> potrivirea pe adresa e inutilizabila pentru o felie mare, trebuie ponderata dupa frecventa




## 2026-08-16 - Construirea sample-ului

Decizie: doua straturi de cate 75.
  - 'all': aleator din toate companiile Active
  - 'trading': aleator din Active, minus DORMANT si NO ACCOUNTS FILED

De ce: 69,3% din registru e dormant/micro/fara conturi depuse. Un sample pur aleator ar fi dominat de firme care n-au cum sa aiba TVA, iar rata mea finala n-ar putea fi interpretata.
Cu doua straturi pot raporta ambele rate, iar diferenta dintre ele arata cat din "not found" e de fapt "not registered".

pool_all      = 3.547.675   (91,1% din cele 3.893.238 - restul de 8,9%
                             sunt in lichidare / administrare, nu "Active")
pool_trading  = 2.240.953   (63,2% din pool_all)
Suprapunere   = 0 companii  (asteptarea matematica era 0,0016 - deci normal)
Seed: 42




-----


## 2026-08-16 - Verificare de consistenta a filtrelor

Din registrul intreg: DORMANT (436.446) + NO ACCOUNTS FILED (985.311) = 1.421.757
Din pool_all am eliminat insa doar: 3.547.675 − 2.240.953 = 1.306.722
Diferenta: 115.035

Explicatie: sunt firmele dormante sau fara conturi care erau deja neactive,
deci excluse de primul filtru (CompanyStatus == "Active"). Cifrele se inchid.

De ce am facut verificarea: pentru ca am avut deja trei rezultate false care
n-au dat nicio eroare. Cand am doua numaratori care ar trebui sa se lege,
le leg - e cea mai ieftina plasa de siguranta din tot proiectul.



-----

## 2026-08-16-Iteratorul consumat

Am pus a doua bucla 'for' peste acelasi obiect 'reader' returnat de pandas.
Un iterator se parcurge o singura data: prima bucla il golise deja.

Rezultat: bucla nu s-a executat niciodata. Output: pool_all: 0, pool_trading: 0, exit code 0. Fara exceptie, fara avertisment.

Ca sa recitesc fisierul imi trebuie un pd.read_csv() nou, fisierul nu se "deruleaza inapoi".


----------



## Tipar observat 

Doua rezultate false care s-au manifestat, plus unul care nu a apucat:

1. names in loc de usecols -> pandas a mapat cele 3 nume pe ULTIMELE 3 coloane din 55, returnand date calendaristice. 
   Simptomul l-am vazut ca "coduri postale" care erau de fapt ConfStmtLastMadeUpDate.

2. Iterator consumat -> a doua bucla nu s-a executat deloc. exit code 0.

3. pool_all = pool_all.extend(...) -> .extend() returneaza None, deci lista ar fi devenit None. 
   Nu s-a manifestat niciodata, pentru ca era ascuns in spatele bug-ului 2. L-am gasit citind codul, nu rulandu-l.


In pipeline-ul asta modul dominant de esec nu e exceptia, e rezultatul plauzibil.
De aceea la pasul 5 verific ATRIBUIREA numarului, nu doar validitatea lui:
un VAT valid atasat companiei gresite este exact acelasi tip de esec, doar
ca la iesirea din sistem in loc de la intrare.


---------------





Predictie (16 aug, inainte de rulare): straturile 'all' si 'trading' se suprapun
in proportie de 63%, deci ma astept la rate apropiate. Daca iese asa, inseamna
ca factorul limitant nu e inregistrarea la TVA, ci disponibilitatea website-ului.


-------=


## 2026-08-16 19:41 - HMRC Check-a-VAT-number API: fara acces neautentificat

Ipoteza: tema listeaza API-ul HMRC ca fiind disponibil pentru verificari in masa ("also available as an API for bulk checks"). Verific daca e accesibil fara cont.

Am rulat: GET https://api.service.hmrc.gov.uk/organisations/vat/check-vat-number/lookup/123456782 (numar valid la checksum, deliberat nu al unei firme reale)

Am primit:
  fara header de versiune          -> 404 MATCHING_RESOURCE_NOT_FOUND
  Accept: ...hmrc.1.0+json         -> 404 MATCHING_RESOURCE_NOT_FOUND
  Accept: ...hmrc.2.0+json         -> 401 MISSING_CREDENTIALS
                                     "Authentication information is not provided"

Dovada bruta: evidence/hmrc_api_probe.txt (rulat 2026-08-16T19:41:32)

Concluzie: nu exista cale neautentificata catre API. Accesul cere inregistrare
pe HMRC Developer Hub, subscription la API si credentiale OAuth.

Consecinta pentru proiect: verificarea nu se poate face prin API in intervalul
disponibil. Trec pe checker-ul web public pentru cele 150 de companii.

Consecinta pentru Partea 3: la scara reala, verificarea devine blocajul
principal, nu crawling-ul. Accesul la API e primul lucru pe care l-as negocia
inainte sa promitem unui client livrarea.




------


## 2026-08-16 20:06 - Checker-ul web HMRC functioneaza si returneaza atribuirea

Am rulat: am introdus manual 406782879 la https://www.tax.service.gov.uk/check-vat-number/enter-vat-details

Am primit:
  "Valid UK VAT number"
  Registered business name:    UBER LONDON LIMITED
  Registered business address: ALDGATE TOWER FIRST FLOOR, 2LEMAN STREET,
                               LONDON, E1 8FA, GB

Dovada: evidence/hmrc_web_checker.png

Ce inseamna: checker-ul nu cere autentificare si NU returneaza doar valid/invalid,ci numele si adresa inregistrata. Asta e ce face posibila verificarea atribuirii, pot compara ce spune HMRC cu ce spune Companies House, in loc sa ma bazez doar pe faptul ca numarul e valid.

Fara aceasta proprietate, tot pasul 5 ar fi imposibil si n-as putea distinge un VAT corect de unul valid dar al altei firme.



---------


## 2026-08-16 20;10 - mod-9755 confirmat pe primul numar real

Implementasem ambele variante de checksum (mod-97 si mod-9755) pe motivul teoretic ca doar una respinge tacut numerele emise dupa ~2010. 
Am testat teoria pe primul numar real pe care l-am avut la indemana.

406782879 (UBER LONDON LIMITED, confirmat de HMRC):
  suma ponderata primele 7 cifre : 157
  + cifre de control              :  79
  = total                         : 236

  236 % 97        = 42  -> PICA mod-97
  (236 + 55) % 97 =  0  -> TRECE mod-9755

Un numar real, valid, confirmat de administratia fiscala britanica pica algoritmul
mod-97 - cel prezentat ca "algoritmul de checksum UK" in majoritatea surselor.

Daca implementam doar mod-97, l-as fi aruncat la pasul 3, fara eroare si fara avertisment. 

Ar fi fost al patrulea rezultat tacut si fals din proiect si singurul care ar fi coborat direct rata mea de acoperire, facand sursa sa paramai slaba decat e.

De retinut pentru document: costul de a implementa ambele variante e de 3 linii.
Costul de a implementa una singura nu se vede niciodata in output.




---------


## 2026-08-16 - Decizie: verificare manuala pentru PoC

Optiuni:  
  A) automatizez formularul web HMRC (sesiune + token CSRF) - ~60-90 min, risc de a nu iesi, si trimit cereri automate catre un serviciu guvernamental
  B) verific manual cei ~20-40 de candidati rezultati din sample-ul de 150 ~20 min, zero risc

Am ales B.

Motivul nu e doar timpul: la scara reala (2M de numere), NICIUNA din variante nu tine. 
2 milioane de cereri automate catre un formular guvernamental nu e o solutie tehnica, e un abuz, ar fi blocat in cateva ore si ar expune firma la risc reputational.

Deci automatizarea formularului n-ar fi demonstrat nimic despre scalabilitate.
Constatarea reala e ca verificarea, nu crawling-ul, e blocajul: singura cale care scaleaza e accesul autorizat la API-ul HMRC. 
Asta e primul lucru pe care l-as negocia inainte sa promitem unui client livrarea.



--------


## 2026-08-16 20:29 - sample.csv construit

150 companii (75 'all'  + 75'trading'), seed 42, salvate in data/sample.csv.

Distributia cate firme impart codul postal, in sample:
  min 1 | 25% = 3 | mediana 9 | 75% = 150 | max 59.168 | media 2.393

Media (2.393) e de 266× mediana (9) - distributia e dominata de cateva adrese de birouri virtuale. 
Raportez mediana; media nu descrie nimic real aici.

Consecinta pentru pasul 5: pentru ~50% din sample adresa identifica firma
(≤9 firme la acelasi cod). Pentru ~25% e inutila (>150). Pragul ales: 20.
Nu e ales arbitrar, ci vine din distributia masurata a sample-ului.





-------





## 2026-08-16 20:45 - Pasul 2: gasirea website-urilor (design, inainte de rulare)

Problema: Companies House nu are camp de website. Nimeni nu mentioneaza asta
in tema, dar fara el nu am ce crawla. E blocajul real al proiectului.

Metode considerate:
  - API comercial de cautare (Bing/Google): ~$5/1000 query-uri.
    La 4,2M companii = ~$21.000 doar pentru descoperirea domeniilor. Fara buget.
  - Common Crawl: EXCLUS. Indexul e organizat pe domeniu si URL, nu pe nume de companie.
    Nu exista cale directa nume->domeniu fara cautare full-text peste petabytes. Util la pasul 3 (daca am deja domeniile), inutil la pasul 2.
  - Ghicire din nume + verificare: ales. Zero cost,zero blocare.



Cum verific ca domeniul e al firmei corecte:

  O companie UK e obligata prin lege (Companies Act 2006) sa-si afiseze numarul
  de inregistrare pe site. Numarul ala e exact cheia mea primara din Companies
  House. Deci caut numarul in pagina:
    gasit numarul -> potrivire aproape sigura  (matched_by = company_number)
    gasit numele  -> semnal slab, firme cu nume similare exista (company_name)
  Cele doua raman coloane separate; la pasul 5 nu au aceeasi greutate.

De ce conteaza: daca atribui domeniul gresit unei companii, tot ce urmeaza e gresit dar arata corect. 
Ar fi al cincilea rezultat plauzibil-si-fals, de data asta la scara intregului pipeline.

Buget: max 6 domenii candidate per companie (150 × 6 = 900 incercari).
Filtru DNS inainte de HTTP - 20ms vs 1-3s. Acelasi principiu ca la checksum:
filtrul ieftin si local inaintea celui scump si remote.

Predictie inainte de rulare: ma astept la o rata de confirmare mica, undeva sub 25%, pentru ca multe firme mici din registru probabil nu au deloc site.
Ma astept ca `no_dns` sa fie cel mai frecvent rezultat.

REZULTATE (dupa rulare):
  outcome:     found 30 | no_match 52 | no_http 14 | no_dns 54
  matched_by:  company_number 5 | company_name 25
  crosstab:    all 13/75 (17,3%) | trading 17/75 (22,7%)
  timp:        8,6 min pentru 150 de companii (3,44 s/companie)

Predictia s-a confirmat: diferenta intre straturi +5,3 pp, eroare standard
6,5 pp, z = 0,82 -> nesemnificativa. Factorul limitant e disponibilitatea
website-ului, nu inregistrarea la TVA.


Pe primele 20: 0 potriviri prin numarul de inregistrare, 3 prin nume.
Cauza: fetch() descarca doar pagina principala, iar numarul de inregistrare
apare de obicei in subsolul paginilor /contact, /about sau /terms.
Decizie: mut verificarea prin numarul companiei la pasul 3, unde oricum
descarc mai multe pagini per domeniu. Numarul gasit acolo ridica retroactiv
increderea in atribuirea domeniului, fara cereri suplimentare.



---------



## 2026-08-16 - Extrapolare la scara (material pentru Partea 3)
Masurat pe 20 de companii: 0,8 min -> 2,4 s per companie, un laptop, un fir.

La 3.547.675 companii activr:
  99 zile secvential | 2 zile cu 50 de lucratori | 0,5 zile cu 200
  21.286.050 de interogari DNS (6 candidati × 3,55M)
  ~846 GB trafic doar pentru homepage-uri

Ce se rupe primul: NU crawling-ul, ci DNS-ul. Niciun resolver public nu accepta 21M de interogari, te limiteaza sau te blocheaza in cateva ore.
Ar fi nevoie de resolver recursiv propriu, cu cache. E o cerinta de infrastructura pe care abordarea "as folosi un crawler distribuit" o rateaza.

Al doilea lucru care se rupe: 36% din companii n-au niciun domeniu care rezolva (54 din 150, masurat). Pentru ele nu e o problema de buget, nu exista ce crawla. Orice suma cheltuita pe crawling se loveste de plafonul asta.





-------



## 2026-08-16 - Common Crawl:exclus pentru pasul 2

Ipoteza:daca numerele de TVA sunt imprastiate pe milioane de pagini, poate un corpus web e forma corecta in loc de crawling site cu site (tema sugereaza asta la "Bulk web corpora").

De ce l-am exclus fara sa scriu cod: indexul Common Crawl e organizat pe domeniu si URL, nu pe nume de companie. 
Nu exista o cale directa nume_companie -> domeniu. 
Ar fi nevoie de cautare full-text peste petabytes, ceea ce depaseste un laptop si oricum ar costa mai mult decat un API de cautare comercial.

Concluzie: Common Crawl e util la pasul 3 (daca am deja domeniile, pot lua paginile din corpus in loc sa le descarc), dar nu rezolva pasul 2, care e blocajul real. Nu am investit timp in el.






-----




## 2026-08-16 21:59 - Pasul 2: rezultate pe 150

Timp: 8,6 min -> 3,44 s/companie (revizuit fata de 2,4 s estimat pe 20).

Palnia:
  no_dns    54  (36,0%)  niciun domeniu candidat nu exista
  no_match  52  (34,7%)  domeniul exista, pagina nu e a firmei
  no_http   14  (9,3%)  DNS rezolva, dar nu serveste pagina
  found     30  (20,0%)  confirmat   [IC 95%: 13,6% – 26,4%]

Confirmate prin: nume 25 | numarul companiei 5

FALS POZITIV LA NIVEL DE DOMENIU:
  82 de pagini au fost efectiv descarcate (found + no_match).
  Doar 30 apartineau companiei cautate.
  -> 63,4% dintre domeniile "care merg" sunt ale altcuiva.
  Fara verificare as fi raportat 55% acoperire, din care aproape doua treimi
  false. Un numar mare si fals in loc de unul mic si corect.

PREDICTIA (scrisa inainte de rulare) - CONFIRMATA:
  all     13/75 = 17,3%
  trading 17/75 = 22,7%
  diferenta+5,3 pp, eroare standard 6,5 pp, z = 0,82 ->nesemnificativa

  Eliminarea firmelor dormante si fara conturi (37% din registru) NU imbunatateste semnificativ rata. 
  Factorul limitant nu e cine e inregistrat la TVA,ci cine are website. Bugetul de crawling nu rezolva asta.

Extrapolare actualizata: 3,44 s/companie × 3.547.675 = 141 zile secvential,
0,7 zile cu 200 de lucratori paraleli.




--------



## 2026-08-16 21:20 - Pasul 3: extragerea (design, inainte de rulare)

Vizitez doar cele 30 de domenii confirmate la pasul 2, cate 8 pagini fiecare
(/, /contact, /about, /terms, /privacy ...), nu doar homepage-ul. Motivul e
constatarea de la pasul 2: 0 potriviri prin numarul de inregistrare pe
homepage-uri, pentru ca detaliile de inregistrare stau in subsolul paginilor
secundare.

Doua rute de extragere, pentru ca site-urile scriu numarul in ambele feluri:
  - prefix explicit GB (ex. "GB123456782")
  - cuvantul VAT urmat de cifre in urmatoarele ~80 de caractere
    (ex. "VAT Registration Number: 406 7828 79")
Al doilea prinde numerele scrise cu spatii, care sunt majoritatea.

Filtrul de lungime (exact 9 cifre) elimina gratis numerele de telefon britanice, care au 10-11 cifre. Checksum-ul filtreaza restul.

Pastrez ±100 de caractere de context pentru fiecare candidat. Fara ele nu pot analiza fals pozitivele la pasul 5, iar analiza aia e jumatate din Partea 2.

Caut si numarul Companies House pe aceleasi pagini. Nu e tinta, dar daca apare, ridica retroactiv increderea in atribuirea domeniului. 25 din cele 30 de domenii au fost confirmate doar prin nume, semnal slab.

Ce ma astept: putine numere. Cele mai multe firme mici nu-si publica VAT-ul.
Ma astept si la fals pozitive de atribuire - VAT-uri valide care apartin agentiei web, firmei-mama sau unui partener citat pe pagina. 
Testul meu pe HTML sintetic a produs a produs deja exact acest caz.

Predictie: sub 15 companii cu cel putin un VAT valid la checksum, din 30.



--------




## 2026-08-16 21:46 Pasul 3: rezultate

Timp: 17,3 min pentru 30 de domenii = 35 s/domeniu, 12,7 s per pagina servita.

Palnia completa:
  150 companii -> 30 cu domeniu (20,0%) -> 3 cu VAT candidat
  acoperire finala 2,0%  [IC 95% Wilson: 0,7% – 5,7%]
  dintre domeniile confirmate: 10,0%  [IC 95%: 3,5% – 25,6%]

Cu 3 rezultate din 150, intervalul e prea larg pentru o estimare precisa.
Raportez intervalul, nu punctul.

IPOTEZA MEA DESPRE PAGINILE SECUNDARE, NETESTATA, NU INFIRMATA:
  Mutasem verificarea prin numarul companiei la pasul 3 presupunand ca
  detaliile de inregistrare stau pe /contact, /about, /terms.
  Rezultat: 3/30 domenii cu numarul companiei, fata de 5/30 pe homepage-uri.
  Cauza reala: din 240 de cai incercate, doar 82 au servit ceva (34%).
  Site-urile nu-si numesc paginile dupa tiparele pe care le-am ghicit eu.
  Ce as face altfel: descarc homepage-ul, extrag link-urile, si urmez pe
  cele care contin "contact"/"about"/"terms". Schimbare de design, nu
  de parametru.

CHECKSUM-UL: 18 din 18 candidati trec (100%).
  Asteptam ~2% daca ar fi numere la intamplare. Probabilitatea ca 18 numere
  aleatorii sa treaca toate: 6×10⁻³¹.
  Deci checksum-ul NU a filtrat nimic aici, extragerea era deja precisa
  (cerinta de proximitate cu "VAT"/"GB" face toata treaba).
  Rolul lui s-a schimbat din filtru in confirmare statistica a preciziei.
  La scara, cu extragere permisiva (orice 9 cifre de pe pagina), ar redeveni
  filtrul principal. Valoarea unui filtru depinde de cat de strans e pasul
  dinaintea lui.

18 candidati pentru 3 companii = duplicate (acelasi numar gasit de ambele
rute si pe mai multe pagini




-----



## 2026-08-16 22:00 - Ce am gasit citind candidates.csv

3 numere distincte in 18 randuri. Restul sunt duplicate: acelasi numar gasit pe pagini diferite si de ambele rute de extragere. 
Deduplicare obligatoriem inainte de pasul 4, o sa verific 3 numere la HMRC, nu 18.

Atribuire, din context:
  1. "Company number: 03047290 | VAT registration number: GB630 968 620"
  2. "Company number: 11498172 | VAT number: 339 2179 84 ... Enviro Clean Group LTD" -> in ambele, cei doi identificatori apar LIPITI in acelasi subsol.
       E cea mai buna dovada de atribuire gasibila pe o pagina.
  3. "...gistration Number GB 413 4733 74 Website by Melt Design"->  niciun numar de companie in context, iar imediat dupa VAT vine
       creditul agentiei web.

Al treilea e tiparul de risc pe care il anticipasem teoretic, aparut pe date reale: un VAT si numele unei agentii web in aceeasi fraza. Aici numarul e
probabil al firmei, dar extractorul nu are cum sa distinga. 
Daca agentia isi punea propriul VAT acolo, iesea identic.

De aici: proximitatea fata de numarul Companies House e un semnal de incredere mult mai bun decat simpla prezenta a unui VAT valid pe pagina. La pasul 5 o sa tratez diferit cele doua cazuri.

BUG gasit citind datele: contextele contin JavaScript si CSS ({""prefetch"":[{""source"":""document""...}). re.sub(r"<[^>]+>") scoate tag-urile, dar nu continutul dintre <script> si <style>.
N-a produs un fals pozitiv aici, dar un fisier JS cu 9 cifre langa "vat" ar fi fost extras ca text vizibil. 
Fix aplicat: elimin blocurile script/style inainte de tag-uri.


------


## 2026-08-16 22:05  Pasul 5: un fals pozitiv de atribuire, prins

Trei candidati verificati manual la checker-ul HMRC:

  630968620 -> CERTIKIN INTERNATIONAL LTD, OX29 0AX
              CH: CERTIKIN INTERNATIONAL LIMITED, OX29 0AX (9 firme la cod)
              nume 1.000, cod postal identic -> CONFIRMED

  339217984 -> ENVIRO CLEAN GROUP LTD, DA9 9UZ
              CH: ENVIRO CLEAN GROUP LTD, CM15 9SG (127 firme la cod)
              nume 1.000, cod postal DIFERIT -> CONFIRMED pe nume

  413473374 -> HIGH LEVEL PHOTOGRAPHY LTD, KT11 2SF
              CH: HIGH LEVEL LIMITED, GU21 2EP (171 firme la cod)
              nume 0.625, cod postal diferit -> MISMATCH

FALS POZITIV PRINS (High Level):
  Compania din sample e HIGH LEVEL LIMITED. Domeniul highlevel.co.uk a fost confirmat la pasul 2 doar prin nume. Nimarul de TVA de pe el e valid,trece checksum-ul, iar HMRC il confirma  dar apartine unei ALTE firme, HIGH LEVEL PHOTOGRAPHY LTD.
  Daca ma opream la "numarul e valid?", il livram. Ar fi aratat perfect.

SEMNALUL company_number_on_site A PREZIS TOATE TREI:
  Certikin     True  -> CONFIRMED
  Enviro Clean True  -> CONFIRMED
  High Level   False -> MISMATCH

  Site-urile care isi afisau numarul Companies House langa VAT au fost corecte; cel care nu-l afisa a fost gresit. n=3, deci e o observatie, nu o regula dovedita, dar merita propusa ca filtru de productie.

DECIZIA DR PRAG, VALIDATA ACCIDENTAL:
  Enviro Clean are cod postal diferit intre HMRC si Companies House. Adresa de inregistrare TVA nu e obligatoriu sediul social. sunt registre separate.
  Daca regula ar fi fost "nume SI cod postal", as fi respins o potrivire corecta. Regula "nume ≥ 0,85 e suficient singur" a salvat cazul.



--------




## 2026-08-17 13:00 - Rezultat final

Palnia completa, 150 de companii:
  150 in sample
   30 cu domeniu confirmat        (20,0%)  [IC 95%:13,6–26,4%]
    3 cu VAT candidat
    2 CONFIRMED                   (1,3%)  [IC 95% Wilson:0,4–4,7%]
    1 MISMATCH
  147 NOT_FOUND

Fals pozitive: 1 din 3 candidati decisi. Cu n=3 raportez numarul, nu procentul -
"33%" sugereaza o precizie pe care trei observatii nu o sustin.

Pe straturi (n prea mic pentru concluzii): ambele CONFIRMED in 'trading',
MISMATCH-ul in 'all'. Nu trag nicio concluzie din asta.

Ce NU surprind numerele mele;
  - daca cele 147 NOT_FOUND sunt firme neinregistrate la TVA sau esecuri ale
    pipeline-ului. Cel mai probabil majoritatea sunt primul caz - 36% n-au
    avut niciun domeniu care rezolva.
  - data reala de fals pozitiv. 1 din 3 e un accident statistic, nu o masura.
  - cazuri pe care nu le-am intslnit: grupuri de firme, francize, firme cu
    VAT-ul afisat doar in PDF-uri sau imagini.
