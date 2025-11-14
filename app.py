import streamlit as st
import pandas as pd
import requests
import re

# --- НАСТРОЙКА ---
TMDB_API_KEY = st.secrets.get("TMDB_API_KEY", "YOUR_TMDB_API_KEY_HERE") 
tmdb_api_base_url = "https://api.themoviedb.org/3"

# ID компаний Disney и ее дочерних студий для фильтрации
DISNEY_COMPANY_IDS = {
    2,       # Walt Disney Pictures
    3,       # Pixar
    6125,    # Walt Disney Animation Studios
    420,     # Marvel Studios
    1,       # Lucasfilm Ltd.
    10282,   # Searchlight Pictures (ранее Fox Searchlight)
    127928   # 20th Century Studios (ранее 20th Century Fox)
}

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
    """Универсальная функция поиска по названию в DataFrame."""
    if dataframe is None or not query:
        return None
    result = dataframe[dataframe["Name"].str.contains(query, case=False, na=False)]
    return result if not result.empty else None

def clean_notion_links(text):
    """Очищает текст от ссылок Notion и возвращает список строк."""
    if not isinstance(text, str): return ["-"]
    cleaned_text = re.sub(r"\(https://www.notion.so/[^)]+\)", "", text)
    items = [item.strip().strip('"') for item in cleaned_text.split(',')]
    return items

def display_field(label, value, extra=""):
    """Отображает строку 'Метка: Значение', только если значение существует."""
    if pd.notna(value) and str(value).strip() not in ['', '-']:
        st.write(f"**{label}:** {value}{extra}")

def display_list(items_list, title):
    """Красиво отображает список элементов под раскрывающимся заголовком."""
    with st.expander(title):
        if items_list and items_list != ['-']:
            for item in items_list: st.markdown(f"- {item.strip()}")
        else:
            st.write("Нет данных.")

# --- ФУНКЦИИ ПОИСКА В TMDB ---

def get_movie_details(query, year=None):
    """Ищет фильмы TMDb, ФИЛЬТРУЕТ по компаниям Disney и возвращает СПИСОК."""
    if not TMDB_API_KEY or TMDB_API_KEY == "YOUR_TMDB_API_KEY_HERE": return []
    
    search_query = query.split(':')[0].strip() if ':' in query else query
    search_url = f"{tmdb_api_base_url}/search/movie"
    params = {"api_key": TMDB_API_KEY, "query": search_query, "language": "ru-RU", "page": 1}
    if year:
        params['primary_release_year'] = year
    
    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        disney_movies = []
        for movie_summary in data.get("results", []):
            movie_id = movie_summary.get("id")
            if not movie_id: continue

            details_url = f"{tmdb_api_base_url}/movie/{movie_id}"
            details_params = {"api_key": TMDB_API_KEY, "language": "ru-RU"}
            details_response = requests.get(details_url, params=details_params)
            movie_details = details_response.json()
            
            # Проверяем компании
            producer_ids = {company['id'] for company in movie_details.get("production_companies", [])}
            if producer_ids.intersection(DISNEY_COMPANY_IDS):
                poster_path = movie_details.get("poster_path")
                disney_movies.append({
                    "title": movie_details.get("title"),
                    "overview": movie_details.get("overview", "Сюжет не найден."),
                    "image_url": f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None,
                    "release_date": movie_details.get("release_date"),
                    "vote_average": movie_details.get("vote_average")
                })
            if len(disney_movies) >= 10: # Ограничиваем до 10 Disney-фильмов
                break
        return disney_movies
    except requests.exceptions.RequestException:
        return []

def get_person_details(query):
    """Ищет людей в TMDb и возвращает СПИСОК до 10 результатов."""
    if not TMDB_API_KEY or TMDB_API_KEY == "YOUR_TMDB_API_KEY_HERE": return []
    # ... (код для этой функции остается без изменений) ...
    search_url = f"{tmdb_api_base_url}/search/person"
    params = {"api_key": TMDB_API_KEY, "query": query, "language": "ru-RU"}
    
    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        results = []
        for person_summary in data.get("results", [])[:10]:
            person_id = person_summary.get("id")
            if not person_id: continue

            details_url = f"{tmdb_api_base_url}/person/{person_id}"
            details_params = {"api_key": TMDB_API_KEY, "language": "ru-RU"}
            details_response = requests.get(details_url, params=details_params)
            details_response.raise_for_status()
            details = details_response.json()
            
            profile_path = details.get("profile_path")
            results.append({
                "name": details.get("name"),
                "biography": details.get("biography", "Биография не найдена."),
                "image_url": f"https://image.tmdb.org/t/p/w500{profile_path}" if profile_path else None,
                "birthday": details.get("birthday"),
                "place_of_birth": details.get("place_of_birth"),
                "known_for": details.get("known_for_department")
            })
        return results
    except requests.exceptions.RequestException:
        return []

# --- ГЛАВНАЯ ЧАСТЬ ПРИЛОЖЕНИЯ ---

st.set_page_config(page_title="Умный поиск по миру Disney", layout="wide")
st.title("✨ Умный поиск по миру Disney")

dataframes = load_data()

if dataframes:
    st.sidebar.title("Навигация")
    search_type = st.sidebar.radio("Выберите раздел:", ("Произведение", "Исполнитель"))

    if search_type == "Произведение":
        st.header("🎬 Поиск по произведениям")
        query = st.text_input("Введите название произведения:", "Красавица и чудовище")
        if st.button("🔍 Найти", key="work_search"):
            
            displayed_items = set() 
            local_results = find_entity_by_name(query, dataframes["works"])
            
            if local_results is not None:
                st.subheader("📊 Результаты из вашей базы данных")
                for _, row in local_results.iterrows():
                    year = int(row['Год выпуска']) if pd.notna(row['Год выпуска']) else 0
                    title_cleaned = row['Name'].split(':')[0].strip().lower()
                    displayed_items.add((title_cleaned, year))
                    
                    details_list = get_movie_details(row["Name"], year=year)
                    details = details_list[0] if details_list else None
                    
                    st.markdown(f"<div style='background-color:#28a745; padding: 10px; border-radius: 5px; color: white; margin-bottom: 10px;'><b>{row['Name']}</b></div>", unsafe_allow_html=True)
                    col1, col2 = st.columns([1, 2.5])
                    with col1:
                        if details and details['image_url']:
                            st.image(details['image_url'])
                    with col2:
                        display_field("Год выпуска", year if year != 0 else "Не указан")
                        display_field("Тип", row.get('Тип'))
                        display_field("Жанр", row.get('Жанр'))
                        display_field("Рейтинг", row.get('Рейтинг'))
                        display_field("Возраст", row.get('Возраст'))
                        display_field("Продолжительность", row.get('Продолжительность'))
                        display_field("Студия", clean_notion_links(row.get('Студия'))[0] if pd.notna(row.get('Студия')) else None)
                        display_field("Бюджет и сборы", row.get('Бюджет и сборы'))
                        display_field("Награды", row.get('Награды'))

                    if details and details['overview']:
                        with st.expander("Сюжет"): st.write(details['overview'])
                    display_list(clean_notion_links(row.get('Персонажи')), "Персонажи")
                    display_list(clean_notion_links(row.get('Исполнители')), "Исполнители")
                    display_list(clean_notion_links(row.get('Песни')), "Песни")
                    st.divider()
            else:
                st.warning("В вашей базе ничего не найдено.")

            st.subheader("🌐 Найдено в интернете (TMDb)")
            internet_results = get_movie_details(query)
            
            new_results_found = False
            if internet_results:
                for internet_result in internet_results:
                    release_date = internet_result.get('release_date')
                    internet_year = int(release_date.split('-')[0]) if release_date and '-' in release_date else 0
                    
                    check_tuple = (internet_result['title'].split(':')[0].strip().lower(), internet_year)
                    if check_tuple in displayed_items:
                        continue 
                    
                    new_results_found = True
                    st.markdown(f"<div style='background-color:#17a2b8; padding: 10px; border-radius: 5px; color: white; margin-bottom: 10px;'><b>{internet_result['title']}</b></div>", unsafe_allow_html=True)
                    col1, col2 = st.columns([1, 2.5])
                    with col1:
                        if internet_result['image_url']: st.image(internet_result['image_url'])
                    with col2:
                        display_field("Дата релиза", internet_result.get('release_date'))
                        display_field("Рейтинг зрителей", f"{internet_result.get('vote_average'):.1f} / 10" if internet_result.get('vote_average') else None)
                        with st.expander("Сюжет"):
                            st.write(internet_result.get('overview'))
                    st.divider()
            
            if not new_results_found:
                st.info("Все релевантные результаты из интернета уже показаны в вашей базе данных или не найдены.")

    elif search_type == "Исполнитель":
        st.header("👤 Поиск по исполнителям")
        query = st.text_input("Введите имя исполнителя:", "Джонни Депп")
        if st.button("🔍 Найти", key="performer_search"):
            local_results = find_entity_by_name(query, dataframes["performers"])

            if local_results is not None:
                st.subheader("📊 Результаты из вашей базы данных")
                for _, row in local_results.iterrows():
                    details_list = get_person_details(row["Name"])
                    details = details_list[0] if details_list else None
                    
                    st.markdown(f"<div style='background-color:#28a745; padding: 10px; border-radius: 5px; color: white; margin-bottom: 10px;'><b>{row['Name']}</b></div>", unsafe_allow_html=True)
                    col1, col2 = st.columns([1, 2.5])
                    with col1:
                        if details and details['image_url']: st.image(details['image_url'])
                    with col2:
                        display_field("Карьера", row.get('Карьера'))
                        display_field("Дата рождения", row.get('Дата рождения'))
                        display_field("Знак зодиака", row.get('Знак зодиака'))
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
                internet_results = get_person_details(query)
                if internet_results:
                    st.subheader("🌐 Найдено в интернете (TMDb)")
                    for internet_result in internet_results:
                        st.markdown(f"<div style='background-color:#17a2b8; padding: 10px; border-radius: 5px; color: white; margin-bottom: 10px;'><b>{internet_result['name']}</b></div>", unsafe_allow_html=True)
                        col1, col2 = st.columns([1, 2.5])
                        with col1:
                            if internet_result['image_url']: st.image(internet_result['image_url'])
                        with col2:
                            display_field("Основная деятельность", internet_result.get('known_for'))
                            display_field("Дата рождения", internet_result.get('birthday'))
                            display_field("Место рождения", internet_result.get('place_of_birth'))
                        
                        if internet_result['biography']:
                            with st.expander("Биография"): st.write(internet_result['biography'])
                        st.divider()
                else:
                    st.error("В интернете также ничего не найдено.")
