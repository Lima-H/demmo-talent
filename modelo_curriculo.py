import os 
from pathlib import Path
import json
import re
import requests
from typing import Dict, Any, List, Tuple
from openai import OpenAI
import streamlit as st



# Obtém a chave da OpenAI a partir do secrets.toml
api_key = st.secrets["OPENAI_API_KEY"]

# # Carrega as variáveis de ambiente
# from dotenv import load_dotenv 
# dotenv_path = Path(__file__).resolve().parent / '.env'
# load_dotenv(dotenv_path)
# api_key = os.getenv("OPENAI_API_KEY")

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

def extrair_dados_curriculo_single(imagem_url: str) -> Dict[str, Any]:
    """
    Extrai dados estruturados de um currículo em uma única imagem usando OpenAI Vision.
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
        
        # Estrutura de dados esperada com instruções específicas
        campos_json = {
            "nome": {
                "descricao": "Nome completo da pessoa",
                "instrucoes": "Extraia o nome completo. Se houver apenas nome ou sobrenome, use o que estiver disponível. Mantenha acentos e formatação original."
            },
            "email": {
                "descricao": "Email válido",
                "instrucoes": "Procure por endereços de e-mail no formato usuario@dominio.com. Se houver múltiplos e-mails, use o principal ou primeiro encontrado."
            },
            "cpf": {
                "descricao": "CPF no formato 123.456.789-00",
                "instrucoes": "Localize números de CPF. Formate com pontos e hífen (123.456.789-00). Se estiver sem formatação, aplique a formatação correta."
            },
            "celular": {
                "descricao": "Celular no formato (XX)XXXXX-XXXX",
                "instrucoes": "Identifique números de celular (9 dígitos). Formate como (XX)XXXXX-XXXX. Se não tiver DDD, use apenas o número disponível."
            },
            "telefone": {
                "descricao": "Telefone fixo no formato (XX)XXXX-XXXX",
                "instrucoes": "Procure telefones fixos (8 dígitos). Formate como (XX)XXXX-XXXX. Diferente de celular por não ter o 9 na frente."
            },
            "idade": {
                "descricao": "Idade em anos",
                "instrucoes": "Procure pela idade em anos. Se encontrar data de nascimento, calcule a idade aproximada. Use apenas números."
            },
            "pis": {
                "descricao": "Número do PIS/PASEP",
                "instrucoes": "Localize o número PIS ou PASEP. Mantenha apenas os números, sem formatação especial."
            },
            "rg": {
                "descricao": "Número do RG",
                "instrucoes": "Encontre o número do RG/Identidade. Mantenha o formato original encontrado no documento."
            },
            "ctps": {
                "descricao": "Número da Carteira de Trabalho",
                "instrucoes": "Procure pelo número da CTPS (Carteira de Trabalho). Pode aparecer como 'Carteira de Trabalho' ou 'CTPS'."
            },
            "habilitacao": {
                "descricao": "Categoria da habilitação (CNH)",
                "instrucoes": "Identifique a categoria da CNH (A, B, C, D, E, AB, AC, etc.). Se só mencionar 'habilitado', use essa informação."
            },
            "estado_civil": {
                "descricao": "Estado civil",
                "instrucoes": "Procure por estado civil: solteiro(a), casado(a), divorciado(a), viúvo(a), união estável, etc."
            },
            "sexo": {
                "descricao": "Sexo/Gênero",
                "instrucoes": "Identifique o sexo: Masculino, Feminino, ou como estiver descrito no documento."
            },
            "objetivos_profissionais": {
                "descricao": "Objetivos profissionais",
                "instrucoes": "Extraia o texto completo da seção de objetivos profissionais, metas de carreira, ou objetivos. Mantenha o texto original."
            },
            "resumo_profissional": {
                "descricao": "Resumo profissional ou perfil",
                "instrucoes": "Copie o texto do resumo profissional, perfil profissional, ou descrição das competências. Preserve o conteúdo completo."
            },
            "pretensao_salarial": {
                "descricao": "Pretensão salarial",
                "instrucoes": "Procure por valores de pretensão salarial. Mantenha o formato original (R$ 1.000,00, por exemplo)."
            },
            "uf": {
                "descricao": "Estado (sigla)",
                "instrucoes": "Identifique a sigla do estado (SP, RJ, MG, etc.). Use sempre a sigla de 2 letras em maiúsculo."
            },
            "cidade": {
                "descricao": "Cidade",
                "instrucoes": "Extraia o nome da cidade onde a pessoa reside. Mantenha a grafia original."
            },
            "cep": {
                "descricao": "CEP no formato XXXXX-XXX",
                "instrucoes": "Localize o CEP. Formate como XXXXX-XXX (5 dígitos, hífen, 3 dígitos). Se estiver sem hífen, adicione a formatação."
            },
            "logradouro": {
                "descricao": "Logradouro (rua, avenida, etc.)",
                "instrucoes": "Extraia o nome da rua, avenida, travessa, etc. Inclua o tipo (Rua, Av., etc.) se estiver presente."
            },
            "numero": {
                "descricao": "Número do endereço",
                "instrucoes": "Identifique o número da residência/endereço. Use apenas números ou 's/n' se for sem número."
            },
            "complemento": {
                "descricao": "Complemento do endereço",
                "instrucoes": "Procure por complementos como apartamento, bloco, casa, andar, etc. Mantenha abreviações originais."
            },
            "nivel_ensino": {
                "descricao": "Nível de ensino",
                "instrucoes": "Identifique o maior nível: Fundamental, Médio, Superior, Pós-graduação, Mestrado, Doutorado, etc."
            },
            "situacao": {
                "descricao": "Situação do ensino",
                "instrucoes": "Determine se está: Completo, Incompleto, Cursando, Em andamento, etc."
            },
            "curso": {
                "descricao": "Nome do curso",
                "instrucoes": "Extraia o nome completo do curso de graduação, técnico, ou principal formação mencionada."
            },
            "serie": {
                "descricao": "Série ou etapa",
                "instrucoes": "Se for ensino fundamental/médio, identifique a série. Para superior, pode ser o período/semestre."
            },
            "inicio_mes": {
                "descricao": "Mês de início dos estudos",
                "instrucoes": "Extraia o mês de início do curso principal. Use nome do mês ou número (01-12)."
            },
            "inicio_ano": {
                "descricao": "Ano de início dos estudos",
                "instrucoes": "Identifique o ano de início do curso. Use formato de 4 dígitos (ex: 2020)."
            },
            "fim_mes": {
                "descricao": "Mês de término dos estudos",
                "instrucoes": "Extraia o mês de conclusão ou previsão de conclusão. Use nome do mês ou número (01-12)."
            },
            "fim_ano": {
                "descricao": "Ano de término dos estudos",
                "instrucoes": "Identifique o ano de conclusão ou previsão. Use formato de 4 dígitos (ex: 2024)."
            },
            "instituicao": {
                "descricao": "Nome da instituição de ensino",
                "instrucoes": "Extraia o nome completo da escola, universidade, ou instituição de ensino principal."
            },
            "carga_horaria": {
                "descricao": "Carga horária do curso",
                "instrucoes": "Procure pela carga horária total do curso em horas. Mantenha apenas números seguidos de 'h' ou 'horas'."
            }
        }
        
        # Cria o prompt estruturado com instruções detalhadas
        campos_formatados = []
        for campo, info in campos_json.items():
            campos_formatados.append(f"""
    "{campo}": 
        - Descrição: {info['descricao']}
        - Instruções: {info['instrucoes']}""")
        
        prompt = f"""
        Analise cuidadosamente esta imagem de currículo e extraia TODAS as informações visíveis seguindo as instruções específicas para cada campo.
        
        REGRAS GERAIS:
        1. Leia todo o texto da imagem com máxima atenção
        2. Siga exatamente as instruções específicas de cada campo
        3. Retorne APENAS um JSON válido, sem texto adicional
        4. Use "Não informado" apenas se a informação realmente não estiver na imagem
        5. Mantenha formatos e acentuação original quando solicitado
        6. Se houver múltiplas informações do mesmo tipo, priorize a mais completa
        
        CAMPOS A EXTRAIR E SUAS INSTRUÇÕES ESPECÍFICAS:
        {''.join(campos_formatados)}
        
        FORMATO DE RESPOSTA:
        Retorne apenas um JSON com as chaves: {list(campos_json.keys())}
        
        Exemplo de estrutura esperada:
        {{
            "nome": "João Silva Santos",
            "email": "joao.silva@email.com",
            "cpf": "123.456.789-00",
            ...
        }}
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
        tokens_usados = response.usage.total_tokens
        
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
                json_match = re.search(r'\{.*\}', resultado_limpo, re.DOTALL)
                if json_match:
                    dados_extraidos = json.loads(json_match.group())
                else:
                    raise ValueError("Nenhum JSON encontrado na resposta")
            
            # Garante que todas as chaves estão presentes
            for chave in campos_json.keys():
                if chave not in dados_extraidos:
                    dados_extraidos[chave] = "Não informado"
            
            return dados_extraidos, tokens_usados
            
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Erro ao decodificar JSON: {e}")
            print(f"Resposta completa recebida: {resultado}")
            return {"erro": "Resposta não está em formato JSON válido", "resposta_bruta": resultado}, tokens_usados
            
    except Exception as e:
        print(f"Erro geral: {e}")
        return {"erro": f"Erro na análise: {str(e)}"}, 0

def combinar_dados_multiplas_paginas(lista_dados: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Combina dados extraídos de múltiplas páginas de currículo.
    Prioriza informações mais completas e não vazias.
    """
    dados_combinados = {}
    
    # Lista de todos os campos possíveis
    todos_campos = set()
    for dados in lista_dados:
        if "erro" not in dados:
            todos_campos.update(dados.keys())
    
    # Para cada campo, escolhe o valor mais completo
    for campo in todos_campos:
        valores_validos = []
        for dados in lista_dados:
            if "erro" not in dados and campo in dados:
                valor = dados[campo]
                if valor and valor != "Não informado" and valor.strip():
                    valores_validos.append(valor)
        
        # Escolhe o valor mais longo (presumivelmente mais completo)
        if valores_validos:
            dados_combinados[campo] = max(valores_validos, key=len)
        else:
            dados_combinados[campo] = "Não informado"
    
    return dados_combinados

def analisar_curriculo_por_links(links_publicos: List[str]) -> Tuple[Dict[str, Any], int, float]:
    """
    Analisa um currículo que pode ter múltiplas páginas através de links públicos.
    
    Args:
        links_publicos: Lista de URLs das imagens do currículo
    
    Returns:
        Tupla contendo: (dados_curriculo, total_tokens, preco_total)
    """
    
    if not links_publicos:
        return {"erro": "Nenhum link fornecido"}, 0, 0.0
    
    print(f"Iniciando análise de {len(links_publicos)} página(s) de currículo...")
    
    dados_por_pagina = []
    total_tokens = 0
    
    # Analisa cada página
    for i, link in enumerate(links_publicos):
        print(f"Analisando página {i+1}/{len(links_publicos)}: {link}")
        
        dados_pagina, tokens_pagina = extrair_dados_curriculo_single(link)
        dados_por_pagina.append(dados_pagina)
        total_tokens += tokens_pagina
        
        # Se houve erro crítico, retorna imediatamente
        if "erro" in dados_pagina and "API Key" in dados_pagina["erro"]:
            return dados_pagina, total_tokens, 0.0
    
    # Combina dados de todas as páginas
    if len(links_publicos) == 1:
        dados_finais = dados_por_pagina[0]
    else:
        print("Combinando dados de múltiplas páginas...")
        dados_finais = combinar_dados_multiplas_paginas(dados_por_pagina)
    
    # Calcula preço estimado (baseado nos preços do GPT-4 Vision)
    # Preços aproximados: input $0.01/1K tokens, output $0.03/1K tokens
    # Assumindo uma proporção média de input/output
    preco_total = (total_tokens / 1000) * 0.02  # Preço médio estimado
    
    print(f"Análise concluída. Tokens totais: {total_tokens}, Custo estimado: ${preco_total:.4f}")
    
    return dados_finais, total_tokens, preco_total

# Função para compatibilidade com o código anterior
def analisar_extrato_por_links(links_publicos: List[str]) -> Tuple[Dict[str, Any], int, float]:
    """
    Função de compatibilidade - redireciona para análise de currículo.
    """
    return analisar_curriculo_por_links(links_publicos)