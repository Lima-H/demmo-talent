import os 
from dotenv import load_dotenv 
from pathlib import Path
from datetime import date
import json
import re
import requests
from typing import Dict, Any
from openai import OpenAI

# Carrega as variáveis de ambiente
dotenv_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path)
api_key = os.getenv("OPENAI_API_KEY")

# Inicializa o cliente OpenAI
client = OpenAI(api_key=api_key)

def link_drive_direto(link: str) -> str:
    """Converte link do Google Drive para formato direto."""
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', link)
    if match:
        file_id = match.group(1)
        return f"https://drive.google.com/uc?export=view&id={file_id}"
    return link

def validar_url_imagem(url: str) -> bool:
    """Valida se a URL da imagem é acessível."""
    try:
        response = requests.head(url, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Aviso: Não foi possível validar a URL: {e}")
        return True  # Assume que está ok se não conseguir validar

def extrair_dados_curriculo(imagem_url: str) -> Dict[str, Any]:
    """
    Extrai dados estruturados de um currículo em imagem usando OpenAI Vision.
    Envia apenas a URL da imagem, sem codificação.
    """
    
    if not api_key:
        return {"erro": "API Key não configurada"}
    
    try:
        # Converte link do Drive se necessário
        if "drive.google.com" in imagem_url:
            imagem_url = link_drive_direto(imagem_url)
            print(f"URL convertida: {imagem_url}")
        
        # Valida a URL (opcional)
        validar_url_imagem(imagem_url)
        
        # Estrutura de dados esperada
        campos_json = {
            "nome": "Nome completo",
            "email": "Email válido",
            "cpf": "CPF no formato 123.456.789-00",
            "celular": "Celular no formato (XX)XXXXX-XXXX",
            "telefone": "Telefone fixo no formato (XX)XXXX-XXXX",
            "idade": "Idade em anos",
            "pis": "Número do PIS",
            "rg": "Número do RG",
            "ctps": "Número da Carteira de Trabalho",
            "habilitacao": "Categoria da habilitação",
            "estado_civil": "Estado civil",
            "sexo": "Sexo",
            "objetivos_profissionais": "Objetivos profissionais",
            "resumo_profissional": "Resumo profissional",
            "pretensao_salarial": "Pretensão salarial",
            "uf": "Estado (sigla)",
            "cidade": "Cidade",
            "cep": "CEP no formato XXXXX-XXX",
            "logradouro": "Logradouro",
            "numero": "Número do endereço",
            "complemento": "Complemento do endereço",
            "nivel_ensino": "Nível de ensino",
            "situacao": "Situação do ensino",
            "curso": "Nome do curso",
            "serie": "Série ou etapa",
            "inicio_mes": "Mês de início",
            "inicio_ano": "Ano de início",
            "fim_mes": "Mês de término",
            "fim_ano": "Ano de término",
            "instituicao": "Nome da instituição",
            "carga_horaria": "Carga horária"
        }
        
        # Cria o prompt estruturado
        prompt = f"""
        Analise cuidadosamente esta imagem de currículo e extraia TODAS as informações visíveis.
        
        INSTRUÇÕES IMPORTANTES:
        1. Leia todo o texto da imagem com atenção
        2. Procure por todas as informações solicitadas
        3. Retorne APENAS um JSON válido, sem texto adicional
        4. Use "Não informado" apenas se a informação realmente não estiver na imagem
        5. Mantenha os formatos solicitados para cada campo
        
        CAMPOS A EXTRAIR:
        {json.dumps(campos_json, indent=2, ensure_ascii=False)}
        
        FORMATO DE RESPOSTA:
        Retorne apenas o JSON com as informações extraídas, usando exatamente as chaves mostradas acima.
        """
        
        print("Enviando requisição para GPT-4 Vision...")
        
        # Faz a chamada para a API usando apenas a URL
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": imagem_url,
                                "detail": "high"  # Para análise mais detalhada
                            }
                        }
                    ]
                }
            ],
            max_tokens=4000,
            temperature=0
        )
        
        # Extrai o conteúdo da resposta
        resultado = response.choices[0].message.content
        print(f"Resposta bruta recebida: {resultado[:200]}...")
        
        # Tenta extrair o JSON da resposta
        try:
            # Remove possíveis marcadores de código
            resultado_limpo = resultado.replace('```json', '').replace('```', '').strip()
            
            # Se a resposta começar com '{', assume que é JSON
            if resultado_limpo.startswith('{'):
                dados_extraidos = json.loads(resultado_limpo)
            else:
                # Se não, procura por JSON na resposta
                import re
                json_match = re.search(r'\{.*\}', resultado_limpo, re.DOTALL)
                if json_match:
                    dados_extraidos = json.loads(json_match.group())
                else:
                    raise ValueError("Nenhum JSON encontrado na resposta")
            
            # Garante que todas as chaves estão presentes
            for chave in campos_json.keys():
                if chave not in dados_extraidos:
                    dados_extraidos[chave] = "Não informado"
            
            return dados_extraidos
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Erro ao decodificar JSON: {e}")
            print(f"Resposta completa recebida: {resultado}")
            return {"erro": "Resposta não está em formato JSON válido", "resposta_bruta": resultado}
            
    except Exception as e:
        print(f"Erro geral: {e}")
        return {"erro": f"Erro na análise: {str(e)}"}

def exibir_resultados(dados: Dict[str, Any]) -> None:
    """Exibe os resultados de forma organizada."""
    if "erro" in dados:
        print(f"❌ ERRO: {dados['erro']}")
        if "resposta_bruta" in dados:
            print(f"Resposta bruta: {dados['resposta_bruta']}")
        return
    
    print("✅ Análise concluída com sucesso!")
    print("\n=== DADOS EXTRAÍDOS DO CURRÍCULO ===\n")
    
    categorias = {
        "DADOS PESSOAIS": ["nome", "email", "cpf", "celular", "telefone", "idade", "pis", "rg", "ctps", "habilitacao", "estado_civil", "sexo"],
        "OBJETIVOS E RESUMO": ["objetivos_profissionais", "resumo_profissional", "pretensao_salarial"],
        "ENDEREÇO": ["uf", "cidade", "cep", "logradouro", "numero", "complemento"],
        "FORMAÇÃO": ["nivel_ensino", "situacao", "curso", "serie", "inicio_mes", "inicio_ano", "fim_mes", "fim_ano", "instituicao", "carga_horaria"]
    }
    
    for categoria, campos in categorias.items():
        print(f"=== {categoria} ===")
        for campo in campos:
            valor = dados.get(campo, "Não informado")
            print(f"{campo.upper().replace('_', ' ')}: {valor}")
        print()

# Exemplo de uso
if __name__ == "__main__":
    # URL de teste - substitua pela sua imagem
    imagem_teste = "https://drive.google.com/file/d/1DK_cgFiPc4BDsYV6vXiVY2QfPRtmEuKp/view?usp=sharing"
    
    print("Iniciando análise do currículo...")
    print(f"URL da imagem: {imagem_teste}")
    
    # Extrai os dados
    dados_completos = extrair_dados_curriculo(imagem_teste)
    
    # Exibe os resultados
    exibir_resultados(dados_completos)
    
    # Salva em JSON se não houver erro
    if "erro" not in dados_completos:
        with open('dados_curriculo.json', 'w', encoding='utf-8') as f:
            json.dump(dados_completos, f, ensure_ascii=False, indent=2)
        print("✅ Dados salvos em 'dados_curriculo.json'")