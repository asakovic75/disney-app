import streamlit as st
import pandas as pd
import requests
import re

# --- НАСТРОЙКА ---
TMDB_API_KEY = st.secrets.get("TMDB_API_KEY", "YOUR_TMDB_API_KEY_HERE")
tmdb_api_base_url = "https://api.themoviedb.org/3"
POSTER_BASE_URL = "https://image.tmdb.org/t/p/w400" # URL для постеров
PROFILE_BASE_URL = "https://image.tmdb.org/t/p/w400" # URL для фото актеров

# --- ФУНКЦИИ ЗАГРУЗКИ И ОЧИСТКИ ДАННЫХ ---

@st.cache_data
def load_data():
    try:
        data = {
            "works": pd.read_csv("Произведения.csv"),
            "performers": pd.read_csv("Исполнители.csv"),
        }
        return data
    except FileNotFoundError as e:
        st.error(f"Ошибка: Не найден файл {e.filename}.")
        return None

def clean_notion_links(text):
    if not isinstance(text, str): return ["-"]
    cleaned_text = re.sub(r"\(https://www.notion.so/[^)]+\)", "", text)
    items = [item.strip().strip('"') for item in cleaned_text.split(',')]
    return items

def display_list(items_list, title):
    with st.expander(title):
        if items_list and items_list != ['-']:
            for item in items_list:
                st.markdown(f"- {item.strip()}")
        else:
            st.write("-")

# --- ФУНКЦИИ ПОИСКА ---

def find_entity_by_name(query, dataframe, column_name="Name"):
    if dataframe is None or not query: return None
    result = dataframe[dataframe[column_name].str.contains(query, case=False, na=False)]
    return result if not result.empty else None

def search_movies_on_tmdb(query):
    """Ищет ВСЕ фильмы, совпадающие с запросом, в TMDb."""
    if not TMDB_API_KEY or TMDB_API_KEY == "YOUR_TMDB_API_KEY_HERE":
        st.warning("Ключ API для TMDb не настроен.")
        return []
    search_url = f"{tmdb_api_base_url}/search/movie"
    params = {"api_key": TMDB_API_KEY, "query": query, "language": "ru-RU"}
    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        return response.json().get("results", [])
    except Exception as e:
        st.error(f"Ошибка при запросе к TMDb: {e}")
    return []
    
def search_person_on_tmdb(query):
    """Ищет актера в TMDb."""
    if not TMDB_API_KEY or TMDB_API_KEY == "YOUR_TMDB_API_KEY_HERE":
        st.warning("Ключ API для TMDb не настроен.")
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
            profile_url = f"{PROFILE_BASE_URL}{profile_path}" if profile_path else None
            
            # Дополнительный запрос для получения биографии
            person_details_url = f"{tmdb_api_base_url}/person/{person['id']}"
            details_response = requests.get(person_details_url, params={"api_key": TMDB_API_KEY, "language": "ru-RU"}).json()

            return {
                "name": person.get("name"),
                "biography": details_response.get("biography"),
                "profile_url": profile_url,
                "known_for_department": person.get("known_for_department")
            }
    except Exception as e:
        st.error(f"Ошибка при поиске исполнителя в TMDb: {e}")
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
        query = st.text_input("Введите название произведения:", "Звёздные войны")
        
        if st.button("🔍 Найти", key="work_search"):
            st.subheader("📊 Результаты из вашей базы данных")
            local_results = find_entity_by_name(query, dataframes["works"])
            
            if local_results is not None:
                for _, row in local_results.iterrows():
                    st.success(f"**{row['Name']}** ({int(row.get('Год выпуска', 0))})")
                    st.write(f"**Тип:** {row.get('Тип', '-')}")
                    st.write(f"**Рейтинг:** {row.get('Рейтинг', '-')} | **Возраст:** {row.get('Возраст', '-')}")
                    st.write(f"**Студия:** {clean_notion_links(row.get('Студия', ''))[0]}")
                    st.divider()
            else:
                st.warning("В вашей локальной базе по этому запросу ничего не найдено.")

            st.divider()
            st.subheader("🌐 Результаты из интернета (TMDb)")
            tmdb_results = search_movies_on_tmdb(query)

            if tmdb_results:
                for movie in tmdb_results:
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        if movie.get('poster_path'):
                            st.image(f"{POSTER_BASE_URL}{movie.get('poster_path')}")
                    with col2:
                        st.info(f"**{movie.get('title')}**")
                        st.write(f"**Дата выхода:** {movie.get('release_date', 'N/A')}")
                        st.write(f"**Рейтинг зрителей:** {movie.get('vote_average', 'N/A')} / 10")
                        st.caption(movie.get('overview', 'Нет описания.'))
                    st.divider()
            else:
                st.info("В интернете ничего не найдено.")


    elif search_type == "Исполнитель":
        st.header("👤 Поиск по исполнителям")
        query = st.text_input("Введите имя исполнителя:", "Том Хэнкс")
        if st.button("🔍 Найти", key="performer_search"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📊 В вашей базе данных")
                results = find_entity_by_name(query, dataframes["performers"])
                if results is not None:
                    for _, row in results.iterrows():
                        st.success(f"**{row['Name']}**")
                        st.write(f"**Карьера:** {row.get('Карьера', '-')}")
                        st.write(f"**Дата рождения:** {row.get('Дата рождения', '-')}")
                        display_list(clean_notion_links(row.get('Фильмография', '')), "Фильмография")
                        st.divider()
                else:
                    st.warning("В базе ничего не найдено.")

            with col2:
                st.subheader("🌐 Найдено в интернете (TMDb)")
                person_result = search_person_on_tmdb(query)
                if person_result:
                    st.info(f"**{person_result['name']}**")
                    if person_result['profile_url']:
                        st.image(person_result['profile_url'], width=200)
                    st.write(f"**Основная деятельность:** {person_result.get('known_for_department', 'N/A')}")
                    with st.expander("Показать биографию"):
                        st.write(person_result.get('biography', 'Биография отсутствует.'))
                else:
                    st.info("В интернете ничего не найдено.")
