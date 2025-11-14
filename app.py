import streamlit as st
import pandas as pd
import requests
import re

# --- НАСТРОЙКА ---
# API ключ будет безопасно браться из секретного хранилища Streamlit.
# Если запускаете локально и секрета нет, подставьте ключ сюда для теста.
TMDB_API_KEY = st.secrets.get("TMDB_API_KEY", "YOUR_TMDB_API_KEY_HERE") 
tmdb_api_base_url = "https://api.themoviedb.org/3"

# --- ФУНКЦИИ ЗАГРУЗКИ И ОЧИСТКИ ДАННЫХ ---

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

def clean_notion_links(text):
    """Очищает текст от ссылок Notion, лишних символов и возвращает список строк."""
    if not isinstance(text, str):
        return ["-"]
    cleaned_text = re.sub(r"\(https://www.notion.so/[^)]+\)", "", text)
    items = [item.strip().strip('"') for item in cleaned_text.split(',')]
    return items

def display_list(items_list, title):
    """Красиво отображает список элементов под раскрывающимся заголовком."""
    with st.expander(title):
        if items_list and items_list != ['-']:
            for item in items_list:
                st.markdown(f"- {item.strip()}")
        else:
            st.write("-")

# --- ФУНКЦИИ ПОИСКА ---

def find_entity_by_name(query, dataframe, column_name="Name"):
    """Универсальная функция поиска по названию в любом DataFrame."""
    if dataframe is None or not query:
        return None
    result = dataframe[dataframe[column_name].str.contains(query, case=False, na=False)]
    return result if not result.empty else None

def search_movie_on_tmdb(query):
    """Ищет фильм в TMDb и возвращает постер и сюжет."""
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
                "overview": movie.get("overview", "Описание не найдено."),
                "poster_url": poster_url,
            }
    except Exception as e:
        st.error(f"Ошибка при запросе к TMDb: {e}")
    return None

def search_person_on_tmdb(query):
    """Ищет исполнителя в TMDb и возвращает фото и биографию."""
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
            profile_path = person.get("profile_path")
            photo_url = f"https://image.tmdb.org/t/p/w500{profile_path}" if profile_path else None
            
            # Получаем детали для биографии
            person_id = person.get("id")
            if not person_id:
                return {"photo_url": photo_url, "biography": "Биография не найдена."}

            details_url = f"{tmdb_api_base_url}/person/{person_id}"
            details_params = {"api_key": TMDB_API_KEY, "language": "ru-RU"}
            details_response = requests.get(details_url, params=details_params)
            details_response.raise_for_status()
            details_data = details_response.json()

            return {
                "photo_url": photo_url,
                "biography": details_data.get("biography", "Биография не найдена.")
            }
    except Exception as e:
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
            
            # --- Секция 1: Поиск в локальной базе ---
            st.subheader("📊 В вашей базе данных")
            local_results = find_entity_by_name(query, dataframes["works"])
            if local_results is not None:
                for _, row in local_results.iterrows():
                    st.success(f"**{row['Name']}** ({int(row.get('Год выпуска', 0))})")
                    st.write(f"**Тип:** {row.get('Тип', '-')}")
                    st.write(f"**Рейтинг:** {row.get('Рейтинг', '-')} | **Возраст:** {row.get('Возраст', '-')}")
                    st.write(f"**Жанр:** {row.get('Жанр', '-')}")
                    st.write(f"**Студия:** {clean_notion_links(row.get('Студия', ''))[0]}")
                    st.write(f"**Бюджет и сборы:** {row.get('Бюджет и сборы', '-')}")
                    st.write(f"**Награды:** {row.get('Награды', '-')}")
                    display_list(clean_notion_links(row.get('Персонажи')), "Персонажи")
                    display_list(clean_notion_links(row.get('Исполнители')), "Исполнители")
                    display_list(clean_notion_links(row.get('Песни')), "Песни")
                    st.divider()
            else:
                st.warning("В вашей базе ничего не найдено.")
            
            # --- Секция 2: Поиск в интернете ---
            st.subheader("🌐 Дополнительная информация из интернета (TMDb)")
            tmdb_result = search_movie_on_tmdb(query)
            if tmdb_result:
                if tmdb_result['poster_url']:
                    st.image(tmdb_result['poster_url'], width=250, caption="Постер")
                
                with st.expander("Сюжет"):
                    st.write(tmdb_result.get('overview') or 'Нет описания.')
            else:
                st.info("В интернете ничего не найдено.")

    elif search_type == "Исполнитель":
        st.header("👤 Поиск по исполнителям")
        query = st.text_input("Введите имя исполнителя:", "Том Хэнкс")
        if st.button("🔍 Найти", key="performer_search"):
            
            # --- Секция 1: Поиск в локальной базе ---
            st.subheader("📊 В вашей базе данных")
            local_results = find_entity_by_name(query, dataframes["performers"])
            if local_results is not None:
                for _, row in local_results.iterrows():
                    st.success(f"**{row['Name']}**")
                    st.write(f"**Карьера:** {row.get('Карьера', '-')}")
                    st.write(f"**Дата рождения:** {row.get('Дата рождения', '-')} | **Дата смерти:** {row.get('Дата смерти', 'Неизвестно')}")
                    st.write(f"**Место рождения:** {row.get('Место рождения', '-')}")
                    st.write(f"**Всего проектов:** {row.get('Всего проектов', '-')}")
                    st.write(f"**Рост:** {row.get('Рост', '-')} м")
                    display_list(clean_notion_links(row.get('Фильмография', '')), "Фильмография")
                    display_list(clean_notion_links(row.get('Сыгранные/озвученные персонажи', '')), "Сыгранные/озвученные персонажи")
                    st.divider()
            else:
                st.warning("В вашей базе ничего не найдено.")

            # --- Секция 2: Поиск в интернете ---
            st.subheader("🌐 Дополнительная информация из интернета (TMDb)")
            tmdb_result = search_person_on_tmdb(query)
            if tmdb_result:
                if tmdb_result['photo_url']:
                    st.image(tmdb_result['photo_url'], width=250, caption="Фото")
                
                with st.expander("Биография"):
                     st.write(tmdb_result.get('biography') or 'Нет описания.')
            else:
                st.info("В интернете ничего не найдено.")
