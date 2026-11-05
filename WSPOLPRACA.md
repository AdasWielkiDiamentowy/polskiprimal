# Współpraca — jak bezpiecznie dodawać treści (Git + S3)

Ten dokument jest dla całego zespołu (autorzy treści: primal, keto, zioła, wywiady).
Opisuje **jak dodawać i zmieniać treści strony polskiprimal.pl** tak, żeby:

1. każda zmiana była zapisana w **Git/GitHub** (historia, cofanie, współpraca),
2. gotowe treści trafiały trwale do **Amazon S3** (to, co widzą użytkownicy na żywo).

> Zasada w jednym zdaniu: **Git = wersje i historia tekstu. S3 = publikacja na żywo.**
> Najpierw zapisujemy zmianę w Git, potem publikujemy ją do S3 jedną komendą na serwerze.

---

## 0. Role — kto co robi

| Rola | Gdzie pracuje | Co robi |
|------|---------------|---------|
| **Autor treści** (Ty i współpracownicy) | na swoim komputerze / GitHub | pisze i edytuje pliki JSON/Markdown w folderze `content/`, wysyła do GitHub |
| **Osoba publikująca** (admin serwera) | terminal Lightsail (serwer) | pobiera zmiany z GitHub i publikuje je do S3 |

Autor **nigdy** nie musi wchodzić na serwer. Publikująca osoba **nigdy** nie pisze treści ręcznie w S3.

---

## 1. Gdzie leżą treści

Wszystkie treści to zwykłe pliki w folderze `content/`:

```
content/
  categories/        # kategorie (menu / działy strony)
    _index.json      # KOLEJNOŚĆ i lista kategorii — ważny plik
    cat-keto.json    # jedna kategoria = jeden plik
    ...
  blog/              # wpisy blogowe
    _index.json      # lista wpisów (tytuł, status, data) — ważny plik
    post-witaj.json  # jeden wpis = jeden plik
    ...
  config/
    theme.json       # kolory i wygląd strony
```

Edytujesz te pliki, zapisujesz w Git, a osoba publikująca wgrywa je do S3.

---

## 2. Dziennik komend — AUTOR TREŚCI (na swoim komputerze)

Robisz to raz przy starcie, a potem powtarzasz pętlę „edytuj → zapisz → wyślij".

### 2A. Pierwsze uruchomienie (jednorazowo)

| Krok | Komenda | Co robi |
|------|---------|---------|
| Pobierz projekt | `git clone <ADRES-REPO-GITHUB> polskiprimal` | ściąga cały projekt na Twój komputer |
| Wejdź do folderu | `cd polskiprimal` | wchodzisz do projektu |
| (opcjonalnie) podgląd | `docker compose up --build` | uruchamia stronę lokalnie na `http://localhost` z treścią z `content/` |

> Lokalny podgląd nie potrzebuje konta AWS — używa trybu „in-memory" i pokazuje dokładnie
> to, co masz w folderze `content/`. Zatrzymujesz go `Ctrl+C`.

### 2B. Pętla codziennej pracy (za każdym razem)

| Krok | Komenda | Co robi |
|------|---------|---------|
| 1. Pobierz najnowsze | `git pull` | ściąga zmiany kolegów, żeby nie było konfliktów |
| 2. Edytuj pliki | *(edytor tekstu)* | tworzysz/zmieniasz plik `.json` w `content/` (wzory w sekcji 4) |
| 3. Zobacz co zmieniłaś/eś | `git status` | pokazuje listę zmienionych plików |
| 4. Dodaj konkretne pliki | `git add content/blog/post-nowy.json` | wybierasz pliki do zapisania (lepiej konkretnie niż `git add .`) |
| 5. Zapisz wersję (commit) | `git commit -m "Dodaję wpis o keto"` | zapisuje zmianę w historii z opisem |
| 6. Wyślij na GitHub | `git push` | wysyła zmianę do wspólnego repozytorium |

Po kroku 6 Twoja zmiana jest bezpieczna w Git i widoczna dla reszty zespołu.
**Jeszcze nie jest na żywo** — publikuje ją osoba z sekcji 3.

> Wskazówka: rób małe, częste commity z jasnym opisem (`-m "..."`). Łatwiej wtedy
> cofnąć pojedynczą zmianę, jeśli coś pójdzie nie tak.

---

## 3. Dziennik komend — OSOBA PUBLIKUJĄCA (terminal serwera Lightsail)

Wchodzisz przez **Connect using SSH** w panelu Lightsail. Robisz to, gdy chcesz wypchnąć
zatwierdzone treści z GitHub na żywą stronę (do S3).

| Krok | Komenda | Co robi |
|------|---------|---------|
| 1. Wejdź do projektu | `cd polskiprimal` | wchodzisz do folderu aplikacji |
| 2. Pobierz zmiany | `git pull` | ściąga nowe treści z GitHub na serwer |
| 3. Przebuduj aplikację | `docker compose up -d --build` | aktualizuje działającą stronę |
| 4. Opublikuj do S3 (dodaj nowe) | `docker compose exec app python -m app.seed` | wgrywa **tylko nowe** pliki; **nie nadpisuje** istniejących |
| 5. Sprawdź, że żyje | `curl -I https://polskiprimal.pl/health` | `200` = działa |
| 6. Sprawdź logi (jeśli coś nie tak) | `docker compose logs --tail=30 app` | pokaże ewentualny błąd S3 |
| 7. cd ~/polskiprimal
| 8. git pull
| 9. aws s3 sync content/ s3://polskiprimal/ --region eu-north-1


### Uwaga o nadpisywaniu — bardzo ważne

#### Dlaczego w ogóle jest ten podział?

Wyobraź sobie, że S3 to witryna sklepowa — to, co widzą klienci.
Git to magazyn z zapasami — tu przechowujesz oryginały.

Komenda `seed` bez żadnych opcji pyta S3: „czy ten plik już masz?" — i jeśli tak, **omija go**.
Dlaczego? Bo w S3 mogły być zmiany zrobione ręcznie przez kogoś innego, a `seed` nie chce ich
przypadkowo zniszczyć. To bezpieczne domyślne zachowanie.

Problem: gdy **zmieniłaś/eś istniejący plik** (np. dodałaś/eś podkategorie do `cat-biedronka.json`),
zwykłe `seed` widzi, że plik już istnieje w S3 i go **pomija** — dlatego napisało „0 objects wrote".
Twoja zmiana była w Git, ale nie trafiła do S3, bo S3 już miał starą wersję tego pliku.

**Rozwiązanie — flaga `--overwrite`:**
Mówi komendzie: „nie pytaj, czy plik już istnieje — zastąp wszystko wersjami z Git".

```bash
docker compose exec app python -m app.seed              # BEZPIECZNE: dodaje tylko NOWE pliki (istniejące pomija)
docker compose exec app python -m app.seed --overwrite  # NADPISUJE wszystko w S3 wersjami z Git
```

**Kiedy używać czego:**
- Dodajesz **nowy** plik (nowy wpis, nowa kategoria) → zwykłe `seed` wystarczy
- **Zmieniłaś/eś istniejący** plik (edytowałaś/eś np. `cat-biedronka.json`) → musisz użyć `--overwrite`
- Nie jesteś pewna/pewny, które pliki są nowe, a które zmienione → `--overwrite` jest bezpieczny,
  **o ile trzymasz się zasady że treść zmieniasz tylko w Git**, nie ręcznie w S3

> Złota zasada: **zmień w Git → wyślij na GitHub → na serwerze `git pull` + `seed --overwrite`**.
> Wtedy `--overwrite` nigdy niczego nie zniszczy, bo Git jest jedynym źródłem prawdy.

---

## 4. Wzory plików (skopiuj i zmień)

### 4A. Nowy wpis blogowy

Utwórz plik `content/blog/post-<nazwa>.json`:

```json
{
  "id": "post-moj-wpis",
  "slug": "moj-wpis-adres-w-url",
  "title": "Tytuł wpisu widoczny na stronie",
  "category_id": null,
  "body_md": "## Nagłówek\n\nTreść wpisu w **Markdown**.\n\n- punkt pierwszy\n- punkt drugi",
  "author": "Imię Autora",
  "status": "published",
  "published_at": "2026-11-01T09:00:00Z"
}
```

Pola:
- `id` — unikalny, taki sam jak nazwa pliku bez `.json` (np. `post-moj-wpis`).
- `slug` — adres w URL (małe litery, myślniki, bez spacji i polskich znaków).
- `body_md` — treść w Markdown. Nowa linia to `\n` wewnątrz tekstu.
- `status` — `"published"` (widoczny) albo `"draft"` (szkic, ukryty przed użytkownikami).
- `published_at` — data w formacie `RRRR-MM-DDTHH:MM:SSZ`; dla szkicu może być `null`.

**Potem dopisz wpis do** `content/blog/_index.json` (to jest lista wszystkich wpisów):

```json
"post-moj-wpis": {"slug": "moj-wpis-adres-w-url", "title": "Tytuł wpisu widoczny na stronie", "status": "published", "published_at": "2026-11-01T09:00:00Z"}
```

> Jeśli nie dopiszesz wpisu do `_index.json`, nie pojawi się na liście bloga.

### 4B. Nowa kategoria

Utwórz plik `content/categories/cat-<nazwa>.json`:

```json
{
  "id": "cat-zioła",
  "slug": "ziola",
  "title": "Zioła",
  "parent_id": null,
  "order": 6,
  "description_md": "Krótki opis działu w Markdown."
}
```

Pola:
- `parent_id` — `null` dla kategorii głównej, albo `id` kategorii-rodzica dla podkategorii.
- `order` — kolejność wyświetlania (mniejsza liczba = wyżej).

**Potem dopisz `id` kategorii do** `content/categories/_index.json` (lista i kolejność):

```json
{
  "ids": ["cat-skladniki", "cat-biedronka", "cat-zakupy", "cat-keto", "cat-cukier", "cat-zioła"]
}
```

> Jeśli nie dopiszesz `id` do `_index.json`, kategoria nie pojawi się w menu.

---

## 5. Jak cofnąć błąd (Git)

| Sytuacja | Komenda |
|----------|---------|
| Chcę zobaczyć historię zmian | `git log --oneline` |
| Zepsułem/am plik, chcę wrócić do ostatniej zapisanej wersji | `git checkout -- content/blog/post-x.json` |
| Chcę zobaczyć, co dokładnie zmieniłem/am | `git diff` |

> Dopóki treść jest w Git, nic nie jest naprawdę stracone — zawsze można wrócić do
> wcześniejszej wersji.

---

## 6. Złota zasada bezpieczeństwa

- **Nigdy** nie wysyłaj do Git pliku `.env` ani kluczy AWS. Plik `.env` jest już w
  `.gitignore` i ma zostać tylko na serwerze.
- Treści zmieniamy w `content/` i przez Git — **nie** ręcznie w S3.
- Publikacja do S3 odbywa się tylko komendą `seed` na serwerze (sekcja 3).

---

## 7. Ściąga — najkrótsza wersja

**Autor (swój komputer):**
```bash
git pull
# ...edytuj pliki w content/...
git add content/<twoj-plik>.json
git commit -m "opis zmiany"
git push
```

**Publikujący (serwer Lightsail):**
```bash
cd polskiprimal
git pull



## 8 - Pisanie w json
Structure

{ } — curly braces wrap the whole object
"key": "value" — every field is a key-value pair
, — comma after every line except the last one
Values

"text" — text always in double quotes
1 — numbers without quotes
null — empty/missing value, no quotes
true / false — boolean, no quotes
Text content (body_md field)

\n — new line
\n\n — empty line (paragraph break)
**bold** — bold text
## Nagłówek — heading
- punkt — bullet point
File and folder names in S3 (image_url)

only lowercase letters: a-z
numbers: 0-9
hyphens: -
slashes for folders: /
❌ no Polish characters: ą ę ó ł ź ż ć ń ś
❌ no spaces
❌ no uppercase
docker compose up -d --build
docker compose exec app python -m app.seed --overwrite  # dodaje nowe I aktualizuje zmienione
curl -I https://polskiprimal.pl/health
```

> Jeśli dopiero dodajesz nowe pliki (nic nie edytowałaś/eś), możesz pominąć `--overwrite`.
> W razie wątpliwości — `--overwrite` jest bezpieczny, gdy trzymasz się zasady „tylko Git, nie S3 ręcznie".
