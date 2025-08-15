import streamlit as st
from dotenv import load_dotenv
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import re
import pandas as pd
import io
from fpdf import FPDF
from docx import Document

# Carregar variáveis de ambiente
load_dotenv()
google_api_key = os.getenv("GOOGLE_API_KEY")

# Verificar se a chave de API está disponível
if not google_api_key:
    st.error("Chave de API do Google não encontrada. Certifique-se de que a variável de ambiente GOOGLE_API_KEY está definida no arquivo .env.")
    st.stop()

# Configurar o modelo Gemini-Flash
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", google_api_key=google_api_key, temperature=0.2)

# ----- Funções LangChain (mesmas do código anterior) -----

def get_data_extraction_chain():
    """Cria uma cadeia LangChain para extrair dados de um texto."""
    template = """
    Você é um assistente especializado em análise de projetos de lei e estudos de impacto financeiro.
    Sua tarefa é extrair informações chave de um texto fornecido, especificamente para calcular o impacto financeiro de um projeto de lei que envolve despesas com pessoal.

    Texto do projeto de lei:
    {text}

    Extraia as seguintes informações em formato JSON:
    - reajuste_proposto: O percentual de reajuste salarial (ex: "5%"). Se não for explícito, use "Não especificado".
    - tipo_proposta: Uma breve descrição da proposta (ex: "Reajuste salarial dos servidores", "Criação de novos cargos").
    - detalhes_adicionais: Qualquer outra informação relevante para o cálculo do impacto (ex: "apenas para servidores ativos", "reajuste escalonado").
    - setor_afetado: O setor ou grupo de servidores afetado (ex: "servidores municipais", "professores da rede municipal").

    Formato da resposta JSON:
    ```json
    {{
      "reajuste_proposto": "",
      "tipo_proposta": "",
      "detalhes_adicionais": "",
      "setor_afetado": ""
    }}
    ```
    """
    prompt = PromptTemplate(template=template, input_variables=["text"])
    chain = LLMChain(llm=llm, prompt=prompt)
    return chain

def calculate_financial_impact(personnel_expenses, reajuste_percent):
    """Calcula o impacto financeiro anual com base nas despesas e no percentual de reajuste."""
    try:
        reajuste_decimal = reajuste_percent / 100
        impacto_mensal = personnel_expenses * reajuste_decimal
        impacto_anual = impacto_mensal * 12
        return impacto_mensal, impacto_anual
    except (TypeError, ValueError):
        return None, None

def extract_percentage(text):
    """Extrai um percentual de uma string."""
    match = re.search(r'(\d+(\.\d+)?)%', text)
    if match:
        return float(match.group(1))
    return None

# ----- Funções para Geração de Documentos -----

def create_report_text(extracted_data, reajuste_percent, personnel_expenses, mensal_impact, anual_impact):
    """Cria a string do relatório para ser usada em diferentes formatos."""
    report_text = f"""
    Estudo de Impacto Financeiro - Proposta de Reajuste Salarial

    1. Descrição da Proposta:
    - Tipo: {extracted_data.get('tipo_proposta', 'N/A')}
    - Setor Afetado: {extracted_data.get('setor_afetado', 'N/A')}
    - Detalhes Adicionais: {extracted_data.get('detalhes_adicionais', 'N/A')}
    - Percentual de Reajuste: {reajuste_percent:.2f}%

    2. Dados para o Cálculo:
    - Gastos Atuais com Pessoal (Mensal): R$ {personnel_expenses:,.2f}

    3. Resultados do Cálculo:
    - Impacto Financeiro Mensal: R$ {mensal_impact:,.2f}
    - Impacto Financeiro Anual: R$ {anual_impact:,.2f}

    Observação: Este estudo foi elaborado com base nos dados e estimativas fornecidos e deve ser complementado com outras informações relevantes para a tomada de decisão.
    """
    return report_text

def create_pdf_report(report_text):
    """Gera um relatório em PDF em memória."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, txt=report_text)
    
    # Salvar o PDF em um buffer de memória
    pdf_output = io.BytesIO(pdf.output(dest='S').encode('latin1'))
    return pdf_output.getvalue()

def create_word_report(report_text):
    """Gera um relatório em Word em memória."""
    document = Document()
    for paragraph in report_text.strip().split('\n'):
        if paragraph.strip():
            document.add_paragraph(paragraph.strip())
    
    # Salvar o documento em um buffer de memória
    doc_output = io.BytesIO()
    document.save(doc_output)
    return doc_output.getvalue()

# ----- Interface do Streamlit -----

st.set_page_config(page_title="Gerador de Estudo de Impacto Financeiro", layout="wide")
st.image("logo_app.png", width=100)
st.title("Sistema de Estudo de Impacto Financeiro")
st.markdown("### Objetivo do Sistema")
st.write("Criar uma ferramenta que auxilie a administração pública na elaboração de estudos de impacto financeiro exigidos pela Lei de Responsabilidade Fiscal.")

st.markdown("---")

st.markdown("### 1. Leitura e Interpretação Automática de Textos Legais")
with st.container():
    project_text = st.text_area(
        "Cole o texto do projeto de lei aqui:",
        height=250,
        placeholder="Ex: 'O reajuste de 5% nos vencimentos dos servidores públicos municipais será concedido a partir de 1º de janeiro de 2026.'"
    )
    
    if st.button("Analisar Texto"):
        if project_text:
            with st.spinner("Analisando o texto..."):
                try:
                    extraction_chain = get_data_extraction_chain()
                    result = extraction_chain.run(text=project_text)
                    
                    try:
                        extracted_data = eval(result.strip("`json\n`"))
                    except:
                        st.warning("Não foi possível extrair os dados em formato JSON. Exibindo o texto bruto.")
                        extracted_data = {"reajuste_proposto": result, "tipo_proposta": "Não especificado", "detalhes_adicionais": "Não especificado", "setor_afetado": "Não especificado"}
                    
                    st.session_state['extracted_data'] = extracted_data
                    
                except Exception as e:
                    st.error(f"Ocorreu um erro na análise: {e}")
        else:
            st.warning("Por favor, cole um texto para análise.")

if 'extracted_data' in st.session_state:
    st.markdown("### 2. Dados Relevantes Extraídos")
    col1, col2 = st.columns(2)
    with col1:
        st.info("Reajuste Proposto: " + st.session_state['extracted_data'].get('reajuste_proposto', 'N/A'))
        st.info("Tipo de Proposta: " + st.session_state['extracted_data'].get('tipo_proposta', 'N/A'))
    with col2:
        st.info("Setor Afetado: " + st.session_state['extracted_data'].get('setor_afetado', 'N/A'))
        st.info("Detalhes Adicionais: " + st.session_state['extracted_data'].get('detalhes_adicionais', 'N/A'))

    st.markdown("---")

    st.markdown("### 3. Cálculo do Impacto Financeiro")
    st.write("Preencha os dados abaixo para calcular o impacto financeiro.")

    reajuste_extracted_percent = extract_percentage(st.session_state['extracted_data'].get('reajuste_proposto', '0%'))
    
    col3, col4 = st.columns(2)
    with col3:
        personnel_expenses = st.number_input(
            "Gastos Atuais com Pessoal (R$ - valor mensal):", 
            min_value=0.0, 
            value=10000000.0, 
            step=10000.0,
            help="Despesa mensal total com pessoal, incluindo salários, encargos, etc."
        )
    with col4:
        reajuste_manual_percent = st.number_input(
            "Percentual de Reajuste Proposto (%):", 
            min_value=0.0, 
            max_value=100.0, 
            value=reajuste_extracted_percent or 5.0,
            step=0.1
        )
    
    st.markdown("---")
    st.markdown("### 5. Geração de Relatório")
    if st.button("Calcular Impacto e Gerar Relatórios"):
        if personnel_expenses > 0 and reajuste_manual_percent is not None:
            mensal_impact, anual_impact = calculate_financial_impact(personnel_expenses, reajuste_manual_percent)
            
            if mensal_impact is not None:
                st.markdown("#### Resultado do Estudo de Impacto Financeiro")
                st.success("Cálculo realizado com sucesso!")

                report_data = {
                    "Item": ["Percentual de Reajuste", "Gastos Atuais com Pessoal (Mensal)", "Impacto Financeiro Mensal", "Impacto Financeiro Anual"],
                    "Valor": [
                        f"{reajuste_manual_percent:.2f}%",
                        f"R$ {personnel_expenses:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                        f"R$ {mensal_impact:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                        f"R$ {anual_impact:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    ]
                }
                
                df_report = pd.DataFrame(report_data)
                st.table(df_report.set_index('Item'))
                
                # Gerar texto do relatório
                report_text = create_report_text(
                    st.session_state['extracted_data'],
                    reajuste_manual_percent,
                    personnel_expenses,
                    mensal_impact,
                    anual_impact
                )

                st.markdown("---")
                col_pdf, col_word = st.columns(2)

                # Botão de download PDF
                with col_pdf:
                    pdf_bytes = create_pdf_report(report_text)
                    st.download_button(
                        label="⬇️ Baixar Relatório em PDF",
                        data=pdf_bytes,
                        file_name="Estudo_Impacto_Financeiro.pdf",
                        mime="application/pdf"
                    )
                
                # Botão de download DOCX
                with col_word:
                    word_bytes = create_word_report(report_text)
                    st.download_button(
                        label="⬇️ Baixar Relatório em Word",
                        data=word_bytes,
                        file_name="Estudo_Impacto_Financeiro.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )

            else:
                st.error("Erro no cálculo. Verifique os valores inseridos.")

# Rodar a aplicação
if __name__ == '__main__':
    st.markdown("---")
    st.markdown("#### Funções-Chave Esperadas")
    st.markdown("1. Leitura e interpretação automática de textos legais")
    st.markdown("2. Extração de dados relevantes")
    st.markdown("3. Cálculo do impacto financeiro")
    st.markdown("4. Flexibilidade para casos simples e complexos")
    st.markdown("5. Geração de relatório pronto para envio")