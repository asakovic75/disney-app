import streamlit as st
import pandas as pd
import requests
import re

# --- НАСТРОЙКА ---
TMDB_API_KEY = st.secrets.get("TMDB_API_KEY", "YOUR_TMDB_API_KEY_HERE") 
tmdb_api_base_url = "https://api.themoviedb.org/3"

# --- ФУНКЦИИ-ПОМОЩНИКИ ---

@st.cache_data
def load_data():
    """Загружает и кэширует CSV файлы."""
    try:
        data = {
            "works": pd.read_csv("Произведения.csv"),
            "performers": pd.read_csv("Исполнители.csv"),
        }
        data["works"]["Name"] = data["works"]["Name"].astype(str)
        data["performers"]["Name"] = data["performers"]["Name"].astype(str)
        return data
    except FileNotFoundError as e:
        st.error(f"Ошибка: Не найден файл {e.filename}.")
        return None

def find_entity_by_name(query, dataframe):
    """Универсальная функция поиска по названию."""
    if dataframe is None or not query:
        return None
    result = dataframe[dataframe["Name"].str.contains(query, case=False, na=False)]
    return result if not result.empty else None

def clean_notion_links(text):
    """Очищает текст от ссылок Notion."""
    if not isinstance(text, str): return ["-"]
    cleaned_text = re.sub(r"\(https://www.notion.so/[^)]+\)", "", text)
    items = [item.strip().strip('"') for item in cleaned_text.split(',')]
    return items

def display_field(label, value, extra=""):
    """Отображает строку 'Метка: Значение', только если значение существует."""
    if pd.notna(value) and str(value).strip() not in ['', '-']:
        st.write(f"**{label}:** {value}{extra}")

def display_list(items_list, title):
    """Отображает список в виде экспандера."""
    with st.expander(title):
        if items_list and items_list != ['-']:
            for item in items_list: st.markdown(f"- {item.strip()}")
        else:
            st.write("Нет данных.")

# --- ФУНКЦИИ ПОИСКА В TMDB ---

def get_movie_details(query, year=None):
    """Ищет фильм/мультфильм в TMDb и возвращает полную информацию."""
    if not TMDB_API_KEY or TMDB_API_KEY == "YOUR_TMDB_API_KEY_HERE":
        return None
    
    search_url = f"{tmdb_api_base_url}/search/movie"
    params = {"api_key": TMDB_API_KEY, "query": query, "language": "ru-RU"}
    if year:
        params['year'] = year
    
    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        data = response.json()
        if not data.get("results"): return None

        movie = data["results"][0]
        poster_path = movie.get("poster_path")
        return {
            "title": movie.get("title"),
            "overview": movie.get("overview", "Сюжет не найден."),
            "image_url": f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None,
            "release_date": movie.get("release_date"),
            "vote_average": movie.get("vote_average")
        }
    except requests.exceptions.RequestException:
        return None

def get_person_details(query):
    """Ищет человека в TMDb и возвращает расширенную информацию."""
    if not TMDB_API_KEY or TMDB_API_KEY == "YOUR_TMDB_API_KEY_HERE": return None
    
    search_url = f"{tmdb_api_base_url}/search/person"
    params = {"api_key": TMDB_API_KEY, "query": query, "language": "ru-RU"}
    
    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        data = response.json()
        if not data.get("results"): return None

        person_id = data["results"][0].get("id")
        if not person_id: return None

        details_url = f"{tmdb_api_base_url}/person/{person_id}"
        details_params = {"api_key": TMDB_API_KEY, "language": "ru-RU"}
        details_response = requests.get(details_url, params=details_params)
        details_response.raise_for_status()
        details = details_response.json()
        
        profile_path = details.get("profile_path")
        return {
            "name": details.get("name"),
            "biography": details.get("biography", "Биография не найдена."),
            "image_url": f"https://image.tmdb.org/t/p/w500{profile_path}" if profile_path else None,
            "birthday": details.get("birthday"),
            "place_of_birth": details.get("place_of_birth"),
            "known_for": details.get("known_for_department")
        }
    except requests.exceptions.RequestException:
        return None

# --- ГЛАВНАЯ ЧАСТЬ ПРИЛОЖЕНИЯ ---

st.set_page_config(page_title="Энциклопедия Disney", layout="wide")
st.title("🏰 Энциклопедия Disney")

dataframes = load_data()

if dataframes:
    st.sidebar.title("Навигация")
    search_type = st.sidebar.radio("Выберите раздел:", ("Произведение", "Исполнитель"))

    if search_type == "Произведение":
        st.header("🎬 Поиск по произведениям")
        query = st.text_input("Введите название произведения:", "Король лев")
        if st.button("🔍 Найти", key="work_search"):
            
            # --- БЛОК 1: ПОИСК В ЛОКАЛЬНОЙ БАЗЕ ---
            local_results = find_entity_by_name(query, dataframes["works"])
            if local_results is not None:
                st.subheader("📊 Результаты из вашей базы данных")
                for _, row in local_results.iterrows():
                    year = int(row['Год выпуска']) if pd.notna(row['Год выпуска']) else None
                    details = get_movie_details(row["Name"], year=year)
                    
                    col1, col2 = st.columns([1, 2.5])
                    with col1:
                        if details and details['image_url']:
                            st.image(details['image_url'])
                    with col2:
                        st.success(f"**{row['Name']}**")
                        display_field("Год выпуска", year)
                        display_field("Тип", row.get('Тип'))
                        display_field("Жанр", row.get('Жанр'))
                        # ... все остальные поля из вашей таблицы
                        display_field("Рейтинг", row.get('Рейтинг'))
                        display_field("Возраст", row.get('Возраст'))
                        display_field("Продолжительность", row.get('Продолжительность'))
                        display_field("Студия", clean_notion_links(row.get('Студия'))[0] if pd.notna(row.get('Студия')) else None)
                        display_field("Бюджет и сборы", row.get('Бюджет и сборы'))
                        display_field("Награды", row.get('Награды'))

                    if details and details['overview']:
                        with st.expander("Сюжет"):
                            st.write(details['overview'])

                    display_list(clean_notion_links(row.get('Персонажи')), "Персонажи")
                    display_list(clean_notion_links(row.get('Исполнители')), "Исполнители")
                    display_list(clean_notion_links(row.get('Песни')), "Песни")
                    st.divider()
            else:
                st.warning("В вашей базе ничего не найдено.")

            # --- БЛОК 2: ОТДЕЛЬНЫЙ ПОИСК В ИНТЕРНЕТЕ ---
            st.subheader("🌐 Найдено в интернете (TMDb)")
            internet_result = get_movie_details(query)
            if internet_result:
                col1, col2 = st.columns([1, 2.5])
                with col1:
                    if internet_result['image_url']: st.image(internet_result['image_url'])
                with col2:
                    st.info(f"**{internet_result['title']}**")
                    display_field("Дата релиза", internet_result.get('release_date'))
                    display_field("Рейтинг зрителей", f"{internet_result.get('vote_average'):.1f} / 10" if internet_result.get('vote_average') else None)
                    with st.expander("Сюжет"):
                        st.write(internet_result.get('overview'))
            else:
                st.error("По вашему запросу в интернете ничего не найдено.")

    elif search_type == "Исполнитель":
        st.header("👤 Поиск по исполнителям")
        query = st.text_input("Введите имя исполнителя:", "Леонардо Ди Каприо")
        if st.button("🔍 Найти", key="performer_search"):
            local_results = find_entity_by_name(query, dataframes["performers"])

            if local_results is not None:
                st.subheader("📊 Результаты из вашей базы данных")
                for _, row in local_results.iterrows():
                    details = get_person_details(row["Name"])
                    col1, col2 = st.columns([1, 2.5])
                    with col1:
                        if details and details['image_url']: st.image(details['image_url'])
                    with col2:
                        st.success(f"**{row['Name']}**")
                        display_field("Карьера", row.get('Карьера'))
                        display_field("Дата рождения", row.get('Дата рождения'))
                        display_field("Знак зодиака", row.get('Знак зодиака'))
                        # ... все остальные поля
                        display_field("Место рождения", row.get('Место рождения'))
                        display_field("Дата смерти", row.get('Дата смерти'))
                        display_field("Место смерти", row.get('Место смерти'))
                        display_field("Рост", row.get('Рост'), extra=" м")
                        display_field("Всего проектов", row.get('Всего проектов'))
                    
                    if details and details['biography']:
                        with st.expander("Биография"): st.write(details['biography'])

                    display_list(clean_notion_links(row.get('Фильмография')), "Фильмография")
                    display_list(clean_notion_links(row.get('Сыгранные/озвученные персонажи')), "Персонажи")
                    st.divider()
            else:
                st.warning("В вашей базе ничего не найдено. Выполняется поиск в интернете...")
                internet_result = get_person_details(query)
                st.subheader("🌐 Найдено в интернете (TMDb)")
                if internet_result:
                    col1, col2 = st.columns([1, 2.5])
                    with col1:
                        if internet_result['image_url']: st.image(internet_result['image_url'])
                    with col2:
                        st.info(f"**{internet_result['name']}**")
                        display_field("Основная деятельность", internet_result.get('known_for'))
                        display_field("Дата рождения", internet_result.get('birthday'))
                        display_field("Место рождения", internet_result.get('place_of_birth'))
                    
                    if internet_result['biography']:
                        with st.expander("Биография"): st.write(internet_result['biography'])
                else:
                    st.error("В интернете также ничего не найдено.")
