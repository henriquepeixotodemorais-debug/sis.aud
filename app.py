import streamlit as st
import pandas as pd
import requests
import base64
import io

# ---------------------------------------------------------
# CONFIGURAÇÃO DO TEMA
# ---------------------------------------------------------
st.set_page_config(layout="wide", initial_sidebar_state="expanded")
st.markdown("""
    <style>
        :root { color-scheme: light; }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# CONFIGURAÇÕES DO GITHUB VIA SECRETS
# ---------------------------------------------------------
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
GITHUB_USER = st.secrets["GITHUB_USER"]
GITHUB_REPO = st.secrets["GITHUB_REPO"]
GITHUB_FILE = "baseaud.csv"

RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/{GITHUB_FILE}"
API_URL = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{GITHUB_FILE}"

# ---------------------------------------------------------
# LIMPA CACHE AO DIGITAR QUALQUER SENHA
# ---------------------------------------------------------
password = st.text_input("Insira a chave de acesso", type="password")

if password:
    st.cache_data.clear()

# ---------------------------------------------------------
# FUNÇÃO PARA CARREGAR CSV DO GITHUB (ACEITA , E ;)
# ---------------------------------------------------------
@st.cache_data(ttl=1)
def load_csv_from_github():
    response = requests.get(RAW_URL)
    if response.status_code != 200:
        st.error("Erro ao carregar CSV do GitHub.")
        st.stop()

    text = response.text

    # Tenta detectar automaticamente o separador
    try:
        df = pd.read_csv(io.StringIO(text), dtype=str, sep=None, engine="python")
    except:
        try:
            df = pd.read_csv(io.StringIO(text), dtype=str, sep=",")
        except:
            df = pd.read_csv(io.StringIO(text), dtype=str, sep=";")

    return df.fillna("")

# ---------------------------------------------------------
# FUNÇÃO DE UPLOAD À PROVA DE ERRO 409 (CONFLICT)
# ---------------------------------------------------------
def upload_csv_to_github(uploaded_file):

    content = uploaded_file.getvalue()
    encoded = base64.b64encode(content).decode()

    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    # 1. Buscar SHA atual
    def get_sha():
        r = requests.get(API_URL, headers=headers)
        if r.status_code == 200:
            return r.json().get("sha")
        return None

    sha = get_sha()

    # 2. Montar payload
    def make_payload(sha_value):
        payload = {
            "message": "Atualização automática do CSV via Streamlit",
            "content": encoded,
            "branch": "main"
        }
        if sha_value:
            payload["sha"] = sha_value
        return payload

    # 3. Tentar enviar
    payload = make_payload(sha)
    response = requests.put(API_URL, json=payload, headers=headers)

    # 4. Se der erro 409, buscar SHA de novo e tentar novamente
    if response.status_code == 409:
        new_sha = get_sha()
        payload = make_payload(new_sha)
        response = requests.put(API_URL, json=payload, headers=headers)

    # 5. Resultado final
    if response.status_code in [200, 201]:
        st.success("CSV atualizado com sucesso no GitHub! Recarregando...")
        st.cache_data.clear()
        st.rerun()
    else:
        st.error(f"Erro ao enviar arquivo: {response.text}")

# ---------------------------------------------------------
# MODO sisbase — APENAS UPLOAD DO CSV
# ---------------------------------------------------------
if password == "sisbase":
    st.header("🗂 Painel de Administração da Base")

    st.info("Use este painel para atualizar o arquivo baseaud.csv no GitHub.")

    uploaded = st.file_uploader("📤 Enviar novo CSV", type=["csv"])

    if uploaded:
        upload_csv_to_github(uploaded)

    st.stop()

# ---------------------------------------------------------
# CARREGAR CSV DO GITHUB
# ---------------------------------------------------------
df = load_csv_from_github()

# ---------------------------------------------------------
# PREPARAÇÃO DOS DADOS
# ---------------------------------------------------------
df["dia"] = pd.to_datetime(df["data e horário"]).dt.strftime("%d/%m/%y")
df = df.sort_values(["dia", "sala de audiência", "data e horário"])

# ---------------------------------------------------------
# FILTRO DE SALAS
# ---------------------------------------------------------
todas_salas = sorted(df["sala de audiência"].unique())

salas_selecionadas = st.multiselect(
    "Filtrar salas:",
    options=todas_salas,
    default=todas_salas,
)

if len(salas_selecionadas) == 0:
    st.warning("Selecione ao menos uma sala.")
    st.stop()

# ---------------------------------------------------------
# FUNÇÃO PARA MONTAR O BOX DE CADA PROCESSO
# ---------------------------------------------------------
def render_process_box(process_df, show_sensitive=False):
    row0 = process_df.iloc[0]

    with st.container(border=True):
        st.markdown(f"### ⏰ {row0['data e horário']}")
        st.markdown(f"**Processo:** {row0['número do processo relacionado']}")
        st.markdown(f"**Tipo:** {row0['parte a ser ouvida ou tipo de processo']}")
        st.markdown(f"[🔗 Link do processo]({row0['link do processo']})")
        st.markdown(f"**Dimensão:** {row0['dimensão da audiência']}")

        with st.expander("Resumo dos fatos"):
            st.write(row0["resumo dos fatos"])

        if show_sensitive:
            st.markdown("#### Partes:")

            for _, r in process_df.iloc[1:].iterrows():
                parte = r["parte a ser ouvida ou tipo de processo"]
                telefone = r["telefone da parte"]
                intimacao = r["estado da intimação"]

                st.markdown(
                    f"""
                    <div style="margin-bottom:10px;">
                        <div style="font-weight:700; font-size:16px;">• {parte}</div>
                        <div style="margin-left:20px; font-size:14px; color:#444;">
                            Telefone: {telefone}<br>
                            Intimação: {intimacao}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

# ---------------------------------------------------------
# RENDERIZAÇÃO POR DIA E SALA
# ---------------------------------------------------------
def render_day(df_dia, show_sensitive):

    salas = [s for s in sorted(df_dia["sala de audiência"].unique()) if s in salas_selecionadas]

    cols = st.columns(len(salas))

    for idx, sala in enumerate(salas):
        with cols[idx]:
            st.markdown(f"### 🏛 Sala {sala}")

            df_sala = df_dia[df_dia["sala de audiência"] == sala]

            for processo, bloco in df_sala.groupby("número do processo relacionado"):
                render_process_box(bloco, show_sensitive)

# ---------------------------------------------------------
# SECRETÁRIOS
# ---------------------------------------------------------
if password == "sissecret":
    st.header("📌 Painel dos Secretários")

    for dia in df["dia"].unique():
        df_dia = df[df["dia"] == dia]

        if any(df_dia["sala de audiência"].isin(salas_selecionadas)):
            st.markdown(f"## 📅 {dia}")
            render_day(df_dia, show_sensitive=True)

# ---------------------------------------------------------
# AUTORIDADES
# ---------------------------------------------------------
elif password == "sisautoridades":
    st.header("⚖ Painel das Autoridades")

    for dia in df["dia"].unique():
        df_dia = df[df["dia"] == dia]

        if any(df_dia["sala de audiência"].isin(salas_selecionadas)):
            st.markdown(f"## 📅 {dia}")
            render_day(df_dia, show_sensitive=False)

# ---------------------------------------------------------
# ACESSO NEGADO
# ---------------------------------------------------------
elif password.strip() != "":
    st.error("Chave inválida.")