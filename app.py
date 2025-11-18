import streamlit as st
import pandas as pd
import requests
import re
import base64
from io import BytesIO
import datetime

TMDB_API_KEY = st.secrets.get("TMDB_API_KEY", "YOUR_TMDB_API_KEY_HERE")
tmdb_api_base_url = "https://api.themoviedb.org/3"
DISNEY_COMPANY_IDS_STR = "2|3|6125|420|1|10282|127928"

@st.cache_data
def get_image_as_base64(url):
    if not url or not url.startswith("http"):
        return None
    try:
        response = requests.get(url)
        response.raise_for_status()
        encoded_string = base64.b64encode(response.content).decode()
        return f"data:image/png;base64,{encoded_string}"
    except requests.exceptions.RequestException:
        return None

@st.cache_data
def load_data():
    try:
        data = { "works": pd.read_csv("Произведения.csv"), "performers": pd.read_csv("Исполнители.csv") }
        data["works"]["Name"] = data["works"]["Name"].astype(str)
        data["performers"]["Name"] = data["performers"]["Name"].astype(str)
        return data
    except FileNotFoundError as e:
        st.error(f"Ошибка: Не найден файл {e.filename}.")
        return None

def find_entity_by_name(query, dataframe):
    if dataframe is None or not query: return None
    result = dataframe[dataframe["Name"].str.contains(query, case=False, na=False)]
    return result if not result.empty else None

def clean_notion_links(text):
    if not isinstance(text, str): return ["-"]
    cleaned_text = re.sub(r"https://www.notion.so/[\w-]+", "", text)
    items = [item.strip().strip('"') for item in cleaned_text.split(',')]
    return items

def clean_review_content(text):
    if not isinstance(text, str): return ""
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'(?i)read\s+.*?\s+full\s+(article|review).*', '', text)
    text = re.sub(r'(?im)^\s*read the full review.*\s*$', '', text)
    text = re.sub(r'(?i)read more at.*', '', text)
    text = '\n'.join([line.strip() for line in text.split('\n') if line.strip()])
    return text if text else "Нет текста."

def display_field(label, value, extra=""):
    if pd.notna(value) and str(value).strip() not in ['', '-']:
        st.write(f"{label}: {value}{extra}")

def display_list(items_list, title):
    with st.expander(title):
        if items_list and items_list != ['-']:
            for item in items_list: st.markdown(f"- {item.strip()}")
        else:
            st.write("Нет данных.")

def get_movie_details(query, year=None):
    if not TMDB_API_KEY or TMDB_API_KEY == "YOUR_TMDB_API_KEY_HERE": return []
    search_query = query.split(':')[0].strip() if ':' in query else query
    discover_url = f"{tmdb_api_base_url}/discover/movie"
    params = {"api_key": TMDB_API_KEY, "language": "ru-RU", "with_text_query": search_query, "with_companies": DISNEY_COMPANY_IDS_STR}
    if year: params['primary_release_year'] = year
    try:
        response = requests.get(discover_url, params=params)
        response.raise_for_status()
        data = response.json()
        disney_movies = []
        for movie_summary in data.get("results", [])[:10]:
            movie_id = movie_summary.get("id")
            if not movie_id: continue
            details_url = f"{tmdb_api_base_url}/movie/{movie_id}"
            details_params = {"api_key": TMDB_API_KEY, "language": "ru-RU"}
            details_response = requests.get(details_url, params=details_params)
            movie_details = details_response.json()
            poster_path = movie_details.get("poster_path")
            genres = [genre['name'] for genre in movie_details.get('genres', [])]
            companies = [comp['name'] for comp in movie_details.get('production_companies', [])]
            disney_movies.append({
                "id": movie_id, "title": movie_details.get("title"), "overview": movie_details.get("overview", "Сюжет не найден."),
                "image_url": f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None,
                "release_date": movie_details.get("release_date"), "vote_average": movie_details.get("vote_average"),
                "runtime": movie_details.get("runtime"), "genres": ", ".join(genres),
                "companies": ", ".join(companies), "budget": movie_details.get("budget"), "revenue": movie_details.get("revenue"),
            })
        return disney_movies
    except requests.exceptions.RequestException:
        return []

def get_person_details(query):
    if not TMDB_API_KEY or TMDB_API_KEY == "YOUR_TMDB_API_KEY_HERE": return []
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
            details_params = {"api_key": TMDB_API_KEY, "language": "ru-RU", "append_to_response": "movie_credits"}
            details_response = requests.get(details_url, params=details_params)
            details = details_response.json()
            credits = details.get('movie_credits', {}).get('cast', [])
            sorted_credits = sorted(credits, key=lambda x: x.get('popularity', 0), reverse=True)
            top_films = [f"{film.get('title')} ({film.get('release_date', 'N/A').split('-')[0]})" for film in sorted_credits[:7] if film.get('release_date')]
            profile_path = details.get("profile_path")
            results.append({
                "name": details.get("name"), "biography": details.get("biography", "Биография не найдена."),
                "image_url": f"https://image.tmdb.org/t/p/w500{profile_path}" if profile_path else None,
                "birthday": details.get("birthday"), "place_of_birth": details.get("place_of_birth"),
                "known_for": details.get("known_for_department"), "gender": details.get("gender"),
                "also_known_as": details.get("also_known_as", []), "filmography": top_films
            })
        return results
    except requests.exceptions.RequestException:
        return []

@st.cache_data
def get_movie_reviews(movie_id):
    if not movie_id: return []
    all_reviews = []
    for page in range(1, 4):
        reviews_url = f"{tmdb_api_base_url}/movie/{movie_id}/reviews"
        params = {"api_key": TMDB_API_KEY, "page": page}
        try:
            response = requests.get(reviews_url, params=params)
            response.raise_for_status()
            data = response.json()
            reviews = data.get("results", [])
            if not reviews:
                break
            all_reviews.extend(reviews)
        except requests.exceptions.RequestException:
            break
    return all_reviews

st.set_page_config(page_title="Умный поиск по миру Disney", layout="wide")
st.title("✨ Умный поиск по миру Disney")

if 'work_query' not in st.session_state:
    st.session_state.work_query = ""
    st.session_state.local_work_results = None
    st.session_state.internet_work_results = None

if 'performer_query' not in st.session_state:
    st.session_state.performer_query = ""
    st.session_state.local_performer_results = None
    st.session_state.internet_performer_results = None

dataframes = load_data()

if dataframes:
    st.sidebar.title("Навигация")
    search_type = st.sidebar.radio("Выберите раздел:", ("Произведение", "Исполнитель"))

    if search_type == "Произведение":
        st.header("🎬 Поиск по произведениям")
        query = st.text_input("Введите название произведения:", "Красавица и чудовище")
        if st.button("🔍 Найти", key="work_search"):
            st.session_state.work_query = query
            st.session_state.local_work_results = find_entity_by_name(query, dataframes["works"])
            st.session_state.internet_work_results = get_movie_details(query)

        if st.session_state.work_query:
            displayed_items = set()
            if st.session_state.local_work_results is not None:
                st.subheader("📊 Результаты из вашей базы данных")
                for index, row in st.session_state.local_work_results.iterrows():
                    year = int(row['Год выпуска']) if pd.notna(row['Год выпуска']) else 0
                    title_cleaned = row['Name'].split(':')[0].strip().lower()
                    displayed_items.add((title_cleaned, year))
                    details = (d[0] if (d := get_movie_details(row["Name"], year=year)) else None)
                    st.markdown(f"<div style='background-color:#28a745; padding: 10px; border-radius: 5px; color: white; margin-bottom: 10px;'><b>{row['Name']}</b></div>", unsafe_allow_html=True)
                    col1, col2 = st.columns([1, 2.5])
                    with col1:
                        if details and details['image_url'] and (img := get_image_as_base64(details['image_url'])): st.image(img)
                    with col2:
                        display_field("Год выпуска", year if year != 0 else "Не указан")
                        display_field("Тип", row.get('Тип')); display_field("Жанр", row.get('Жанр')); display_field("Рейтинг", row.get('Рейтинг'))
                        display_field("Возраст", row.get('Возраст')); display_field("Продолжительность", row.get('Продолжительность'))
                        display_field("Студия", clean_notion_links(row.get('Студия'))[0] if pd.notna(row.get('Студия')) else None)
                        display_field("Бюджет и сборы", row.get('Бюджет и сборы')); display_field("Награды", row.get('Награды'))
                    if details and details['overview']:
                        with st.expander("Сюжет"): st.write(details['overview'])
                    display_list(clean_notion_links(row.get('Персонажи')), "Персонажи"); display_list(clean_notion_links(row.get('Исполнители')), "Исполнители")
                    display_list(clean_notion_links(row.get('Песни')), "Песни")

                    if details:
                        movie_id = details['id']
                        if st.button("Показать отзывы", key=f"review_local_{index}"):
                            with st.spinner("Загрузка отзывов..."):
                                reviews = get_movie_reviews(movie_id)
                                if reviews:
                                    ratings = [r['author_details']['rating'] for r in reviews if r.get('author_details', {}).get('rating') is not None]
                                    if ratings:
                                        average_rating = sum(ratings) / len(ratings)
                                        st.metric(label="Средняя оценка по отзывам", value=f"{average_rating:.2f} / 10", delta=f"На основе {len(ratings)} оценок")
                                    else:
                                        st.info("В загруженных отзывах нет оценок.")

                                    st.write(f"#### Последние {min(len(reviews), 20)} отзывов:")
                                    latest_reviews = sorted(reviews, key=lambda r: r.get('created_at', ''), reverse=True)[:20]
                                    for review in latest_reviews:
                                        author, content, created_str = review.get('author', 'Аноним'), review.get('content', 'Нет текста.'), review.get('created_at')
                                        cleaned_content = clean_review_content(content)
                                        try:
                                            created_dt = datetime.datetime.strptime(created_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                                            date_display = created_dt.strftime("%d.%m.%Y в %H:%M")
                                        except (ValueError, TypeError): date_display = "Неизвестная дата"
                                        with st.expander(f"Отзыв от **{author}** ({date_display})"):
                                            st.markdown(cleaned_content)
                                else:
                                    st.info("Для этого фильма не найдено отзывов.")
                    st.divider()
            else:
                st.warning(f"В вашей базе ничего не найдено по запросу: '{st.session_state.work_query}'")

            st.subheader("🌐 Найдено в интернете (TMDb)")
            new_results_found = False
            if st.session_state.internet_work_results:
                for res in st.session_state.internet_work_results:
                    rel_date = res.get('release_date')
                    internet_year = int(rel_date.split('-')[0]) if rel_date and '-' in rel_date else 0
                    check_tuple = (res['title'].split(':')[0].strip().lower(), internet_year)
                    if check_tuple in displayed_items: continue
                    new_results_found = True
                    st.markdown(f"<div style='background-color:#17a2b8; padding: 10px; border-radius: 5px; color: white; margin-bottom: 10px;'><b>{res['title']}</b></div>", unsafe_allow_html=True)
                    col1, col2 = st.columns([1, 2.5])
                    with col1:
                        if res['image_url'] and (img := get_image_as_base64(res['image_url'])): st.image(img)
                    with col2:
                        display_field("Дата релиза", res.get('release_date')); display_field("Рейтинг зрителей", f"{res.get('vote_average'):.1f} / 10" if res.get('vote_average') else None)
                        display_field("Жанр", res.get('genres')); display_field("Продолжительность", res.get('runtime'), extra=" мин.")
                        display_field("Студия", res.get('companies')); display_field("Бюджет", f"${res.get('budget'):,}" if res.get('budget', 0) > 0 else "Не указан")
                        display_field("Сборы", f"${res.get('revenue'):,}" if res.get('revenue', 0) > 0 else "Не указаны")
                    with st.expander("Сюжет"): st.write(res.get('overview'))

                    movie_id = res['id']
                    if st.button("Показать отзывы", key=f"review_inet_{movie_id}"):
                        with st.spinner("Загрузка отзывов..."):
                            reviews = get_movie_reviews(movie_id)
                            if reviews:
                                ratings = [r['author_details']['rating'] for r in reviews if r.get('author_details', {}).get('rating') is not None]
                                if ratings:
                                    average_rating = sum(ratings) / len(ratings)
                                    st.metric(label="Средняя оценка по отзывам", value=f"{average_rating:.2f} / 10", delta=f"На основе {len(ratings)} оценок")
                                else:
                                    st.info("В загруженных отзывах нет оценок.")
                                
                                st.write(f"#### Последние {min(len(reviews), 20)} отзывов:")
                                latest_reviews = sorted(reviews, key=lambda r: r.get('created_at', ''), reverse=True)[:20]
                                for review in latest_reviews:
                                    author, content, created_str = review.get('author', 'Аноним'), review.get('content', 'Нет текста.'), review.get('created_at')
                                    cleaned_content = clean_review_content(content)
                                    try:
                                        created_dt = datetime.datetime.strptime(created_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                                        date_display = created_dt.strftime("%d.%m.%Y в %H:%M")
                                    except (ValueError, TypeError): date_display = "Неизвестная дата"
                                    with st.expander(f"Отзыв от **{author}** ({date_display})"):
                                        st.markdown(cleaned_content)
                            else:
                                st.info("Для этого фильма не найдено отзывов.")
                    st.divider()
            if not new_results_found:
                st.info("Все релевантные Disney-фильмы из интернета уже показаны в вашей базе данных или не найдены.")

    elif search_type == "Исполнитель":
        st.header("👤 Поиск по исполнителям")
        query = st.text_input("Введите имя исполнителя:", "Джонни Депп")
        if st.button("🔍 Найти", key="performer_search"):
            st.session_state.performer_query = query
            local_results = find_entity_by_name(query, dataframes["performers"])
            st.session_state.local_performer_results = local_results
            if local_results is None:
                st.session_state.internet_performer_results = get_person_details(query)
            else:
                st.session_state.internet_performer_results = None

        if st.session_state.performer_query:
            if st.session_state.local_performer_results is not None:
                st.subheader("📊 Результаты из вашей базы данных")
                for _, row in st.session_state.local_performer_results.iterrows():
                    details = (d[0] if (d := get_person_details(row["Name"])) else None)
                    st.markdown(f"<div style='background-color:#28a745; padding: 10px; border-radius: 5px; color: white; margin-bottom: 10px;'><b>{row['Name']}</b></div>", unsafe_allow_html=True)
                    col1, col2 = st.columns([1, 2.5])
                    with col1:
                        if details and details['image_url'] and (img := get_image_as_base64(details['image_url'])): st.image(img)
                    with col2:
                        display_field("Карьера", row.get('Карьера')); display_field("Дата рождения", row.get('Дата рождения'))
                        display_field("Знак зодиака", row.get('Знак зодиака')); display_field("Место рождения", row.get('Место рождения'))
                        display_field("Дата смерти", row.get('Дата смерти')); display_field("Место смерти", row.get('Место смерти'))
                        display_field("Рост", row.get('Рост'), extra=" м"); display_field("Всего проектов", row.get('Всего проектов'))
                    if details and details['biography']:
                        with st.expander("Биография"): st.write(details['biography'])
                    if details and details.get('filmography'):
                        display_list(details['filmography'], "Избранная фильмография (по популярности)")
                    display_list(clean_notion_links(row.get('Фильмография')), "Фильмография (из вашей базы)")
                    display_list(clean_notion_links(row.get('Сыгранные/озвученные персонажи')), "Персонажи")
                    st.divider()
            else:
                st.warning(f"В вашей базе ничего не найдено по запросу: '{st.session_state.performer_query}'. Выполняется поиск в интернете...")
                if st.session_state.internet_performer_results:
                    st.subheader("🌐 Найдено в интернете (TMDb)")
                    for res in st.session_state.internet_performer_results:
                        st.markdown(f"<div style='background-color:#17a2b8; padding: 10px; border-radius: 5px; color: white; margin-bottom: 10px;'><b>{res['name']}</b></div>", unsafe_allow_html=True)
                        col1, col2 = st.columns([1, 2.5])
                        with col1:
                            if res['image_url'] and (img := get_image_as_base64(res['image_url'])): st.image(img)
                        with col2:
                            display_field("Основная деятельность", res.get('known_for')); display_field("Дата рождения", res.get('birthday'))
                            display_field("Место рождения", res.get('place_of_birth'))
                            if res['biography']:
                                with st.expander("Биография"): st.write(res['biography'])
                        if res.get('filmography'):
                            display_list(res['filmography'], "Избранная фильмография (по популярности)")
                        st.divider()
                else:
                    st.error("В интернете также ничего не найдено.")
