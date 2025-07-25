import os
import fitz
import docx
from pdfplumber import open as open_pdf
from concurrent.futures import ThreadPoolExecutor
import easyocr
import openai
import json
from datetime import date
from dotenv import load_dotenv

def extract_text_from_pdf(pdf_path):
    """Extrai texto de um arquivo PDF."""
    all_text = ""
    try:
        with open_pdf(pdf_path) as pdf:
            for page in pdf.pages:
                all_text += page.extract_text() or ""  
    except Exception as e:
        print(f"Erro ao processar PDF {pdf_path}: {e}")
    return all_text


def extract_text_from_docx(docx_path):
    all_text = ""
    try:
        doc = docx.Document(docx_path)
        all_text = "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        print(f"Erro ao processar DOCX {docx_path}: {e}")
    return all_text


def extract_text_from_image(image_path):
    all_text = ""
    try:
        reader = easyocr.Reader(['pt'])
        result = reader.readtext(image_path)
        all_text = " ".join([res[1] for res in result])
    except Exception as e:
        print(f"Erro ao processar imagem {image_path}: {e}")
    return all_text


def extract_text(file_path):
    file_extension = os.path.splitext(file_path)[1].lower()
    if file_extension == ".pdf":
        return extract_text_from_pdf(file_path)
    elif file_extension == ".docx":
        return extract_text_from_docx(file_path)
    elif file_extension in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
        return extract_text_from_image(file_path)
    else:
        print(f"Formato não suportado: {file_extension}")
        return ""


def process_files_in_folder(input_folder):
    files = [os.path.join(input_folder, f) for f in os.listdir(input_folder)
             if os.path.isfile(os.path.join(input_folder, f)) and f.lower().endswith(('.pdf', '.docx', '.jpg', '.png', '.bmp', '.tiff'))]
    
    extracted_texts = {}
    
    def process_file(file_path):
        base_filename = os.path.splitext(os.path.basename(file_path))[0]
        extracted_texts[base_filename] = extract_text(file_path)
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        executor.map(process_file, files)
    
    return extracted_texts

# Diretório de entrada
diretorio_origem = "diretorio_destino/curriculos_ia"

document_texts = process_files_in_folder(diretorio_origem)

# Agora os textos extraídos estão armazenados no dicionário document_texts

# Carregar chave da API
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

questions = {
    "nome": "Qual é o nome completo do candidato?",
    "email": "Qual é o email válido do candidato? (Exemplo: exemplo@dominio.com)",
    "cpf": "Qual é o CPF válido do candidato? Formato esperado: 123.456.789-00.",
    "celular": "Qual é o número de celular válido do candidato? Formato esperado: (XX)XXXXX-XXXX.",
    "telefone": "Qual é o número de telefone fixo válido do candidato? Formato esperado: (XX)XXXX-XXXX.",
    "idade": f"Qual é a idade do candidato? Se houver apenas a data de nascimento, faça a diferença com a data: {date.today()}. Formato esperado: XX Anos",
    "pis": "Qual é o número do PIS do candidato? Deve ser um número válido com 11 dígitos.",
    "rg": "Qual é o número do RG do candidato?",
    "ctps": "Qual é o número da Carteira de Trabalho do candidato?",
    "habilitacao": "Qual é a categoria da habilitação do candidato? (Exemplo: A, B, AB, C, etc.)",
    "estado_civil": "Qual é o estado civil do candidato? (Exemplo: solteiro(a), casado(a), etc.)",
    "sexo": "Qual é o sexo do candidato? (Masculino ou Feminino)",
    "objetivos_profissionais": "Quais são os objetivos profissionais do candidato? Forneça um resumo objetivo.",
    "resumo_profissional": "Qual é o resumo profissional do candidato? Inclua habilidades e experiências relevantes.",
    "pretensao_salarial": "Qual é a pretensão salarial do candidato? Informe o valor em moeda.",
    "uf": "Qual é o estado de residência do candidato? (Exemplo: SP, RJ, MG, etc.)",
    "cidade": "Qual é a cidade de residência do candidato?",
    "cep": "Qual é o CEP do endereço do candidato? Formato esperado: XXXXX-XXX.",
    "logradouro": "Qual é o logradouro do endereço do candidato? (Exemplo: Rua, Avenida, etc.)",
    "numero": "Qual é o número do imóvel do candidato? Apenas números.",
    "complemento": "Qual é o complemento do endereço do candidato? (Exemplo: apartamento, bloco, etc.)",
    "nivel_ensino": "Qual é o nível de ensino do candidato? (Exemplo: médio completo, superior completo, etc.)",
    "situacao": "Qual é a situação atual do nível de ensino do candidato? (Exemplo: cursando, concluído, etc.)",
    "curso": "Qual é o nome do curso realizado pelo candidato?",
    "serie": "Qual é a série ou etapa de ensino do candidato? (Exemplo: 1º ano, 2º semestre, etc.)",
    "inicio_mes": "Qual é o mês de início do curso do candidato? (Exemplo: janeiro, fevereiro, etc.)",
    "inicio_ano": "Qual é o ano de início do curso do candidato?",
    "fim_mes": "Qual é o mês de término do curso do candidato? (Exemplo: dezembro, junho, etc.)",
    "fim_ano": "Qual é o ano de término do curso do candidato?",
    "instituicao": "Qual é o nome da instituição de ensino frequentada pelo candidato?",
    "carga_horaria": "Qual é a carga horária total do curso do candidato? Informe em horas.",
}

def ask_chatgpt(question, text):
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Você é um assistente que extrai informações específicas do texto. Só traga a informação; se não houver, imprima 'null'."},
            {"role": "user", "content": f"{question}\n\nTexto:\n{text}"}
        ]
    )
    answer = response.choices[0].message.content
    return answer.strip() if answer.strip() else None

diretorio_destino = "resposta_gpt"
os.makedirs(diretorio_destino, exist_ok=True)

results = {}

for filename, text_content in document_texts.items():
    print(f"Processando o arquivo: {filename}")
    answers = {key: ask_chatgpt(question, text_content) for key, question in questions.items()}
    results[filename] = {key: value if value else None for key, value in answers.items()}
    
    json_filename = os.path.join(diretorio_destino, f"{filename}.json")
    with open(json_filename, 'w', encoding='utf-8') as json_file:
        json.dump(results[filename], json_file, indent=4, ensure_ascii=False)
    
    print(f"Respostas salvas em {json_filename}")