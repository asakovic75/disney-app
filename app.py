import streamlit as st
import pandas as pd
import requests
import re

# --- НАСТРОЙКА ---
# API ключ будет безопасно браться из секретного хранилища Streamlit.
# Если запускаете локально и секрета нет, подставьте ключ сюда для теста.
TMDB_API_KEY = st.secrets.get("TMDB_API_KEY", "YOUR_TMDB_API_KEY_HERE") 
tmdb_api_base_url = "https://api.themoviedb.org/3"

# --- ФУНКЦИИ-ПОМОЩНИКИ ---

@st.cache_data
def load_data():
    """Загружает CSV файлы (Произведения, Исполнители) и кэширует их."""
    try:
        data = {
            "works": pd.read_csv("Произведения.csv"),
            "performers": pd.read_csv("Исполнители.csv"),
        }
        return data
    except FileNotFoundError as e:
        st.error(f"Ошибка: Не найден файл {e.filename}. Убедитесь, что CSV файлы ('Произведения.csv', 'Исполнители.csv') находятся в той же папке, что и app.py.")
        return None

# !!! ВОТ ИСПРАВЛЕНИЕ: ВОЗВРАЩЕНА НЕДОСТАЮЩАЯ ФУНКЦИЯ !!!
def find_entity_by_name(query, dataframe, column_name="Name"):
    """Универсальная функция поиска по названию в любом DataFrame."""
    if dataframe is None or not query:
        return None
    # .astype(str) делает поиск более надежным, даже если в колонке есть не-текстовые данные
    result = dataframe[dataframe[column_name].astype(str).str.contains(query, case=False, na=False)]
    return result if not result.empty else None

def clean_notion_links(text):
    """Очищает текст от ссылок Notion, лишних символов и возвращает список строк."""
    if not isinstance(text, str):
        return ["-"]
    cleaned_text = re.sub(r"\(https://www.notion.so/[^)]+\)", "", text)
    items = [item.strip().strip('"') for item in cleaned_text.split(',')]
    return items

def display_field(label, value):
    """Отображает строку 'Метка: Значение', только если значение существует (не пустое, не NaN, не '-')"""
    if pd.notna(value) and str(value).strip() not in ['', '-']:
        st.write(f"**{label}:** {value}")

def display_list(items_list, title):
    """Красиво отображает список элементов под раскрывающимся заголовком."""
    with st.expander(title):
        if items_list and items_list != ['-']:
            for item in items_list:
                st.markdown(f"- {item.strip()}")
        else:
            st.write("Нет данных.")

# --- ФУНКЦИИ ПОИСКА В TMDB ---

def search_movie_on_tmdb(query):
    """Ищет фильм в TMDb и возвращает расширенную информацию."""
    if not TMDB_API_KEY or TMDB_API_KEY == "YOUR_TMDB_API_KEY_HERE":
        st.warning("Ключ API для TMDb не настроен. Поиск в интернете недоступен.")
        return None
    search_url = f"{tmdb_api_base_url}/search/movie"
    params = {"api_key": TMDB_API_KEY, "query": query, "language": "ru-RU"}
    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get("results"):
            movie = data["results"][0]
            poster_path = movie.get("poster_path")
            poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
            return {
                "title": movie.get("title"),
                "overview": movie.get("overview", "Описание не найдено."),
                "poster_url": poster_url,
                "release_date": movie.get("release_date"),
                "vote_average": movie.get("vote_average")
            }
    except requests.exceptions.RequestException as e:
        st.error(f"Ошибка при запросе к TMDb: {e}")
    return None

def search_person_on_tmdb(query):
    """Ищет исполнителя в TMDb и возвращает расширенную информацию."""
    if not TMDB_API_KEY or TMDB_API_KEY == "YOUR_TMDB_API_KEY_HERE":
        st.warning("Ключ API для TMDb не настроен. Поиск в интернете недоступен.")
        return None
    search_url = f"{tmdb_api_base_url}/search/person"
    params = {"api_key": TMDB_API_KEY, "query": query, "language": "ru-RU"}
    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get("results"):
            person = data["results"][0]
            person_id = person.get("id")
            if not person_id: return None

            details_url = f"{tmdb_api_base_url}/person/{person_id}"
            details_params = {"api_key": TMDB_API_KEY, "language": "ru-RU"}
            details_response = requests.get(details_url, params=details_params)
            details_response.raise_for_status()
            details_data = details_response.json()
            
            profile_path = person.get("profile_path")
            photo_url = f"https://image.tmdb.org/t/p/w500{profile_path}" if profile_path else None

            return {
                "name": person.get("name"),
                "photo_url": photo_url,
                "known_for": person.get("known_for_department"),
                "popularity": person.get("popularity"),
                "biography": details_data.get("biography", "Биография не найдена.")
            }
    except requests.exceptions.RequestException as e:
        st.error(f"Ошибка при запросе к TMDb: {e}")
    return None

# --- ГЛАВНАЯ ЧАСТЬ ПРИЛОЖЕНИЯ ---

st.set_page_config(page_title="Disney DB Search", layout="wide")
st.title("🪄 Ассистент по базе данных Disney")

dataframes = load_data()

if dataframes:
    st.sidebar.title("Навигация")
    search_type = st.sidebar.radio(
        "Выберите раздел для поиска:",
        ("Произведение", "Исполнитель")
    )

    if search_type == "Произведение":
        st.header("🎬 Поиск по произведениям")
        query = st.text_input("Введите название произведения:", "Король лев")
        if st.button("🔍 Найти", key="work_search"):
            local_results = find_entity_by_name(query, dataframes["works"])
            tmdb_result = search_movie_on_tmdb(query)

            if local_results is not None:
                st.subheader("📊 Результаты из вашей базы данных")
                for _, row in local_results.iterrows():
                    col1, col2 = st.columns([1, 2.5])
                    
                    with col1:
                        if tmdb_result and tmdb_result.get('poster_url'):
                            st.image(tmdb_result['poster_url'])
                    
                    with col2:
                        st.success(f"**{row['Name']}**")
                        display_field("Год выпуска", int(row.get('Год выпуска', 0)) if pd.notna(row.get('Год выпуска')) else None)
                        display_field("Тип", row.get('Тип'))
                        display_field("Жанр", row.get('Жанр'))
                        display_field("Рейтинг", row.get('Рейтинг'))
                        display_field("Возраст", row.get('Возраст'))
                        display_field("Продолжительность", row.get('Продолжительность'))
                        display_field("Студия", clean_notion_links(row.get('Студия'))[0] if pd.notna(row.get('Студия')) else None)
                        display_field("Бюджет и сборы", row.get('Бюджет и сборы'))
                        display_field("Награды", row.get('Награды'))

                    display_list(clean_notion_links(row.get('Персонажи')), "Персонажи")
                    display_list(clean_notion_links(row.get('Исполнители')), "Исполнители")
                    display_list(clean_notion_links(row.get('Песни')), "Песни")
                    
                    if tmdb_result:
                        st.subheader("🌐 Дополнительная информация из интернета (TMDb)")
                        display_field("Название по версии TMDb", tmdb_result.get('title'))
                        display_field("Дата мирового релиза", tmdb_result.get('release_date'))
                        display_field("Рейтинг зрителей TMDb", f"{tmdb_result.get('vote_average'):.1f} / 10" if tmdb_result.get('vote_average') else None)
                        with st.expander("Сюжет"):
                            st.write(tmdb_result.get('overview') or 'Нет описания.')
                    st.divider()
            else:
                st.warning("В вашей базе ничего не найдено.")

    elif search_type == "Исполнитель":
        st.header("👤 Поиск по исполнителям")
        query = st.text_input("Введите имя исполнителя:", "Джонни Депп")
        if st.button("🔍 Найти", key="performer_search"):
            local_results = find_entity_by_name(query, dataframes["performers"])
            tmdb_result = search_person_on_tmdb(query)

            if local_results is not None:
                st.subheader("📊 Результаты из вашей базы данных")
                for _, row in local_results.iterrows():
                    col1, col2 = st.columns([1, 2.5])
                    with col1:
                        if tmdb_result and tmdb_result.get('photo_url'):
                            st.image(tmdb_result['photo_url'])
                            
                    with col2:
                        st.success(f"**{row['Name']}**")
                        display_field("Карьера", row.get('Карьера'))
                        display_field("Дата рождения", row.get('Дата рождения'))
                        display_field("Знак зодиака", row.get('Знак зодиака'))
                        display_field("Место рождения", row.get('Место рождения'))
                        display_field("Дата смерти", row.get('Дата смерти'))
                        display_field("Место смерти", row.get('Место смерти'))
                        display_field("Рост", f"{row.get('Рост')} м" if pd.notna(row.get('Рост')) else None)
                        display_field("Всего проектов", row.get('Всего проектов'))

                    display_list(clean_notion_links(row.get('Фильмография', '')), "Фильмография")
                    display_list(clean_notion_links(row.get('Сыгранные/озвученные персонажи', '')), "Персонажи")

                    if tmdb_result:
                        st.subheader("🌐 Дополнительная информация из интернета (TMDb)")
                        display_field("Имя по версии TMDb", tmdb_result.get('name'))
                        display_field("Основная деятельность", tmdb_result.get('known_for'))
                        display_field("Индекс популярности TMDb", f"{tmdb_result.get('popularity'):.2f}" if tmdb_result.get('popularity') else None)
                        with st.expander("Биография"):
                            st.write(tmdb_result.get('biography') or 'Нет описания.')
                    st.divider()
            else:
                st.warning("В вашей базе ничего не найдено.")
