import fitz  # PyMuPDF
import os
import shutil
import boto3
import base64
from PIL import Image
import io
import json
import tiktoken
import re
from datetime import date

from dotenv import load_dotenv
import os

load_dotenv()

# === CONFIGURAÇÃO AWS ===
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_DEFAULT_REGION = os.getenv('AWS_DEFAULT_REGION')

os.environ['AWS_ACCESS_KEY_ID'] = AWS_ACCESS_KEY_ID
os.environ['AWS_SECRET_ACCESS_KEY'] = AWS_SECRET_ACCESS_KEY
os.environ['AWS_DEFAULT_REGION'] = AWS_DEFAULT_REGION

MODEL_ID = 'arn:aws:bedrock:us-west-2:941100472524:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0'
bedrock = boto3.client('bedrock-runtime', region_name=AWS_DEFAULT_REGION)

# === DICIONÁRIO DE PERGUNTAS ===
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

# === PROMPT PARA O MODELO ===
def create_prompt():
    prompt = """
A imagem representa um currículo ou documento de candidato a emprego. 
Analise cuidadosamente o documento e extraia as seguintes informações:

"""
    
    for key, question in questions.items():
        prompt += f"- {key}: {question}\n"
    
    prompt += """
Retorne APENAS um JSON válido com as informações encontradas. Se alguma informação não estiver disponível, use null como valor.
Seja preciso e extraia apenas as informações que estão claramente visíveis no documento.

Formato de resposta:
{
"""
    
    for i, key in enumerate(questions.keys()):
        comma = "," if i < len(questions) - 1 else ""
        prompt += f'    "{key}": "valor_extraído_ou_null"{comma}\n'
    
    prompt += "}"
    
    return prompt

PROMPT_CURRICULUM = create_prompt()

# === FUNÇÕES DE UTILIDADE ===

def contar_tokens(texto, model_name="claude-instant-1"):
    enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(texto))

def image_to_base64(image_path):
    with Image.open(image_path) as img:
        img.thumbnail((1024, 1024))
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        return base64.b64encode(buffer.getvalue()).decode('utf-8'), len(buffer.getvalue())

def analyze_image_raw(image_base64, prompt):
    try:
        prompt_tokens = contar_tokens(prompt)
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1500,  # Aumentado para acomodar mais informações
            "temperature": 0.1,  # Reduzido para maior precisão
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_base64}},
                        {"type": "text", "text": prompt}
                    ]
                }
            ]
        }

        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(body),
            contentType='application/json',
            accept='application/json'
        )

        result = json.loads(response['body'].read())
        resposta = result['content'][0]['text']
        response_tokens = contar_tokens(resposta)
        return resposta, prompt_tokens, response_tokens
    except Exception as e:
        print(f"Erro ao analisar imagem: {str(e)}")
        return '{}', 0, 0

def split_pdf(pdf_path, output_dir):
    try:
        doc = fitz.open(pdf_path)
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        image_dir = os.path.join(output_dir, pdf_name)
        os.makedirs(image_dir, exist_ok=True)

        for page_num in range(doc.page_count):
            page = doc[page_num]
            matrix = fitz.Matrix(2.0, 2.0)  # Zoom
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            pix.save(os.path.join(image_dir, f"page{page_num + 1}.png"))

        doc.close()
        shutil.copy(pdf_path, os.path.join(image_dir, os.path.basename(pdf_path)))
        return image_dir

    except Exception as e:
        print(f"Erro ao dividir PDF '{pdf_path}': {e}")
        return None

def merge_curriculum_data(all_data):
    """
    Combina dados de múltiplas páginas do currículo,
    priorizando informações não-nulas
    """
    merged_data = {}
    
    for key in questions.keys():
        merged_data[key] = None
        
        # Procura o primeiro valor não-nulo para cada campo
        for page_data in all_data:
            if page_data.get(key) and page_data[key] not in [None, "null", "", "N/A"]:
                merged_data[key] = page_data[key]
                break
    
    return merged_data

# === EXECUÇÃO DO PROCESSO PARA UM PDF ESPECÍFICO ===

# Caminho para o PDF único a ser processado
pdf_path = 'content/_curriculos_testar/rs_anexos_4603_0902231675969963 (1).pdf'  # Altere para o caminho do seu currículo
output_dir = 'content/_imagens'
all_extracted_data = []
tokens_utilizados = 0

# Divide o PDF em imagens
pasta_imagens = split_pdf(pdf_path, output_dir)

if pasta_imagens:
    for imagem_nome in sorted(os.listdir(pasta_imagens)):
        if not imagem_nome.lower().endswith('.png'):
            continue

        caminho_imagem = os.path.join(pasta_imagens, imagem_nome)
        print(f"Analisando imagem: {caminho_imagem}")
        
        image_base64, image_bytes_len = image_to_base64(caminho_imagem)
        resposta_bruta, prompt_tokens, resposta_tokens = analyze_image_raw(image_base64, PROMPT_CURRICULUM)

        tokens_utilizados = tokens_utilizados + (image_bytes_len/4 + prompt_tokens + resposta_tokens)

        try:
            # Extrai JSON da resposta
            json_str = re.search(r'\{.*\}', resposta_bruta, re.DOTALL)
            if json_str:
                json_data = json.loads(json_str.group(0))
                all_extracted_data.append(json_data)
                print(f"Dados extraídos da página {imagem_nome}: {len([k for k, v in json_data.items() if v and v != 'null'])} campos preenchidos")
            else:
                print(f"Nenhum JSON válido encontrado na resposta para {imagem_nome}")
                print("Resposta bruta:", resposta_bruta[:200] + "...")
                
        except Exception as e:
            print(f"Erro ao processar resposta do modelo para {imagem_nome}: {e}")
            print("Resposta bruta:", resposta_bruta[:200] + "...")

# === COMBINAÇÃO E RESULTADOS FINAIS ===
if all_extracted_data:
    dados_finais = merge_curriculum_data(all_extracted_data)
    
    print("\n===== DADOS EXTRAÍDOS DO CURRÍCULO =====")
    for key, value in dados_finais.items():
        if value and value != "null":
            print(f"{key.upper()}: {value}")
    
    print(f"\n===== ESTATÍSTICAS =====")
    campos_preenchidos = len([v for v in dados_finais.values() if v and v != "null"])
    print(f"Campos preenchidos: {campos_preenchidos}/{len(questions)}")
    print(f"Total de tokens utilizados: {tokens_utilizados}")
    
    model_cost = 0.003  # per 1k tokens
    print(f"Custo estimado do modelo: ${(tokens_utilizados/1000) * model_cost:.4f}")

    # Salva os resultados em um arquivo JSON
    output_file = os.path.join(pasta_imagens, 'dados_curriculum.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(dados_finais, f, indent=4, ensure_ascii=False)
    
    print(f"\nResultados salvos em: {output_file}")
    
else:
    print("Nenhum dado foi extraído do documento.")