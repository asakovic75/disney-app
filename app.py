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
    """Загружает CSV файлы и кэширует их."""
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
    """Очищает текст от ссылок Notion, лишних символов и возвращает список строк."""
    if not isinstance(text, str):
        return ["-"]
    # Удаляем URL Notion
    cleaned_text = re.sub(r"\(https://www.notion.so/[^)]+\)", "", text)
    # Разделяем по запятым и убираем лишние пробелы/кавычки у каждого элемента
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
    if dataframe is None or not query: return None
    result = dataframe[dataframe[column_name].str.contains(query, case=False, na=False)]
    return result if not result.empty else None

@st.cache_data
def search_movie_on_tmdb(query):
    """Ищет один фильм в интернете (TMDb) и кэширует результат."""
    if not TMDB_API_KEY or TMDB_API_KEY == "YOUR_TMDB_API_KEY_HERE":
        return None
        
    search_url = f"{tmdb_api_base_url}/search/movie"
    params = {"api_key": TMDB_API_KEY, "query": query, "language": "ru-RU"}
    try:
        response = requests.get(search_url, params=params).json()
        if response.get("results"):
            # Ищем первый результат, у которого есть постер
            best_result = next((movie for movie in response["results"] if movie.get("poster_path")), response["results"][0])
            
            poster_path = best_result.get("poster_path")
            poster_url = f"{POSTER_BASE_URL}{poster_path}" if poster_path else None
            return {
                "title": best_result.get("title"),
                "overview": best_result.get("overview"),
                "vote_average": best_result.get("vote_average"),
                "poster_url": poster_url,
                "release_date": best_result.get("release_date")
            }
    except Exception:
        return None

@st.cache_data
def search_person_on_tmdb(query):
    """Ищет одного актера в TMDb и кэширует результат."""
    if not TMDB_API_KEY or TMDB_API_KEY == "YOUR_TMDB_API_KEY_HERE":
        return None
    search_url = f"{tmdb_api_base_url}/search/person"
    params = {"api_key": TMDB_API_KEY, "query": query, "language": "ru-RU"}
    try:
        response = requests.get(search_url, params=params).json()
        if response.get("results"):
            person = response["results"][0]
            person_details_url = f"{tmdb_api_base_url}/person/{person['id']}"
            details_response = requests.get(person_details_url, params={"api_key": TMDB_API_KEY, "language": "ru-RU"}).json()
            profile_path = person.get("profile_path")
            profile_url = f"{PROFILE_BASE_URL}{profile_path}" if profile_path else None
            return {
                "name": person.get("name"),
                "biography": details_response.get("biography"),
                "profile_url": profile_url,
                "known_for_department": person.get("known_for_department")
            }
    except Exception:
        return None

# --- ГЛАВНАЯ ЧАСТЬ ПРИЛОЖЕНИЯ ---

st.set_page_config(page_title="Disney DB Search", layout="centered") # Изменено на centered для одного столбца
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
        query = st.text_input("Введите название произведения:", "Пираты Карибского моря")
        
        if st.button("🔍 Найти", key="work_search"):
            local_results = find_entity_by_name(query, dataframes["works"])
            
            if local_results is not None:
                st.subheader(f"Найдено в вашей базе: {len(local_results)} совпадений")
                for _, row in local_results.iterrows():
                    # Для каждого найденного локального результата ищем дополнение в интернете
                    tmdb_result = search_movie_on_tmdb(row['Name'])
                    
                    with st.container(border=True):
                        col1, col2 = st.columns([1, 2])
                        
                        # Колонка с постером из интернета
                        with col1:
                            if tmdb_result and tmdb_result['poster_url']:
                                st.image(tmdb_result['poster_url'])
                            else:
                                st.image("https://via.placeholder.com/400x600.png?text=No+Poster", caption="Постер не найден")
                        
                        # Колонка с объединенной информацией
                        with col2:
                            st.success(f"**{row['Name']}** ({int(row.get('Год выпуска', 0))})")
                            st.write(f"**Рейтинг (ваш):** {row.get('Рейтинг', '-')}")
                            if tmdb_result:
                                st.write(f"**Рейтинг (TMDb):** {tmdb_result.get('vote_average', 'N/A')} / 10")
                            st.write(f"**Тип:** {row.get('Тип', '-')}")
                            st.write(f"**Студия:** {clean_notion_links(row.get('Студия', ''))[0]}")
                            st.write(f"**Награды:** {row.get('Награды', '-')}")
                            if tmdb_result and tmdb_result.get('overview'):
                                with st.expander("Описание из интернета"):
                                    st.write(tmdb_result.get('overview'))
            else:
                st.warning("В вашей базе ничего не найдено.")

    elif search_type == "Исполнитель":
        st.header("👤 Поиск по исполнителям")
        query = st.text_input("Введите имя исполнителя:", "Джонни Депп")
        
        if st.button("🔍 Найти", key="performer_search"):
            local_results = find_entity_by_name(query, dataframes["performers"])
            
            if local_results is not None:
                st.subheader(f"Найдено в вашей базе: {len(local_results)} совпадений")
                for _, row in local_results.iterrows():
                    tmdb_result = search_person_on_tmdb(row['Name'])
                    
                    with st.container(border=True):
                        col1, col2 = st.columns([1, 2])

                        with col1:
                            if tmdb_result and tmdb_result['profile_url']:
                                st.image(tmdb_result['profile_url'])
                            else:
                                st.image("https://via.placeholder.com/400x600.png?text=No+Photo", caption="Фото не найдено")

                        with col2:
                            st.success(f"**{row['Name']}**")
                            st.write(f"**Карьера:** {row.get('Карьера', '-')}")
                            st.write(f"**Дата рождения:** {row.get('Дата рождения', '-')}")
                            if tmdb_result and tmdb_result.get('biography'):
                                with st.expander("Биография из интернета"):
                                    st.write(tmdb_result.get('biography'))
                            display_list(clean_notion_links(row.get('Фильмография', '')), "Фильмография (из вашей базы)")
            else:
                st.warning("В вашей базе ничего не найдено.")
