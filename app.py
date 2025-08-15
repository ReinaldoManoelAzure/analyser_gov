# --- IMPORTAÇÕES E CONFIGURAÇÃO ---

import streamlit as st
from dotenv import load_dotenv
import os
import re
import pandas as pd
import io
import json
from fpdf import FPDF
from docx import Document
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

# Carregar variáveis de ambiente
env_path = ".env"
load_dotenv(env_path)
google_api_key = os.getenv("GOOGLE_API_KEY")

if not google_api_key:
    st.error("Chave de API do Google não encontrada. Certifique-se de definir GOOGLE_API_KEY no .env.")
    st.stop()

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash-latest",
    google_api_key=google_api_key,
    temperature=0.2
)


# --- CHAIN 1: EXTRAÇÃO DE DADOS ---
def get_data_extraction_chain():
    template = """
    Você é um especialista jurídico-financeiro que atua no apoio à administração pública para análise de projetos de lei que envolvem despesas com pessoal, conforme exige a Lei de Responsabilidade Fiscal (LRF).

    Sua tarefa é analisar o texto a seguir e extrair dados estruturados que permitam a elaboração de um estudo de impacto financeiro, considerando aspectos legais, operacionais e financeiros.

    Texto do projeto de lei:
    {text}

    Extraia as seguintes informações no formato JSON. Se algum item não for encontrado, use "Não especificado":

    ```json
    {{
      "tipo_proposta": "",
      "reajuste_proposto": "",
      "abrangencia_temporal": "",
      "setor_afetado": "",
      "detalhes_adicionais": "",
      "quantitativo_envolvido": "",
      "fonte_orcamentaria": "",
      "condicionantes_legais": "",
      "natureza_juridica_da_medida": ""
    }}
    ```
    """
    prompt = PromptTemplate(template=template, input_variables=["text"])
    return LLMChain(llm=llm, prompt=prompt)


# --- CHAIN 2: VALIDAÇÃO LEGAL ---
def get_legal_validation_chain():
    template = """
    Você é um consultor jurídico com foco na Lei de Responsabilidade Fiscal (LRF).

    Analise o seguinte projeto de lei e informe se ele cumpre as exigências legais para aumento de despesa com pessoal:

    Texto:
    {text}

    Responda em formato JSON:
    ```json
    {{
      "cumpre_lrf": "Sim" ou "Não",
      "justificativa": "Explicação concisa sobre o motivo."
    }}
    ```
    """
    prompt = PromptTemplate(template=template, input_variables=["text"])
    return LLMChain(llm=llm, prompt=prompt)


# --- CHAIN 3: AJUSTES SUGERIDOS ---
def get_adjustment_suggestion_chain():
    template = """
    Com base no seguinte texto de projeto de lei, sugira ajustes ou melhorias para garantir conformidade com a LRF e viabilidade financeira:

    Texto:
    {text}

    Responda em formato estruturado:
    ```json
    {{
      "ajustes_sugeridos": [
        "...",
        "..."
      ]
    }}
    ```
    """
    prompt = PromptTemplate(template=template, input_variables=["text"])
    return LLMChain(llm=llm, prompt=prompt)


# --- UTILITÁRIOS ---
def extract_percentage(text):
    match = re.search(r'(\d+(\.\d+)?)%', text)
    if match:
        return float(match.group(1))
    return None

def calculate_financial_impact(personnel_expenses, reajuste_percent):
    try:
        reajuste_decimal = reajuste_percent / 100
        impacto_mensal = personnel_expenses * reajuste_decimal
        impacto_anual = impacto_mensal * 12
        return impacto_mensal, impacto_anual
    except:
        return None, None

def parse_llm_response(response_text):
    """Função para extrair JSON da resposta do LLM"""
    try:
        # Remove markdown e espaços
        clean_text = response_text.strip()
        
        # Remove ```json e ``` se existirem
        if "```json" in clean_text:
            start = clean_text.find("```json") + 7
            end = clean_text.rfind("```")
            clean_text = clean_text[start:end]
        elif "```" in clean_text:
            start = clean_text.find("```") + 3
            end = clean_text.rfind("```")
            clean_text = clean_text[start:end]
        
        # Parse JSON
        return json.loads(clean_text.strip())
    except:
        # Se falhar, retorna um dicionário vazio
        return {}

def create_report_text(extracted_data, validacao, sugestoes, reajuste_percent, personnel_expenses, mensal_impact, anual_impact):
    ajustes_str = "\n- ".join(sugestoes.get("ajustes_sugeridos", [])) if sugestoes and sugestoes.get("ajustes_sugeridos") else "Nenhum ajuste sugerido."
    return f"""
Estudo de Impacto Financeiro - Proposta de Reajuste Salarial

1. Descrição da Proposta:
- Tipo: {extracted_data.get('tipo_proposta', 'Não especificado')}
- Setor Afetado: {extracted_data.get('setor_afetado', 'Não especificado')}
- Detalhes Adicionais: {extracted_data.get('detalhes_adicionais', 'Não especificado')}
- Percentual de Reajuste: {reajuste_percent:.2f}%
- Abrangência Temporal: {extracted_data.get('abrangencia_temporal', 'Não especificado')}
- Quantitativo Envolvido: {extracted_data.get('quantitativo_envolvido', 'Não especificado')}
- Fonte Orçamentária: {extracted_data.get('fonte_orcamentaria', 'Não especificado')}
- Condicionantes Legais: {extracted_data.get('condicionantes_legais', 'Não especificado')}
- Natureza Jurídica: {extracted_data.get('natureza_juridica_da_medida', 'Não especificado')}

2. Resultados do Cálculo:
- Gastos Atuais com Pessoal: R$ {personnel_expenses:,.2f}
- Impacto Mensal: R$ {mensal_impact:,.2f}
- Impacto Anual: R$ {anual_impact:,.2f}

3. Validação Jurídica:
- Cumpre LRF? {validacao.get('cumpre_lrf', 'N/A')}
- Justificativa: {validacao.get('justificativa', 'N/A')}

4. Ajustes Sugeridos:
- {ajustes_str}
    """

def create_pdf_report(texto):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    # Codificar o texto para latin-1
    texto_encoded = texto.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 10, txt=texto_encoded)
    pdf_output = io.BytesIO()
    pdf_output.write(pdf.output(dest='S').encode('latin1'))
    pdf_output.seek(0)
    return pdf_output.getvalue()

def create_word_report(texto):
    doc = Document()
    doc.add_heading('Estudo de Impacto Financeiro', 0)
    
    for linha in texto.strip().split('\n'):
        if linha.strip():
            doc.add_paragraph(linha.strip())
    
    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    return output.getvalue()

def display_results(dados, validacao, sugestoes, reajuste, gasto_atual, impacto_mensal, impacto_anual):
    """Função para exibir os resultados de forma amigável"""
    
    # Cabeçalho principal
    st.markdown("## 📊 Resultado do Estudo de Impacto Financeiro")
    st.markdown("---")
    
    # 1. Descrição da Proposta
    st.markdown("### 📝 Descrição da Proposta")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info(f"**Tipo:** {dados.get('tipo_proposta', 'Não especificado')}")
        st.info(f"**Setor Afetado:** {dados.get('setor_afetado', 'Não especificado')}")
        st.info(f"**Percentual de Reajuste:** {reajuste:.2f}%")
        st.info(f"**Abrangência Temporal:** {dados.get('abrangencia_temporal', 'Não especificado')}")
        st.info(f"**Quantitativo Envolvido:** {dados.get('quantitativo_envolvido', 'Não especificado')}")
    
    with col2:
        st.info(f"**Fonte Orçamentária:** {dados.get('fonte_orcamentaria', 'Não especificado')}")
        st.info(f"**Condicionantes Legais:** {dados.get('condicionantes_legais', 'Não especificado')}")
        st.info(f"**Natureza Jurídica:** {dados.get('natureza_juridica_da_medida', 'Não especificado')}")
    
    if dados.get('detalhes_adicionais') and dados.get('detalhes_adicionais') != 'Não especificado':
        st.markdown("**Detalhes Adicionais:**")
        st.write(dados.get('detalhes_adicionais'))
    
    st.markdown("---")
    
    # 2. Impacto Financeiro
    st.markdown("### 💰 Impacto Financeiro")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="💼 Gastos Atuais com Pessoal",
            value=f"R$ {gasto_atual:,.2f}"
        )
    
    with col2:
        st.metric(
            label="📅 Impacto Mensal",
            value=f"R$ {impacto_mensal:,.2f}",
            delta=f"{reajuste:.2f}%"
        )
    
    with col3:
        st.metric(
            label="📈 Impacto Anual",
            value=f"R$ {impacto_anual:,.2f}",
            delta=f"R$ {impacto_anual:,.2f}"
        )
    
    # Gráfico de pizza para visualização
    df_impacto = pd.DataFrame({
        'Categoria': ['Gasto Atual', 'Impacto do Reajuste'],
        'Valor': [gasto_atual, impacto_anual]
    })
    
    st.markdown("#### 📊 Visualização do Impacto")
    st.bar_chart(df_impacto.set_index('Categoria'))
    
    st.markdown("---")
    
    # 3. Validação Jurídica
    st.markdown("### ⚖️ Validação Jurídica")
    
    cumpre_lrf = validacao.get('cumpre_lrf', 'N/A')
    
    if cumpre_lrf.lower() == 'sim':
        st.success(f"✅ **Cumpre LRF:** {cumpre_lrf}")
    elif cumpre_lrf.lower() == 'não':
        st.error(f"❌ **Cumpre LRF:** {cumpre_lrf}")
    else:
        st.warning(f"⚠️ **Cumpre LRF:** {cumpre_lrf}")
    
    if validacao.get('justificativa'):
        st.markdown("**Justificativa:**")
        st.write(validacao.get('justificativa'))
    
    st.markdown("---")
    
    # 4. Sugestões de Ajustes
    st.markdown("### 💡 Sugestões de Ajustes")
    
    if sugestoes and sugestoes.get('ajustes_sugeridos'):
        for i, ajuste in enumerate(sugestoes.get('ajustes_sugeridos'), 1):
            st.markdown(f"**{i}.** {ajuste}")
    else:
        st.success("✅ Nenhum ajuste necessário identificado.")
    
    st.markdown("---")


# --- STREAMLIT ---
st.set_page_config(
    page_title="Estudo de Impacto Financeiro", 
    layout="wide",
    page_icon="📊"
)

# Header personalizado
st.markdown("""
<div style='text-align: center; padding: 20px;'>
    <h1 style='color: #2e7d32;'>📊 Sistema de Estudo de Impacto Financeiro</h1>
    <p style='font-size: 18px; color: #666;'>Análise automática de projetos de lei conforme a Lei de Responsabilidade Fiscal (LRF)</p>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# Sidebar com informações
with st.sidebar:
    st.markdown("## ℹ️ Sobre o Sistema")
    st.markdown("""
    Este sistema realiza:
    - ✅ Extração automática de dados
    - ⚖️ Validação jurídica (LRF)
    - 📊 Cálculo de impacto financeiro
    - 💡 Sugestões de ajustes
    - 📄 Geração de relatórios
    """)
    
    st.markdown("## 📋 Como usar")
    st.markdown("""
    1. Cole o texto do projeto de lei
    2. Informe o gasto atual com pessoal
    3. Clique em "Analisar"
    4. Baixe os relatórios se necessário
    """)

# Input principal
st.markdown("## 📝 Entrada de Dados")

texto = st.text_area(
    "Cole aqui o texto do projeto de lei:", 
    height=200,
    help="Cole o texto completo do projeto de lei que você deseja analisar"
)

# Configurações adicionais
with st.expander("⚙️ Configurações Avançadas"):
    gasto_atual = st.number_input(
        "Gasto Atual com Pessoal (R$):", 
        value=10000000.0, 
        step=10000.0,
        help="Informe o valor atual gasto com pessoal para cálculo do impacto"
    )

# Botão de análise
if st.button("🔍 Analisar e Gerar Estudo", type="primary"):
    if texto:
        with st.spinner("🔄 Executando análise completa..."):
            try:
                # Executar as chains
                progress_bar = st.progress(0)
                
                # Chain 1 - Extração de dados
                st.write("📝 Extraindo dados do projeto...")
                progress_bar.progress(25)
                dados_response = get_data_extraction_chain().run(text=texto)
                dados = parse_llm_response(dados_response)
                
                # Chain 2 - Validação legal
                st.write("⚖️ Realizando validação jurídica...")
                progress_bar.progress(50)
                validacao_response = get_legal_validation_chain().run(text=texto)
                validacao = parse_llm_response(validacao_response)
                
                # Chain 3 - Sugestões
                st.write("💡 Gerando sugestões de ajustes...")
                progress_bar.progress(75)
                sugestoes_response = get_adjustment_suggestion_chain().run(text=texto)
                sugestoes = parse_llm_response(sugestoes_response)
                
                # Cálculos
                st.write("📊 Calculando impacto financeiro...")
                progress_bar.progress(100)
                
                reajuste = extract_percentage(dados.get("reajuste_proposto", "0%")) or 5.0
                impacto_mensal, impacto_anual = calculate_financial_impact(gasto_atual, reajuste)
                
                # Exibir resultados
                display_results(dados, validacao, sugestoes, reajuste, gasto_atual, impacto_mensal, impacto_anual)
                
                # Botões de download
                st.markdown("## 📥 Downloads")
                
                texto_relatorio = create_report_text(
                    dados, validacao, sugestoes, reajuste, 
                    gasto_atual, impacto_mensal, impacto_anual
                )
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.download_button(
                        label="📄 Baixar PDF",
                        data=create_pdf_report(texto_relatorio),
                        file_name="relatorio_impacto.pdf",
                        mime="application/pdf"
                    )
                
                with col2:
                    st.download_button(
                        label="📝 Baixar Word",
                        data=create_word_report(texto_relatorio),
                        file_name="relatorio_impacto.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                
                with col3:
                    st.download_button(
                        label="📊 Baixar Dados (JSON)",
                        data=json.dumps({
                            "dados": dados,
                            "validacao": validacao,
                            "sugestoes": sugestoes,
                            "impacto_financeiro": {
                                "reajuste_percent": reajuste,
                                "gasto_atual": gasto_atual,
                                "impacto_mensal": impacto_mensal,
                                "impacto_anual": impacto_anual
                            }
                        }, indent=2, ensure_ascii=False),
                        file_name="dados_analise.json",
                        mime="application/json"
                    )
                
            except Exception as e:
                st.error(f"❌ Erro durante a análise: {str(e)}")
                st.error("Verifique se a API do Google está funcionando corretamente.")
    else:
        st.warning("⚠️ Por favor, cole o texto do projeto de lei antes de iniciar a análise.")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <small>Sistema de Análise de Impacto Financeiro | Desenvolvido para auxiliar na análise de projetos de lei conforme a LRF</small>
</div>
""", unsafe_allow_html=True)