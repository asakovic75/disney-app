import streamlit as st
import pandas as pd
import requests
import re
import base64
from io import BytesIO
import datetime

st.set_page_config(page_title="Умный поиск по миру Disney", layout="wide")

css_styles = """
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;700&display=swap');

body, .stApp {
    font-family: 'Nunito', sans-serif !important;
}

h1, h2, h3 {
    text-align: center;
}
h1 { font-size: 1.5rem !important; }
h2 { font-size: 1.1rem !important; }
h3 { font-size: 1.0rem !important; }

[data-testid="stTextInput"] input {
    font-size: 0.9rem;
    padding: 8px 12px;
}

.stButton button {
    font-size: 0.9rem;
    padding: 8px 16px;
}

/* Стили для обычного текста и выпадающих списков */
div[data-testid="stMarkdownContainer"] p, .st-emotion-cache-1hver2b, .st-emotion-cache-pa7p7d {
    font-size: 0.9rem !important;
}
"""
st.markdown(f"<style>{css_styles}</style>", unsafe_allow_html=True)


TMDB_API_KEY = st.secrets.get("TMDB_API_KEY", "YOUR_TMDB_API_KEY_HERE")
tmdb_api_base_url = "https://api.themoviedb.org/3"
DISNEY_COMPANY_IDS_STR = "2|3|6125|420|1|10282|127928"

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
    cleaned_text = re.sub(r"\s\(\?pvs=.*?\)", "", cleaned_text)
    items = [item.strip().strip('"') for item in cleaned_text.split(',')]
    return items

def display_field(label, value, extra=""):
    if pd.notna(value) and str(value).strip() not in ['', '-']:
        st.write(f"**{label}:** {value}{extra}")

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
        for movie_summary in data.get("results", [])[:5]:
            movie_id = movie_summary.get("id")
            if not movie_id: continue
            details_url = f"{tmdb_api_base_url}/movie/{movie_id}"
            details_params = {"api_key": TMDB_API_KEY, "language": "ru-RU"}
            details_response = requests.get(details_url, params=details_params)
            movie_details = details_response.json()
            poster_path = movie_details.get("poster_path")
            disney_movies.append({
                "id": movie_id, "title": movie_details.get("title"), "overview": movie_details.get("overview", "Сюжет не найден."),
                "image_url": f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None,
                "release_date": movie_details.get("release_date")
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
        for person_summary in data.get("results", [])[:5]:
            person_id = person_summary.get("id")
            if not person_id: continue
            details_url = f"{tmdb_api_base_url}/person/{person_id}"
            details_params = {"api_key": TMDB_API_KEY, "language": "ru-RU"}
            details_response = requests.get(details_url, params=details_params)
            details = details_response.json()
            profile_path = details.get("profile_path")
            results.append({
                "name": details.get("name"), "biography": details.get("biography", "Биография не найдена."),
                "image_url": f"https://image.tmdb.org/t/p/w500{profile_path}" if profile_path else None,
                "birthday": details.get("birthday"), "known_for": details.get("known_for_department")
            })
        return results
    except requests.exceptions.RequestException:
        return []

st.title("✨ Умный поиск")

if 'work_query' not in st.session_state: st.session_state.work_query = ""
if 'performer_query' not in st.session_state: st.session_state.performer_query = ""

dataframes = load_data()

if dataframes:
    search_type = st.radio("Выберите раздел:", ("Произведения", "Исполнители"), horizontal=True, label_visibility="collapsed")
    
    st.markdown("---")

    if search_type == "Произведения":
        query = st.text_input("Введите название произведения:", key="work_input", label_visibility="collapsed", placeholder="Введите название произведения...")
        if st.button("🔍 Найти", key="work_search", use_container_width=True):
            st.session_state.work_query = query
            with st.spinner("Идет поиск..."):
                st.session_state.local_work_results = find_entity_by_name(query, dataframes["works"])
                st.session_state.internet_work_results = get_movie_details(query)
        
        if st.session_state.work_query:
            displayed_items = set()
            if st.session_state.get('local_work_results') is not None:
                st.subheader("📊 Найдено в вашей базе")
                for _, row in st.session_state.local_work_results.iterrows():
                    year = int(row['Год выпуска']) if pd.notna(row['Год выпуска']) else 0
                    title_cleaned = row['Name'].split(':')[0].strip().lower()
                    displayed_items.add((title_cleaned, year))
                    details = (d[0] if (d := get_movie_details(row["Name"], year=year)) else None)
                    st.markdown(f"**{row['Name']}**")
                    col1, col2 = st.columns([1, 2])
                    if details and details['image_url']: col1.image(details['image_url'])
                    with col2:
                        display_field("Год", year if year != 0 else "-")
                        display_field("Тип", row.get('Тип'))
                        if details and details['overview']:
                            with st.expander("Сюжет"): st.write(details['overview'])
                    st.divider()

            st.subheader("🌐 Найдено в интернете")
            new_results_found = False
            if st.session_state.get('internet_work_results'):
                for res in st.session_state.internet_work_results:
                    rel_date = res.get('release_date')
                    internet_year = int(rel_date.split('-')[0]) if rel_date else 0
                    check_tuple = (res['title'].split(':')[0].strip().lower(), internet_year)
                    if check_tuple in displayed_items: continue
                    new_results_found = True
                    st.markdown(f"**{res['title']}**")
                    col1, col2 = st.columns([1, 2])
                    if res['image_url']: col1.image(res['image_url'])
                    with col2:
                        display_field("Релиз", res.get('release_date'))
                        with st.expander("Сюжет"): st.write(res.get('overview'))
                    st.divider()
            if not new_results_found:
                st.info("Новых произведений в интернете не найдено.")

    elif search_type == "Исполнители":
        query = st.text_input("Введите имя исполнителя:", key="performer_input", label_visibility="collapsed", placeholder="Введите имя исполнителя...")
        if st.button("🔍 Найти", key="performer_search", use_container_width=True):
            st.session_state.performer_query = query
            with st.spinner("Идет поиск..."):
                st.session_state.local_performer_results = find_entity_by_name(query, dataframes["performers"])
                st.session_state.internet_performer_results = get_person_details(query)
        
        if st.session_state.performer_query:
            local_names = set()
            if st.session_state.get('local_performer_results') is not None:
                st.subheader("📊 Найдено в вашей базе")
                for _, row in st.session_state.local_performer_results.iterrows():
                    local_names.add(row['Name'].lower())
                    details = (d[0] if (d := get_person_details(row["Name"])) else None)
                    st.markdown(f"**{row['Name']}**")
                    col1, col2 = st.columns([1, 2])
                    if details and details['image_url']: col1.image(details['image_url'])
                    with col2:
                        display_field("Карьера", row.get('Карьера'))
                        display_field("Дата рождения", row.get('Дата рождения'))
                        if details and details['biography']:
                            with st.expander("Биография"): st.write(details['biography'])
                    st.divider()

            st.subheader("🌐 Найдено в интернете")
            new_results_found = False
            if st.session_state.get('internet_performer_results'):
                for res in st.session_state.internet_performer_results:
                    if res['name'].lower() in local_names: continue
                    new_results_found = True
                    st.markdown(f"**{res['name']}**")
                    col1, col2 = st.columns([1, 2])
                    if res['image_url']: col1.image(res['image_url'])
                    with col2:
                        display_field("Деятельность", res.get('known_for'))
                        display_field("Дата рождения", res.get('birthday'))
                        if res['biography']:
                            with st.expander("Биография"): st.write(res['biography'])
                    st.divider()
            if not new_results_found:
                st.info("Новых исполнителей в интернете не найдено.")
