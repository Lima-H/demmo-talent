import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import os
import tempfile
import pandas as pd
from modelo_curriculo import analisar_curriculo_por_links

# Configurações Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive.file']
FOLDER_ID = "1kvWh4CxWZsmovOBZat7QzgY9kw26o7RE"  # Sua pasta

def authenticate():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds

def upload_image_and_get_public_link(path_image, folder_id, return_id=False):
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)

    file_metadata = {
        'name': os.path.basename(path_image),
        'parents': [folder_id]
    }
    media = MediaFileUpload(path_image, mimetype='image/png')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    file_id = file.get('id')

    # Torna o arquivo público
    permission = {
        'type': 'anyone',
        'role': 'reader'
    }
    service.permissions().create(fileId=file_id, body=permission).execute()

    # Gera o link público
    public_url = f"https://drive.google.com/uc?id={file_id}"
    if return_id:
        return public_url, file_id
    return public_url

def formatar_dados_para_tabela(dados_curriculo):
    """Converte os dados do currículo em formato tabular para exibição"""
    if "erro" in dados_curriculo:
        return None, None, None
    
    def formatar_valor(valor):
        """Formata valores vazios ou 'Não informado' para '-'"""
        if valor == 'Não informado' or not valor or str(valor).strip() == '':
            return '-'
        return valor
    
    # Dados pessoais
    dados_pessoais = {
        'Campo': ['Nome', 'Email', 'CPF', 'Celular', 'Telefone', 'Idade', 'PIS', 'RG', 'CTPS', 'Habilitação', 'Estado Civil', 'Sexo'],
        'Valor': [
            formatar_valor(dados_curriculo.get('nome')),
            formatar_valor(dados_curriculo.get('email')),
            formatar_valor(dados_curriculo.get('cpf')),
            formatar_valor(dados_curriculo.get('celular')),
            formatar_valor(dados_curriculo.get('telefone')),
            formatar_valor(dados_curriculo.get('idade')),
            formatar_valor(dados_curriculo.get('pis')),
            formatar_valor(dados_curriculo.get('rg')),
            formatar_valor(dados_curriculo.get('ctps')),
            formatar_valor(dados_curriculo.get('habilitacao')),
            formatar_valor(dados_curriculo.get('estado_civil')),
            formatar_valor(dados_curriculo.get('sexo'))
        ]
    }
    
    # Endereço
    endereco = {
        'Campo': ['UF', 'Cidade', 'CEP', 'Logradouro', 'Número', 'Complemento'],
        'Valor': [
            formatar_valor(dados_curriculo.get('uf')),
            formatar_valor(dados_curriculo.get('cidade')),
            formatar_valor(dados_curriculo.get('cep')),
            formatar_valor(dados_curriculo.get('logradouro')),
            formatar_valor(dados_curriculo.get('numero')),
            formatar_valor(dados_curriculo.get('complemento'))
        ]
    }
    
    # Formação
    formacao = {
        'Campo': ['Nível de Ensino', 'Situação', 'Curso', 'Série', 'Início (Mês)', 'Início (Ano)', 'Fim (Mês)', 'Fim (Ano)', 'Instituição', 'Carga Horária'],
        'Valor': [
            formatar_valor(dados_curriculo.get('nivel_ensino')),
            formatar_valor(dados_curriculo.get('situacao')),
            formatar_valor(dados_curriculo.get('curso')),
            formatar_valor(dados_curriculo.get('serie')),
            formatar_valor(dados_curriculo.get('inicio_mes')),
            formatar_valor(dados_curriculo.get('inicio_ano')),
            formatar_valor(dados_curriculo.get('fim_mes')),
            formatar_valor(dados_curriculo.get('fim_ano')),
            formatar_valor(dados_curriculo.get('instituicao')),
            formatar_valor(dados_curriculo.get('carga_horaria'))
        ]
    }
    
    return pd.DataFrame(dados_pessoais), pd.DataFrame(endereco), pd.DataFrame(formacao)

# --- INTERFACE PRINCIPAL ---
st.set_page_config(page_title="Análise de Currículos", page_icon="📄", layout="wide")
st.title("📄 Análise Inteligente de Currículos")

# --- SIDEBAR ---
with st.sidebar:
    st.header("ℹ️ Informações")
    st.info("""
    Esta ferramenta analisa currículos em PDF e extrai:
    - 👤 Dados pessoais
    - 📍 Informações de endereço
    - 🎓 Dados de formação
    - 💼 Objetivos profissionais
    """)

    st.header("📋 Como usar")
    st.markdown("""
    1. Faça upload do arquivo PDF do currículo
    2. Clique em "Processar Currículo com IA"
    3. Aguarde o processamento
    4. Veja os dados extraídos organizados
    """)

st.markdown("Faça upload de um PDF de currículo e extraia automaticamente todas as informações estruturadas.")

uploaded_file = st.file_uploader("Selecione o PDF do Currículo", type=['pdf'])

if uploaded_file is not None:
    st.success(f"Arquivo carregado: {uploaded_file.name}")

    if st.button("🚀 Processar Currículo com IA"):
        with st.spinner("🔄 Convertendo PDF, enviando imagens e analisando currículo... Isso pode levar alguns minutos."):
            # 1. Converter PDF em imagens
            pdf_bytes = uploaded_file.read()
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            imagens = []
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                pix = page.get_pixmap()
                img_bytes = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_bytes))
                imagens.append(img)
                
            links_publicos = []
            file_ids = []
            
            for i, img in enumerate(imagens):
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    img.save(tmp.name, format="PNG")
                    tmp.flush()
                    link, file_id = upload_image_and_get_public_link(tmp.name, FOLDER_ID, return_id=True)
                    links_publicos.append(link)
                    file_ids.append(file_id)
                os.unlink(tmp.name)
            
            # 2. Analisar currículo com IA
            dados_curriculo, total_tokens, preco_total = analisar_curriculo_por_links(links_publicos)
        
        if "erro" not in dados_curriculo:
            st.success("✅ Processamento concluído!")

            # --- CARDS DE RESUMO ---
            st.subheader("👤 Resumo do Candidato")
            
            # Nome
            nome = dados_curriculo.get('nome', '-')
            nome_display = nome if nome != 'Não informado' else '-'
            st.metric(
                label="👤 Nome",
                value=nome_display
            )
            
            # Idade
            idade = dados_curriculo.get('idade', '-')
            idade_display = f"{idade} anos" if idade != 'Não informado' and idade != '-' else '-'
            st.metric(
                label="🎂 Idade",
                value=idade_display
            )
            
            # Escolaridade
            nivel_ensino = dados_curriculo.get('nivel_ensino', '-')
            nivel_display = nivel_ensino if nivel_ensino != 'Não informado' else '-'
            st.metric(
                label="🎓 Escolaridade",
                value=nivel_display
            )
            
            # E-mail
            email = dados_curriculo.get('email', '-')
            email_display = email if email != 'Não informado' else '-'
            st.metric(
                label="📧 E-mail",
                value=email_display
            )

            # --- OBJETIVOS E RESUMO PROFISSIONAL ---
            st.markdown("---")
            st.subheader("💼 Perfil Profissional")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**🎯 Objetivos Profissionais:**")
                objetivos = dados_curriculo.get('objetivos_profissionais', '-')
                objetivos_display = objetivos if objetivos != 'Não informado' else '-'
                st.write(objetivos_display)
            
            with col2:
                st.markdown("**📝 Resumo Profissional:**")
                resumo = dados_curriculo.get('resumo_profissional', '-')
                resumo_display = resumo if resumo != 'Não informado' else '-'
                st.write(resumo_display)
            
            # Pretensão salarial
            pretensao = dados_curriculo.get('pretensao_salarial', '-')
            if pretensao != 'Não informado' and pretensao != '-':
                st.markdown(f"**💰 Pretensão Salarial:** {pretensao}")

            # --- TABELAS DETALHADAS ---
            st.markdown("---")
            st.subheader("📊 Dados Detalhados")

            df_pessoais, df_endereco, df_formacao = formatar_dados_para_tabela(dados_curriculo)
            
            # Abas para organizar as informações
            tab1, tab2, tab3 = st.tabs(["👤 Dados Pessoais", "📍 Endereço", "🎓 Formação"])
            
            with tab1:
                if df_pessoais is not None:
                    st.dataframe(df_pessoais, use_container_width=True, hide_index=True)
            
            with tab2:
                if df_endereco is not None:
                    st.dataframe(df_endereco, use_container_width=True, hide_index=True)
            
            with tab3:
                if df_formacao is not None:
                    st.dataframe(df_formacao, use_container_width=True, hide_index=True)

            # # --- INFORMAÇÕES DO PROCESSAMENTO ---
            # st.markdown("---")
            # st.subheader("💡 Informações do Processamento")

            # col1, col2, col3 = st.columns(3)
            # with col1:
            #     st.metric("📄 Páginas Processadas", len(imagens))
            # with col2:
            #     st.metric("🔢 Tokens Utilizados", f"{total_tokens:,.0f}")
            # with col3:
            #     st.metric("💵 Custo Estimado", f"${preco_total:.4f}")

        else:
            st.error(f"❌ Erro no processamento: {dados_curriculo['erro']}")
            if "resposta_bruta" in dados_curriculo:
                with st.expander("Ver resposta bruta para debug"):
                    st.text(dados_curriculo['resposta_bruta'])

        # --- DELETA AS IMAGENS DO GOOGLE DRIVE ---
        try:
            creds = authenticate()
            service = build('drive', 'v3', credentials=creds)
            for file_id in file_ids:
                try:
                    service.files().delete(fileId=file_id).execute()
                except Exception as e:
                    st.warning(f"Não foi possível deletar o arquivo {file_id}: {e}")
        except Exception as e:
            st.warning(f"Erro ao limpar arquivos temporários: {e}")