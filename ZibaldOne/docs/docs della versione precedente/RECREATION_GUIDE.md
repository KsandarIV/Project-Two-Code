# 🎮 RECREATION DOMAIN - Guida Completa

## Overview

Il `recreation_domain` è stato completamente riprogettato per supportare:
- **Categorie predefinite**: Book, Anime, VideoGame, TVSeries, Sport, Movie, TabletopGame
- **Componenti generici**: Counter, Progress, Bookmark, Rating, Tags
- **Categorie custom**: L'utente può aggiungere qualsiasi hobby personalizzato
- **Tracking granulare**: Tempo, progresso, bookmark, rating per ogni item

---

## Componenti Base

### 1. Recreation_Counter
Traccia il progresso con limite opzionale.

```python
counter = Recreation_Counter()

counter.counter_current_value_integer = 150  # Es: pagine lette
counter.counter_target_limit_integer = 300   # Target (es: pagine totali)
counter.counter_is_unlimited_boolean = False
counter.counter_unit_of_measurement_string = "pages"
```

### 2. Recreation_Progress
Traccia lo status di completamento.

```python
progress = Recreation_Progress()

progress.progress_percentage_float = 50.0
progress.progress_status_string = "ongoing"  # not_started, ongoing, completed, paused, dropped
progress.progress_started_timestamp_string = "2026-03-01 10:00"
progress.progress_completed_timestamp_string = ""
```

### 3. Recreation_Bookmark
Marca il punto di interruzione per riprendere dopo.

```python
bookmark = Recreation_Bookmark()

bookmark.bookmark_position_description_string = "Capitolo 5, pagina 150"
bookmark.bookmark_timestamp_string = "2026-03-14 18:30"
bookmark.bookmark_notes_string = "Momento chiave della trama!"
bookmark.bookmark_page_or_chapter_number_integer = 150
```

### 4. Recreation_Rating
Archivia rating e recensione.

```python
rating = Recreation_Rating()

rating.rating_stars_out_of_ten_float = 8.5
rating.rating_review_text_string = "Bellissimo fino a metà, poi è calato"
rating.rating_created_timestamp_string = "2026-03-14"
rating.rating_is_spoiler_boolean = False
```

### 5. Recreation_Tag
Categorizza e etichetta gli item.

```python
tag = Recreation_Tag("Favorito")

tag.tag_category_string = "Favorite"
tag.tag_color_code_string = "#FF5733"  # Colore per UI
```

---

## Categorie Predefinite

### Book
```python
book = Book("Il Signore degli Anelli")

book.book_author_name_string = "J.R.R. Tolkien"
book.book_genre_string = "Fantasy"
book.book_total_pages_integer = 1216
book.book_current_page_integer = 450
book.book_publication_year_integer = 1954
book.book_isbn_string = "978-0544933568"

# Componenti base (ereditati)
book.recreation_item_counter.counter_current_value_integer = 450
book.recreation_item_counter.counter_target_limit_integer = 1216
book.recreation_item_progress.progress_percentage_float = 37.0
book.recreation_item_rating.rating_stars_out_of_ten_float = 9.0
book.recreation_item_bookmark.bookmark_position_description_string = "Inizio di Rivendell"
```

### Anime
```python
anime = Anime("Attack on Titan")

anime.anime_studio_name_string = "Wit Studio"
anime.anime_total_episodes_integer = 139
anime.anime_current_episode_integer = 50
anime.anime_current_season_integer = 2
anime.anime_genre_list = ["Action", "Drama", "Mystery"]

# Tracking
anime.recreation_item_counter.counter_current_value_integer = 50
anime.recreation_item_progress.progress_status_string = "ongoing"
```

### VideoGame
```python
game = VideoGame("The Witcher 3")

game.videogame_developer_string = "CD Projekt Red"
game.videogame_platform_string = "PC"
game.videogame_genre_string = "RPG"
game.videogame_total_playtime_hours_float = 150.5
game.videogame_completion_percentage_float = 85.0
game.videogame_achievements_unlocked_integer = 42

# Tracking
game.recreation_item_counter.counter_current_value_integer = 150
game.recreation_item_counter.counter_unit_of_measurement_string = "hours"
```

### TVSeries
```python
series = TVSeries("Breaking Bad")

series.tvseries_network_string = "AMC"
series.tvseries_total_seasons_integer = 5
series.tvseries_current_season_integer = 3
series.tvseries_current_episode_in_season_integer = 8
series.tvseries_genre_list = ["Crime", "Drama", "Thriller"]
series.tvseries_is_completed_boolean = False
```

### Sport
```python
sport = Sport("Running")

sport.sport_type_string = "Running"
sport.sport_total_hours_practiced_float = 45.5
sport.sport_skill_level_string = "Intermediate"
sport.sport_frequency_per_week_integer = 3
sport.sport_personal_records_dictionary = {
    "5km_best_time": "22:30",
    "10km_best_time": "47:15"
}
```

### Movie
```python
movie = Movie("Inception")

movie.movie_director_string = "Christopher Nolan"
movie.movie_genre_list = ["Sci-Fi", "Thriller"]
movie.movie_release_year_integer = 2010
movie.movie_runtime_minutes_integer = 148
movie.movie_watched_count_integer = 3
movie.movie_is_watched_boolean = True
```

### TabletopGame
```python
game = TabletopGame("Dungeons & Dragons")

game.tabletopgame_type_string = "RPG"
game.tabletopgame_player_count_minimum_integer = 2
game.tabletopgame_player_count_maximum_integer = 6
game.tabletopgame_duration_minutes_integer = 180
game.tabletopgame_times_played_integer = 12
game.tabletopgame_favorite_players_list = ["Marco", "Lucia"]
```

---

## Aggiungere Recreation Items al Daily Journal

### Aggiungere un Libro
```python
daily_journal = Daily_Journal("14-03-2026")

# Creare il libro
book = Book("1984")
book.book_author_name_string = "George Orwell"
book.book_total_pages_integer = 328
book.recreation_item_counter.counter_target_limit_integer = 328

# Aggiungerlo al domain
if "Book" not in daily_journal.recreation_domain["recreation_items_by_category_dictionary"]:
    daily_journal.recreation_domain["recreation_items_by_category_dictionary"]["Book"] = {}

daily_journal.recreation_domain["recreation_items_by_category_dictionary"]["Book"]["book_001"] = book
```

### Aggiungere un Anime
```python
anime = Anime("Jujutsu Kaisen")
anime.anime_total_episodes_integer = 50
anime.anime_studio_name_string = "MAPPA"

if "Anime" not in daily_journal.recreation_domain["recreation_items_by_category_dictionary"]:
    daily_journal.recreation_domain["recreation_items_by_category_dictionary"]["Anime"] = {}

daily_journal.recreation_domain["recreation_items_by_category_dictionary"]["Anime"]["anime_001"] = anime
```

---

## Categorie Custom

L'utente può aggiungere qualsiasi hobby personalizzato usando la classe base `Recreation_Item`:

### Esempio: Fotografia
```python
photography = Recreation_Item("Progetto Fotografie Natura", "Photography")

photography.recreation_item_description_string = "Raccolta di foto di fauna selvatica"
photography.recreation_item_counter.counter_current_value_integer = 150
photography.recreation_item_counter.counter_target_limit_integer = 300
photography.recreation_item_counter.counter_unit_of_measurement_string = "photos"
photography.recreation_item_rating.rating_stars_out_of_ten_float = 8.5

if "Photography" not in daily_journal.recreation_domain["recreation_items_by_category_dictionary"]:
    daily_journal.recreation_domain["recreation_items_by_category_dictionary"]["Photography"] = {}

daily_journal.recreation_domain["recreation_items_by_category_dictionary"]["Photography"]["photo_001"] = photography
```

### Esempio: Maglieria (Knitting)
```python
knitting = Recreation_Item("Sciarpa Invernale", "Knitting")

knitting.recreation_item_counter.counter_current_value_integer = 50
knitting.recreation_item_counter.counter_target_limit_integer = 100
knitting.recreation_item_counter.counter_unit_of_measurement_string = "rows"
knitting.recreation_item_progress.progress_status_string = "ongoing"
knitting.recreation_item_bookmark.bookmark_position_description_string = "Riga 50, preparare cambio colore"
```

---

## Tracking Progress

### Aggiornare Progresso Libro
```python
book = daily_journal.recreation_domain["recreation_items_by_category_dictionary"]["Book"]["book_001"]

# Leggi altre 20 pagine
book.recreation_item_counter.counter_current_value_integer += 20

# Aggiorna percentuale
total_pages = book.book_total_pages_integer
current_pages = book.recreation_item_counter.counter_current_value_integer
book.recreation_item_progress.progress_percentage_float = (current_pages / total_pages) * 100

# Aggiorna bookmark
book.recreation_item_bookmark.bookmark_position_description_string = f"Pagina {current_pages}"
book.recreation_item_bookmark.bookmark_timestamp_string = "2026-03-14 20:00"

# Se finito
if current_pages >= total_pages:
    book.recreation_item_progress.progress_status_string = "completed"
    book.recreation_item_progress.progress_percentage_float = 100.0
    book.recreation_item_date_finished_string = "2026-03-14"
```

### Segnare Episodio Anime Visto
```python
anime = daily_journal.recreation_domain["recreation_items_by_category_dictionary"]["Anime"]["anime_001"]

# Guaarda prossimo episodio
anime.anime_current_episode_integer += 1

# Aggiorna counter
anime.recreation_item_counter.counter_current_value_integer = anime.anime_current_episode_integer

# Calcola percentuale
anime.recreation_item_progress.progress_percentage_float = (anime.anime_current_episode_integer / anime.anime_total_episodes_integer) * 100

# Se episodio finale della stagione
if anime.anime_current_episode_integer == 13:
    anime.anime_current_season_integer += 1
    anime.anime_current_episode_integer = 0
```

---

## Query e Statistiche

### Trovare Tutti gli Item "In Progresso"
```python
def get_all_items_in_progress(daily_journal):
    """Find all items currently being consumed"""
    
    in_progress_items = []
    
    for category, items_dict in daily_journal.recreation_domain["recreation_items_by_category_dictionary"].items():
        for item_id, item_object in items_dict.items():
            if item_object.recreation_item_progress.progress_status_string == "ongoing":
                in_progress_items.append({
                    "item": item_object,
                    "category": category,
                    "progress": item_object.recreation_item_progress.progress_percentage_float
                })
    
    return in_progress_items
```

### Calcolare Tempo Totale Speso per Categoria
```python
def get_total_time_for_category(daily_journal, category_string):
    """Calculate total time spent on a category"""
    
    total_time_hours = 0.0
    
    if category_string in daily_journal.recreation_domain["recreation_items_by_category_dictionary"]:
        items_dict = daily_journal.recreation_domain["recreation_items_by_category_dictionary"][category_string]
        
        for item_object in items_dict.values():
            if item_object.recreation_item_counter.counter_unit_of_measurement_string == "hours":
                total_time_hours += item_object.recreation_item_counter.counter_current_value_integer
    
    return total_time_hours
```

### Trovare Item Favoriti
```python
def get_favorite_items(daily_journal):
    """Find all items marked as favorite"""
    
    favorites = []
    
    for category, items_dict in daily_journal.recreation_domain["recreation_items_by_category_dictionary"].items():
        for item_id, item_object in items_dict.items():
            if item_object.recreation_item_is_favorite_boolean:
                favorites.append(item_object)
    
    return favorites
```

---

## Aggiungere tag agli Item

```python
book = daily_journal.recreation_domain["recreation_items_by_category_dictionary"]["Book"]["book_001"]

# Creare tag
tag_favorite = Recreation_Tag("Favorito")
tag_favorite.tag_category_string = "Favorite"
tag_favorite.tag_color_code_string = "#FFD700"  # Oro

tag_recommend = Recreation_Tag("Consigliato da Marco")
tag_recommend.tag_category_string = "Recommended"

# Aggiungere tag
book.recreation_item_tags_list.append(tag_favorite)
book.recreation_item_tags_list.append(tag_recommend)

# Marcare come favorito
book.recreation_item_is_favorite_boolean = True
```

---

## Wishlist

```python
# Aggiungere item a wishlist
upcoming_book = {
    "title": "Dune Part Two",
    "category": "Book",
    "reason": "Sequel bellissimo",
    "date_added": "2026-03-14"
}

if "Book" not in daily_journal.recreation_domain["recreation_wishlist_by_category_dictionary"]:
    daily_journal.recreation_domain["recreation_wishlist_by_category_dictionary"]["Book"] = []

daily_journal.recreation_domain["recreation_wishlist_by_category_dictionary"]["Book"].append(upcoming_book)
```

---

## Struttura JSON per Serializzazione

Il sistema si serializza naturalmente a JSON:

```json
{
  "recreation_items_by_category_dictionary": {
    "Book": {
      "book_001": {
        "recreation_item_name_string": "1984",
        "recreation_item_category_string": "Book",
        "book_author_name_string": "George Orwell",
        "book_total_pages_integer": 328,
        "recreation_item_counter": {
          "counter_current_value_integer": 150,
          "counter_target_limit_integer": 328,
          "counter_unit_of_measurement_string": "pages"
        },
        "recreation_item_progress": {
          "progress_percentage_float": 45.7,
          "progress_status_string": "ongoing"
        },
        "recreation_item_rating": {
          "rating_stars_out_of_ten_float": 9.5
        }
      }
    }
  }
}
```

---

## Best Practices

1. **Sempre aggiornare counter e progress insieme** - Mantieni sincronizzati
2. **Usa bookmark per item in progress** - Facilita la ripresa
3. **Completa rating solo dopo finish** - Evita spoiler e opinioni premature
4. **Organizza con tag** - Facilita ricerca e filtering
5. **Tieni track di timestamps** - Permette analytics sul tempo
6. **Sfrutta custom categories** - Vai oltre le 7 predefinite

---

*Guida creato: 14 Marzo 2026 - Versione 1.0*
