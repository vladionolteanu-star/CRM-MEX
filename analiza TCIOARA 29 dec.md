# Analiza TCIOARA 29 dec

## Feedback & Feature Requests

### 1. Informații Suplimentare în Tabel
- **Cubaj / MP**: Necesitatea afișării informațiilor despre volum (m³) sau suprafață (mp).
- **Data Primei Intrări**: Adăugare în capul de tabel a datei primei intrări (momentan informația nu există în DB).

### 2. Vizualizare și Alerte Lead Time
- **Alertă Acoperire**: Evidențierea diferenței dintre *Lead Time* și *Zile Acoperire*.
- **Font Roșu**: Dacă diferența este mai mică de 10 zile (Lead Time vs Zile Acoperire), textul trebuie să fie roșu.

### 3. Agregare Date UI/UX
- **Vedere Trimestrială**: Pe lângă datele granulare (Oct, Nov, Dec), utilizatorul dorește vizualizarea datelor agregate pe trimestru în UI.

### 4. Management Comenzi în Tranzit
- **Feature Import Comenzi**:
    - *Problemă*: Informațiile referitoare la comenzile în tranzit nu sunt importate corect din fișierul inițial.
    - *Soluție*: Adăugare funcționalitate în **Settings** pentru import comenzi.
    - *Structură necesară*: `Cod articol`, `Cantitate comandată`, `Data comandată`, `Data estimată de livrare`.
    - **Impact Formule**: Datele importate (în special Data Estimată Livrare) trebuie să impacteze formulele de calcul.
    - **Editare**: Posibilitatea de a edita aceste date importate.

### 5. Calcul Cantități Sugerate și Costuri
- **Coloane Noi Necesare în Tabel**:
    1. **Cantitate Sugerată (cu tranzit)**: Calcul ce include marfa în tranzit și ține cont de data estimată de livrare.
    2. **Cantitate Sugerată (fără tranzit)**: Calcul ce ignoră marfa în tranzit.
    3. **Cost Estimat Comandă**: Adăugare coloană cu valoarea estimată.
- **Editabilitate**: Formula/valoarea pentru cantitatea sugerată trebuie să fie editabilă la nivel de celulă (interacțiune stil Excel).

### 6. Data Chat & AI Contextual
- **Data Chat (Feature Separat)**: Funcționalitate distinctă unde utilizatorul poate interoga sistemul în limbaj natural (ex: "în aprilie am nevoie să vând 4k de buc din familia x campanie etc").
- **Interfață AI**: 
    - Butonul de AI trebuie să deschidă o fereastră de **chat**.
    - **Indicator de Context**: Să afișeze cât context are modelul.
    - **Interactivitate**: Să permită rafinarea comenzii finale către furnizor prin dialog, nu doar să ofere un output static de tip "chain of thoughts".

### 7. Logică de Business, Filtrare și Raportare
- **Filtrare pe Subclasă**: Feature esențial. Logica de business dictează că nu se comandă "secțiunile" din tool, ci se comandă **toată colecția** (subclasa) de la un furnizor.
- **Vizualizare Top Urgențe**: Necesitatea unei vizualizări aggregate (Top pe Subclasă/Furnizori) pentru a identifica rapid furnizorul care "țipă" cel mai tare că are nevoie de marfă. Vizualizarea curentă la nivel de SKU (mii de linii) introduce prea mult zgomot ("too much noise"). PREFRABIL DRAG AND DROP SUBCLASA SI DE LUCRAT COMANDA LA NIVEL DE SUBCLASA
- **Dead Stock**:
    - Introducere caracteristică `Dead Stock` la nivel de articol.
    - Logica: Articolele *Long Tail* nu se reaprovizionează.
    - *Notă Tehnică*: Tool-ul actual nu mapează corect coloanele de vânzări din sursă.
