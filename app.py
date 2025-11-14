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
        # Приводим колонки с именами к строковому типу для надежного поиска
        data["works"]["Name"] = data["works"]["Name"].astype(str)
        data["performers"]["Name"] = data["performers"]["Name"].astype(str)
        return data
    except FileNotFoundError as e:
        st.error(f"Ошибка: Не найден файл {e.filename}. Убедитесь, что CSV файлы ('Произведения.csv', 'Исполнители.csv') находятся в той же папке.")
        return None

def find_entity_by_name(query, dataframe):
    """Универсальная функция поиска по названию."""
    if dataframe is None or not query:
        return None
    result = dataframe[dataframe["Name"].str.contains(query, case=False, na=False)]
    return result if not result.empty else None

def clean_notion_links(text):
    """Очищает текст от ссылок Notion."""
    if not isinstance(text, str):
        return ["-"]
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
            for item in items_list:
                st.markdown(f"- {item.strip()}")
        else:
            st.write("Нет данных.")

# --- ФУНКЦИИ ПОИСКА В TMDB ---

def get_tmdb_supplement(query, entity_type="movie"):
    """Получает из TMDb только постер/фото и описание/биографию."""
    if not TMDB_API_KEY or TMDB_API_KEY == "YOUR_TMDB_API_KEY_HERE":
        return {"image_url": None, "details": "Ключ API для TMDb не настроен."}
    
    search_endpoint = "search/movie" if entity_type == "movie" else "search/person"
    search_url = f"{tmdb_api_base_url}/{search_endpoint}"
    params = {"api_key": TMDB_API_KEY, "query": query, "language": "ru-RU"}
    
    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        data = response.json()

        if not data.get("results"):
            return {"image_url": None, "details": "Не найдено в TMDb."}

        first_result = data["results"][0]
        item_id = first_result.get("id")

        if entity_type == "movie":
            poster_path = first_result.get("poster_path")
            image_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
            details = first_result.get("overview", "Сюжет не найден.")
        else: # person
            profile_path = first_result.get("profile_path")
            image_url = f"https://image.tmdb.org/t/p/w500{profile_path}" if profile_path else None
            details = "Биография не найдена."
            if item_id:
                details_url = f"{tmdb_api_base_url}/person/{item_id}"
                details_params = {"api_key": TMDB_API_KEY, "language": "ru-RU"}
                details_response = requests.get(details_url, params=details_params)
                details_response.raise_for_status()
                details_data = details_response.json()
                details = details_data.get("biography", details)
        
        return {"image_url": image_url, "details": details}

    except requests.exceptions.RequestException:
        return {"image_url": None, "details": "Ошибка при запросе к TMDb."}

# --- ГЛАВНАЯ ЧАСТЬ ПРИЛОЖЕНИЯ ---

st.set_page_config(page_title="Энциклопедия Disney", layout="wide")
st.title("🏰 Энциклопедия Disney")

dataframes = load_data()

if dataframes:
    st.sidebar.title("Навигация")
    search_type = st.sidebar.radio("Выберите раздел для поиска:", ("Произведение", "Исполнитель"))

    if search_type == "Произведение":
        st.header("🎬 Поиск по произведениям")
        query = st.text_input("Введите название произведения:", "Король лев")
        if st.button("🔍 Найти", key="work_search"):
            local_results = find_entity_by_name(query, dataframes["works"])

            if local_results is not None:
                st.subheader("📊 Результаты из вашей базы данных")
                for _, row in local_results.iterrows():
                    # Для каждого локального результата получаем постер и сюжет
                    supplement = get_tmdb_supplement(row["Name"], entity_type="movie")
                    
                    col1, col2 = st.columns([1, 2.5])
                    with col1:
                        if supplement['image_url']:
                            st.image(supplement['image_url'])
                    
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

                    # Интегрируем сюжет без лишних заголовков
                    with st.expander("Сюжет"):
                        st.write(supplement['details'])

                    display_list(clean_notion_links(row.get('Персонажи')), "Персонажи")
                    display_list(clean_notion_links(row.get('Исполнители')), "Исполнители")
                    display_list(clean_notion_links(row.get('Песни')), "Песни")
                    st.divider()
            else:
                st.warning("В вашей базе ничего не найдено. Выполняется поиск в интернете...")
                # Если в локальной базе нет, ищем в интернете
                tmdb_result = get_tmdb_supplement(query, entity_type="movie")
                st.subheader("🌐 Найдено в интернете (TMDb)")
                if tmdb_result and tmdb_result['image_url']:
                    col1, col2 = st.columns([1, 2.5])
                    with col1:
                        st.image(tmdb_result['image_url'])
                    with col2:
                        st.info(f"**{query}**") # Используем исходный запрос как заголовок
                        with st.expander("Сюжет"):
                            st.write(tmdb_result['details'])
                else:
                    st.error("В интернете также ничего не найдено.")

    elif search_type == "Исполнитель":
        st.header("👤 Поиск по исполнителям")
        query = st.text_input("Введите имя исполнителя:", "Джонни Депп")
        if st.button("🔍 Найти", key="performer_search"):
            local_results = find_entity_by_name(query, dataframes["performers"])

            if local_results is not None:
                st.subheader("📊 Результаты из вашей базы данных")
                for _, row in local_results.iterrows():
                    # Для каждого локального результата получаем фото и биографию
                    supplement = get_tmdb_supplement(row["Name"], entity_type="person")

                    col1, col2 = st.columns([1, 2.5])
                    with col1:
                        if supplement['image_url']:
                            st.image(supplement['image_url'])
                            
                    with col2:
                        st.success(f"**{row['Name']}**")
                        display_field("Карьера", row.get('Карьера'))
                        display_field("Дата рождения", row.get('Дата рождения'))
                        display_field("Знак зодиака", row.get('Знак зодиака'))
                        display_field("Место рождения", row.get('Место рождения'))
                        display_field("Дата смерти", row.get('Дата смерти'))
                        display_field("Место смерти", row.get('Место смерти'))
                        display_field("Рост", row.get('Рост'), extra=" м")
                        display_field("Всего проектов", row.get('Всего проектов'))
                    
                    # Интегрируем биографию
                    with st.expander("Биография"):
                        st.write(supplement['details'])

                    display_list(clean_notion_links(row.get('Фильмография', '')), "Фильмография")
                    display_list(clean_notion_links(row.get('Сыгранные/озвученные персонажи', '')), "Персонажи")
                    st.divider()
            else:
                st.warning("В вашей базе ничего не найдено. Выполняется поиск в интернете...")
                # Если в локальной базе нет, ищем в интернете
                tmdb_result = get_tmdb_supplement(query, entity_type="person")
                st.subheader("🌐 Найдено в интернете (TMDb)")
                if tmdb_result and tmdb_result['image_url']:
                    col1, col2 = st.columns([1, 2.5])
                    with col1:
                        st.image(tmdb_result['image_url'])
                    with col2:
                        st.info(f"**{query}**")
                        with st.expander("Биография"):
                            st.write(tmdb_result['details'])
                else:
                    st.error("В интернете также ничего не найдено.")
