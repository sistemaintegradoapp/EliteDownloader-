import os
os.system('apt-get update && apt-get install -y ffmpeg')
import shutil
import time
import queue
from typing import List, Dict, Tuple
import requests
import streamlit as st
from http import cookies
from urllib.parse import urlparse, urlunparse
from concurrent.futures import ThreadPoolExecutor
import json
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import uuid
import mercadopago
import hashlib
import platform
import feedparser
from urllib.parse import quote
import tempfile
import re
import socket
import ipaddress
from pydub import AudioSegment
import subprocess
from bs4 import BeautifulSoup

# ============================================================
# CONFIGURAÇÕES GLOBAIS
# ============================================================
st.set_page_config(
    page_title="Sistema de Conteúdo Premium",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# OCULTAR ELEMENTOS DO STREAMLIT (APENAS ISSO)
# ============================================================
hide_streamlit_style = """
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:visible;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True) 

hide_deploy_css = """
<style>
.free-downloads-counter {
background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%) !important;
color: white !important;
padding: 15px !important;
border-radius: 10px !important;
text-align: center !important;
margin: 10px 0 !important;
border: 2px solid #2E7D32 !important;
}
</style>
"""
st.markdown(hide_deploy_css, unsafe_allow_html=True)

# ============================================================
# PREÇOS E LIMITES (CONFIGURÁVEIS)
# ============================================================
PLANO_MENSAL_PRECO = 9.90
PLANO_VITALICIO_PRECO = 297.00
TEST_DRIVE_PRECO = 2.00
DOWNLOAD_GRATIS_LIMITE = 10

# ============================================================
# IMPORTAÇÕES E CONFIGURAÇÕES
# ============================================================
TKINTER_AVAILABLE = False

try:
    import yt_dlp
    YTDLP_OK = True
except Exception:
    YTDLP_OK = False

try:
    import feedparser
    FEEDPARSER_OK = True
except Exception:
    FEEDPARSER_OK = False

# ============================================================
# SISTEMA DE PROGRESSO DE DOWNLOAD EM TEMPO REAL (SEM TRANSCRIÇÃO)
# ============================================================
class DownloadProgressHook:
    def __init__(self):
        self.progress_bar = None
        self.status_text = None
        self.current_percent = 0
        
    def hook(self, d):
        if d['status'] == 'downloading':
            # Extrair porcentagem do progresso
            if '_percent_str' in d:
                percent_str = d['_percent_str'].strip()
                if percent_str.endswith('%'):
                    try:
                        self.current_percent = float(percent_str.replace('%', ''))
                        if self.progress_bar:
                            self.progress_bar.progress(self.current_percent / 100)
                        if self.status_text:
                            self.status_text.text(f"📥 Baixando: {self.current_percent:.1f}%")
                    except:
                        pass
            
        elif d['status'] == 'finished':
            if self.progress_bar:
                self.progress_bar.progress(1.0)
            if self.status_text:
                self.status_text.text("✅ Download concluído!")    
    
# ============================================================
# FUNÇÃO PARA SELEÇÃO DE PASTA - SIMPLIFICADA
# ============================================================
def select_download_folder():
    """Seletor de pasta simplificado que sempre aparece"""
    st.write("**Selecione onde salvar seus downloads:**")
    
    # Opções comuns de pastas
    common_folders = [
        os.path.join(os.path.expanduser("~"), "Downloads"),
        os.path.join(os.path.expanduser("~"), "Desktop"),
        os.path.join(os.path.expanduser("~"), "Documents"),
        os.path.join(os.path.expanduser("~"), "Videos")
    ]
    
    selected = st.selectbox(
        "Pasta padrão:",
        options=common_folders,
        format_func=lambda x: x.replace(os.path.expanduser("~"), "~"),
        key="folder_selector"
    )
    
    # Atualizar sempre que mudar a seleção
    if selected != st.session_state.get('download_path'):
        st.session_state.download_path = selected
        st.success(f"✅ Pasta definida: {selected}")
    
    # Opção personalizada
    st.write("**Ou digite um caminho personalizado:**")
    custom_path = st.text_input("Caminho completo:", 
                               value=st.session_state.download_path, 
                               key="custom_path_input")
    
    if custom_path and custom_path != st.session_state.download_path:
        try:
            if not os.path.exists(custom_path):
                os.makedirs(custom_path)
                st.success(f"📁 Pasta criada: {custom_path}")
            
            st.session_state.download_path = custom_path
            st.success(f"✅ Pasta definida: {custom_path}")
        except Exception as e:
            st.error(f"❌ Erro ao acessar pasta: {e}")

# ============================================================
# Configuração Mercado Pago
# ============================================================
PUBLIC_KEY = "APP_USR-488e77a6-23aa-4cde-98da-3c80a9b582af"
ACCESS_TOKEN = "APP_USR-1239668553931980-082711-99182945035c9d5379043ce84a4e61be-68167871"
mp = mercadopago.SDK(ACCESS_TOKEN)

# ============================================================
# Configuração Zoho Mail
# ============================================================
ZOHO_CONFIG = {
    "SMTP_HOST": "smtp.zoho.com",
    "SMTP_PORT": 587,
    "SMTP_USER": "sistema.integrado.app@zohomail.com",
    "SMTP_PASS": "6Brm0H1Qyy1b",
    "SMTP_FROM": "sistema.integrado.app@zohomail.com"
}

# ============================================================
# UTILS E FUNÇÕES AUXILIARES
# ============================================================
def clean_url(url: str) -> str:
    parsed_url = urlparse(url)
    return urlunparse(parsed_url._replace(query="", fragment=""))

def is_valid_email(email: str) -> bool:
    pattern = r'^[a-zA-Z00-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def get_device_id():
    try:
        system_info = f"{platform.node()}{socket.gethostname()}{uuid.getnode()}"
        return hashlib.md5(system_info.encode()).hexdigest()[:12]
    except:
        return str(uuid.uuid4())[:12]

def get_client_ip():
    try:
        return st.experimental_get_forwarding_url()
    except:
        return "unknown"

def detect_platform(url: str) -> str:
    url_lower = url.lower()
    platforms = {
        'youtube.com': 'YouTube', 'youtu.be': 'YouTube',
        'instagram.com': 'Instagram', 'tiktok.com': 'TikTok',
        'twitter.com': 'Twitter/X', 'x.com': 'Twitter/X',
        'facebook.com': 'Facebook', 'fb.com': 'Facebook',
        'twitch.tv': 'Twitch', 'vimeo.com': 'Vimeo',
        'dailymotion.com': 'Dailymotion', 'reddit.com': 'Reddit',
        'pinterest.com': 'Pinterest', 'linkedin.com': 'LinkedIn'
    }
    for domain, name in platforms.items():
        if domain in url_lower:
            return name
    return "Outra plataforma"

# ============================================================
# SISTEMA DE DOWNLOADS GRATUITOS - DEFINIR PRIMEIRO
# ============================================================
def init_free_downloads():
    if 'free_downloads' not in st.session_state:
        st.session_state.free_downloads = DOWNLOAD_GRATIS_LIMITE
    if 'used_free_downloads' not in st.session_state:
        st.session_state.used_free_downloads = 0
    if 'free_downloads_history' not in st.session_state:
        st.session_state.free_downloads_history = []

def can_use_free_download():
    init_free_downloads()
    return st.session_state.free_downloads > 0

def use_free_download(url: str = None):
    init_free_downloads()
    if st.session_state.free_downloads > 0:
        st.session_state.free_downloads -= 1
        st.session_state.used_free_downloads += 1
        
        if url:
            st.session_state.free_downloads_history.append({
                'url': url,
                'timestamp': datetime.now().isoformat(),
                'remaining': st.session_state.free_downloads
            })
        return True
    return False

def get_free_downloads_count():
    init_free_downloads()
    return st.session_state.free_downloads

# ============================================================
# SISTEMA DE DOWNLOADS GRATUITOS UI - CORRIGIDO
# ============================================================
def show_free_downloads_ui():
    st.markdown("---")
    st.subheader("🎁 Downloads Gratuitos")
    
    init_free_downloads()
    
    # MOSTRAR O CONTADOR CORRETAMENTE
    remaining = st.session_state.free_downloads
    st.markdown(f"""
    <div class="free-downloads-counter">
        <h3>📊 Downloads Disponíveis</h3>
        <h1>{remaining}/{DOWNLOAD_GRATIS_LIMITE}</h1>
        <p>Você ainda tem {remaining} downloads gratuitos!</p>
    </div>
    """, unsafe_allow_html=True)
    
    # PRIMEIRO: SELECIONAR A PASTA DE DESTINO (SEMPRE MOSTRAR)
    st.write("### 📁 Escolha onde salvar seus arquivos:")
    
    if 'download_path' not in st.session_state:
        st.session_state.download_path = os.path.join(os.path.expanduser("~"), "Downloads")
    
    # SEMPRE mostrar o seletor de pasta
    select_download_folder()
    
    st.write("### ⬇️ Agora faça seu download gratuito")
    
    free_url = st.text_input("Cole o link do vídeo:", key="free_url", 
                           placeholder="https://www.youtube.com/watch?v=...")
    
    col1, col2 = st.columns(2)
    with col1:
        free_fmt = st.selectbox("Formato:", ["mp4", "audio (mp3)"], key="free_fmt")
    with col2:
        free_quality = st.selectbox("Qualidade:", ["best", "720p", "480p", "360p"], key="free_quality")
    
    if st.button("🚀 Download Gratuito", key="btn_free_download", type="secondary"):
        if not free_url.strip():
            st.error("Por favor, cole um link válido.")
            return
            
        if not can_use_free_download():
            st.error("❌ Você já usou todos os seus downloads gratuitos!")
            st.info("💡 Assine um plano premium para downloads ilimitados!")
            return
        
        # VERIFICAR SE A PASTA EXISTE
        if not os.path.exists(st.session_state.download_path):
            st.error("❌ A pasta de destino não existe! Por favor, selecione uma pasta válida.")
            return
            
        # USAR O DOWNLOAD GRATUITO ANTES DE BAIXAR
        # Área dedicada para o progresso do download
            download_container = st.container()
            
            with download_container:
                st.info("🔄 Iniciando download...")
                
                # Esta função agora mostrará a barra de progresso automaticamente
                success, message, logs = run_ytdlp(
                    free_url, 
                    st.session_state.download_path, 
                    free_fmt, 
                    free_quality
                )
                
                if success:
                    # ATUALIZAR O CONTADOR NA MENSAGEM
                    remaining_after = st.session_state.free_downloads
                    st.success(f"✅ Download concluído! Restam {remaining_after} downloads gratuitos.")
                    st.info(f"📁 Salvo em: {st.session_state.download_path}")
                    
                    # REMOVER o botão "Abrir pasta" que não funciona
                    # Em vez disso, mostrar instruções claras
                    st.markdown("""
                    **📋 Como acessar seus arquivos:**
                    - Se você está usando o sistema localmente, os arquivos estão na pasta selecionada acima
                    - Se você está acessando via web, entre em contato com o suporte para receber seus arquivos
                    - Arquivo salvo: `{}`
                    """.format(os.path.basename(message.split(": ")[1] if ": " in message else "arquivo")))
                    
                    # Forçar atualização da interface
                    st.rerun()
                else:
                    st.error(f"❌ Erro no download: {message}")
                    # Se falhou, devolvemos o download gratuito
                    st.session_state.free_downloads += 1
                    st.session_state.used_free_downloads -= 1
                    st.rerun()
                    
# ============================================================
# SISTEMA DE CHAVES E PAGAMENTOS - CORRIGIDO
# ============================================================
def save_user_key(email: str, key_data: dict):
    """Salva ou atualiza chave do usuário"""
    try:
        keys_file = 'user_keys.json'
        # Carregar chaves existentes
        if os.path.exists(keys_file):
            with open(keys_file, 'r', encoding='utf-8') as f:
                try:
                    keys = json.load(f)
                except:
                    keys = {}
        else:
            keys = {}
        
        # Atualizar chave do usuário
        keys[email] = key_data
        
        # Salvar arquivo
        with open(keys_file, 'w', encoding='utf-8') as f:
            json.dump(keys, f, indent=4, ensure_ascii=False)
        
        return True
    except Exception as e:
        st.error(f"Erro ao salvar chave: {e}")
        return False
        
def load_user_key(email: str):
    keys_file = 'user_keys.json'
    if os.path.exists(keys_file):
        with open(keys_file, 'r', encoding='utf-8') as f:
            try:
                keys = json.load(f)
                return keys.get(email, None)
            except Exception as e:
                st.error(f"Erro ao carregar arquivo de chaves: {e}")
                return None
    return None

def check_key_status(email: str):
    key_data = load_user_key(email)
    if not key_data:
        return "Não encontrada", None
    
    if key_data.get("status") != "active":
        return "Inativa", key_data
    
    expiry_date = key_data.get("expiry_date")
    if expiry_date:
        expiry = datetime.fromisoformat(expiry_date)
        if expiry < datetime.now():
            return "Expirada", key_data
        return f"Ativa (expira em {expiry.strftime('%d/%m/%Y')})", key_data
    
    return "Vitalícia", key_data

def renew_key(email: str):
    key_data = load_user_key(email)
    if not key_data:
        return False, "Chave não encontrada"
    
    if key_data.get("plan") == "lifetime":
        return False, "Plano vitalício não precisa de renovação"
    
    new_expiry = (datetime.now() + timedelta(days=30)).isoformat()
    key_data["expiry_date"] = new_expiry
    key_data["renewed_date"] = datetime.now().isoformat()
    
    save_user_key(email, key_data)
    return True, f"Chave renovada com sucesso! Nova validade: {new_expiry}"

def generate_user_key(email: str, plan_type: str) -> dict:
    """Gera uma chave de usuário com base no plano selecionado"""
    user_key = str(uuid.uuid4()).replace('-', '')[:16]
    
    if plan_type == "Mensal":
        expiry_date = (datetime.now() + timedelta(days=30)).isoformat()
    elif plan_type == "TestDrive":
        expiry_date = (datetime.now() + timedelta(hours=24)).isoformat()
    else:  # Vitalício
        expiry_date = None
    
    key_data = {
        "key": user_key,
        "email": email,
        "plan": plan_type.lower(),
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "expiry_date": expiry_date,
        "device_id": get_device_id()
    }
    
    return key_data

def send_key_via_email(email: str, key: str, plan_type: str):
    """Tenta enviar por email, se falhar mostra na tela"""
    try:
        # Configuração do e-mail
        smtp_server = ZOHO_CONFIG["SMTP_HOST"]
        smtp_port = ZOHO_CONFIG["SMTP_PORT"]
        smtp_user = ZOHO_CONFIG["SMTP_USER"]
        smtp_pass = ZOHO_CONFIG["SMTP_PASS"]
        smtp_from = ZOHO_CONFIG["SMTP_FROM"]

        # Criação do corpo do e-mail
        subject = f"Sua Chave de Acesso Premium - Plano {plan_type}"
        
        if plan_type == "Mensal":
            validity = "30 dias"
        elif plan_type == "TestDrive":
            validity = "24 horas"
        else:
            validity = "Vitalício"
            
        body = f"""
        Olá,
        
        Sua chave de acesso ao sistema premium é: {key}
        
        Plano: {plan_type}
        Validade: {validity}
        
        Acesse o sistema e use esta chave para fazer login e aproveitar todos os recursos exclusivos!
        
        Atenciosamente,
        Equipe Sistema Premium
        """
        
        # Preparar e-mail
        msg = MIMEMultipart()
        msg['From'] = smtp_from
        msg['To'] = email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Enviar e-mail
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            text = msg.as_string()
            server.sendmail(smtp_from, email, text)

        st.success(f"✅ Chave enviada para: {email}")
        return True
        
    except Exception as e:
        # Se falhar o email, mostrar a chave na tela
        st.warning(f"⚠️ Não foi possível enviar email: {e}")
        st.info("📋 Sua chave de acesso foi gerada com sucesso!")
        
        if plan_type == "Mensal":
            validity = "30 dias"
        elif plan_type == "TestDrive":
            validity = "24 horas"
        else:
            validity = "Vitalício"
            
        st.markdown(f"""
        **📧 Email:** {email}  
        **🔑 Chave de Acesso:** `{key}`  
        **📦 Plano:** {plan_type}  
        **⏰ Validade:** {validity}
        
        **💡 Guarde esta chave com segurança!**
        """)
        
        # Botão para copiar a chave
        if st.button("📋 Copiar Chave para Área de Transferência"):
            import pyperclip
            try:
                pyperclip.copy(key)
                st.success("✅ Chave copiada!")
            except:
                st.warning("⚠️ Não foi possível copiar automaticamente. Copie manualmente acima.")
        
        return False  # Retorna False mas mostra a chave na tela
        
def test_mp_connection():
    """Testa a conexão com a API do Mercado Pago"""
    try:
        # Teste mais simples - criar uma preferência de teste
        test_data = {
            "items": [{
                "title": "Teste de Conexão",
                "quantity": 1,
                "unit_price": 1.00,
                "currency_id": "BRL",
            }],
            "auto_return": "approved",
        }
        
        result = mp.preference().create(test_data)
        if 'response' in result:
            st.success("✅ Conexão com Mercado Pago OK!")
            return True
        else:
            st.error("❌ Resposta inesperada do Mercado Pago")
            st.write("Resposta completa:", result)
            return False
            
    except Exception as e:
        st.error(f"❌ Falha na conexão com Mercado Pago: {str(e)}")
        
        # Verificar se é erro de autenticação
        if "401" in str(e) or "authentication" in str(e).lower():
            st.error("🔑 Token de acesso inválido ou expirado!")
            st.info("💡 Verifique se o ACCESS_TOKEN está correto no código")
        elif "404" in str(e):
            st.error("🌐 Endpoint não encontrado - verifique a configuração da API")
        else:
            # Mostrar detalhes completos do erro para debug
            import traceback
            st.error("Detalhes completos do erro:")
            st.code(traceback.format_exc())
        
        return False
        
# ============================================================
# SISTEMA DE VERIFICAÇÃO DE PAGAMENTO (ATUALIZADO)
# ============================================================
def check_payment_status():
    """Verifica se há parâmetros de status de pagamento na URL"""
    params = st.query_params
    payment_status = params.get("payment_status", [None])[0]
    payment_id = params.get("payment_id", [None])[0]
    
    if payment_status and payment_id:
        if payment_status == "success":
            st.success("✅ Pagamento aprovado! Gerando sua chave de acesso...")
            # Buscar informações do pagamento pendente
            payment_info = st.session_state.pending_payments.get(payment_id)
            if payment_info:
                email = payment_info["email"]
                plan = payment_info["plan"]
                
                # Gerar e salvar a chave
                key_data = generate_user_key(email, plan)
                if save_user_key(email, key_data):
                    # Enviar email com a chave
                    if send_key_via_email(email, key_data["key"], plan):
                        st.success(f"🎉 Chave enviada para: {email}")
                        st.info(f"Sua chave de acesso: {key_data['key']}")
                        
                        # Limpar parâmetros da URL
                        st.query_params.clear()
                        # Remover pagamento pendente
                        st.session_state.pending_payments.pop(payment_id, None)
                    else:
                        st.error("❌ Erro ao enviar email. Entre em contato com o suporte.")
                else:
                    st.error("❌ Erro ao gerar chave. Entre em contato com o suporte.")
            else:
                st.error("❌ Informações de pagamento não encontradas.")
        
        elif payment_status == "failure":
            st.error("❌ Pagamento recusado ou cancelado.")
            st.query_params.clear()
        
        elif payment_status == "pending":
            st.warning("⏳ Pagamento pendente. Aguarde a confirmação.")
            st.query_params.clear()

# ============================================================
# VERIFICAÇÃO CORRETA COM API DO MERCADO PAGO
# ============================================================
def check_mp_payment_status(payment_id):
    """Verifica o status real do pagamento na API do Mercado Pago"""
    try:
        # Primeiro, buscar pagamentos associados a esta preferência
        # O payment_id aqui é o external_reference (ID da preferência)
        
        filters = {
            "external_reference": payment_id,
            "sort": "date_created",
            "criteria": "desc"
        }
        
        search_result = mp.payment().search(filters)
        
        if 'response' in search_result:
            payments = search_result['response'].get('results', [])
            
            if payments:
                # Pegar o pagamento mais recente
                latest_payment = payments[0]
                status = latest_payment.get('status')
                payment_id_actual = latest_payment.get('id')
                
                if status == 'approved':
                    return True, "Pagamento aprovado", payment_id_actual
                elif status == 'pending':
                    return False, "Pagamento pendente", payment_id_actual
                elif status == 'rejected':
                    return False, "Pagamento recusado", payment_id_actual
                elif status == 'in_process':
                    return False, "Pagamento em processo", payment_id_actual
                else:
                    return False, f"Status: {status}", payment_id_actual
            else:
                return False, "Nenhum pagamento encontrado para esta preferência", None
        
        return False, "Resposta inválida do Mercado Pago", None
        
    except Exception as e:
        return False, f"Erro ao verificar pagamento: {e}", None

def manual_payment_check():
    """Botão manual para verificar pagamento COM VERIFICAÇÃO REAL"""
    
    # Criar um container dedicado para as mensagens
    message_container = st.container()
    
    if st.button("🔄 Verificar Status com Mercado Pago", type="primary", key="verify_mp_btn"):
        if not st.session_state.pending_payments:
            with message_container:
                st.warning("Não há pagamentos pendentes para verificar.")
            return
            
        with message_container:
            st.info("Consultando Mercado Pago...⏳")
        
        # Usar um container específico para os resultados
        results_container = st.container()
        
        with results_container:
            for payment_id, payment_info in list(st.session_state.pending_payments.items()):
                email = payment_info["email"]
                plan = payment_info["plan"]
                
                # VERIFICAÇÃO REAL COM API
                is_paid, message, actual_payment_id = check_mp_payment_status(payment_id)
                
                # Criar colunas para cada resultado
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    if is_paid:
                        st.success(f"✅ {message} - {email}")
                    else:
                        st.warning(f"⏳ {message} - {email}")
                
                with col2:
                    if is_paid:
                        if st.button(f"🎯 Gerar Chave", key=f"gen_{payment_id}"):
                            generate_and_activate_key(email, plan, payment_id)
                    else:
                        st.button("🔄", key=f"refresh_{payment_id}", disabled=True)

# ============================================================
# ATUALIZAR A FUNÇÃO GENERATE_AND_ACTIVATE_KEY
# ============================================================
def generate_and_activate_key(email, plan, payment_id):
    """Gera e ativa a chave para um pagamento confirmado"""
    try:
        # Usar um container para as mensagens de geração
        gen_container = st.container()
        
        with gen_container:
            st.info("Gerando sua chave de acesso...⏳")
        
        # Gerar chave
        key_data = generate_user_key(email, plan)
        
        if save_user_key(email, key_data):
            # Tentar enviar email, se falhar mostra na tela
            email_sent = send_key_via_email(email, key_data["key"], plan)
            
            if email_sent:
                with gen_container:
                    st.success(f"🎉 Chave enviada para: {email}")
            else:
                with gen_container:
                    st.info("📋 Chave exibida na tela")
                
            # Remover pagamento pendente
            st.session_state.pending_payments.pop(payment_id, None)
            
            # Fazer login automaticamente
            st.session_state.user_email = email
            st.session_state.user_key = key_data["key"]
            st.session_state.key_valid = True
            
            # Botão para continuar
            with gen_container:
                if st.button("🚀 Acessar Sistema Premium", type="primary"):
                    st.rerun()
                
        else:
            with gen_container:
                st.error("❌ Erro ao salvar chave.")
            
    except Exception as e:
        with gen_container:
            st.error(f"❌ Erro ao gerar chave: {e}")
# ============================================================
# VERIFICAR CREDENCIAIS DO ZOHO (OPCIONAL)
# ============================================================
def test_zoho_credentials():
    """Testa as credenciais do Zoho Mail"""
    try:
        smtp_server = ZOHO_CONFIG["SMTP_HOST"]
        smtp_port = ZOHO_CONFIG["SMTP_PORT"]
        smtp_user = ZOHO_CONFIG["SMTP_USER"]
        smtp_pass = ZOHO_CONFIG["SMTP_PASS"]
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            st.success("✅ Credenciais do Zoho Mail estão corretas!")
            return True
            
    except Exception as e:
        st.error(f"❌ Erro nas credenciais do Zoho: {e}")
        st.info("""
        **🔧 Configure corretamente o Zoho Mail:**
        1. Verifique se o email e senha estão corretos
        2. Certifique-se de usar uma Senha de App (não a senha normal)
        3. Verifique se o acesso a apps menos seguros está ativado
        4. Confirme se a autenticação de 2 fatores está configurada corretamente
        """)
        return False
        
# ============================================================
# FUNÇÃO AUXILIAR PARA MOSTRAR PAGAMENTOS PENDENTES
# ============================================================
def show_pending_payments():
    """Mostra pagamentos pendentes de forma organizada"""
    if st.session_state.pending_payments:
        st.markdown("---")
        st.subheader("📋 Pagamentos Pendentes")
        
        # Container para os pagamentos
        payments_container = st.container()
        
        with payments_container:
            for i, (payment_id, payment_info) in enumerate(st.session_state.pending_payments.items()):
                email = payment_info["email"]
                plan = payment_info["plan"]
                created = payment_info["created_at"]
                
                # Formatar data
                try:
                    created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    created_str = created_dt.strftime("%d/%m/%Y %H:%M")
                except:
                    created_str = created
                
                st.markdown(f"""
                **Email:** {email}  
                **Plano:** {plan}  
                **Solicitado em:** {created_str}  
                **Status:** ⏳ Aguardando confirmação
                """)
                
                # Container para cada verificação individual
                check_container = st.container()
                
                with check_container:
                    # Usar índice único para cada botão
                    if st.button(f"🔍 Verificar Pagamento", key=f"check_single_{i}_{payment_id}"):
                        is_paid, message, actual_id = check_mp_payment_status(payment_id)
                        
                        if is_paid:
                            st.success(f"✅ {message}")
                            generate_and_activate_key(email, plan, payment_id)
                        else:
                            st.warning(f"⏳ {message}")
                
                st.markdown("---")

# ============================================================
# ATUALIZAR A FUNÇÃO DE PAGAMENTO PARA USAR ID CORRETO
# ============================================================
def create_payment_preference(email: str, price: float, description: str, plan: str) -> str:
    payment_id = str(uuid.uuid4())
    
    preference_data = {
        "items": [{
            "title": description,
            "quantity": 1,
            "unit_price": float(price),
            "currency_id": "BRL",
        }],
        "payer": {"email": email},
        "back_urls": {
            "success": "https://37d4991f431d.ngrok-free.app/?payment_status=success",
            "failure": "https://37d4991f431d.ngrok-free.app/?payment_status=failure", 
            "pending": "https://37d4991f431d.ngrok-free.app/?payment_status=pending"
        },
        "external_reference": payment_id,  # Este é o ID que usaremos para verificar
        "auto_return": "approved",
        "metadata": {
            "email": email,
            "plan": plan.lower(),
            "payment_id": payment_id
        },
    }

    try:
        preference = mp.preference().create(preference_data)
        if 'response' in preference:
            response = preference['response']
            init_point = response.get('init_point')
            sandbox_init_point = response.get('sandbox_init_point')
            
            if init_point or sandbox_init_point:
                if 'pending_payments' not in st.session_state:
                    st.session_state.pending_payments = {}
                
                # Salvar com o external_reference como ID
                st.session_state.pending_payments[payment_id] = {
                    "email": email,
                    "plan": plan,
                    "price": price,
                    "created_at": datetime.now().isoformat(),
                    "preference_id": response.get('id')  # Salvar também o ID da preferência
                }
                return init_point or sandbox_init_point
        
        return None
        
    except Exception as e:
        st.error(f"Erro ao criar pagamento: {e}")
        return None

# ============================================================
# Função para criar o link de pagamento e gerar a chave após
# a confirmação do pagamento
# ============================================================
def create_payment_based_on_plan(email: str) -> str:
    """Cria o link de pagamento com base no plano e gera a chave após pagamento"""
    
    # Verifica o plano escolhido pelo usuário
    selected_plan = st.session_state.get("selected_plan")
    
    if not selected_plan:
        st.error("Plano não selecionado corretamente.")
        return ""
    
    # Definir o preço e a descrição com base no plano
    if selected_plan == "Mensal":
        price = PLANO_MENSAL_PRECO
        description = "Acesso Mensal - Sistema Premium"
    elif selected_plan == "Vitalício":
        price = PLANO_VITALICIO_PRECO
        description = "Acesso Vitalício - Sistema Premium"
    elif selected_plan == "TestDrive":
        price = TEST_DRIVE_PRECO
        description = "Test Drive 24h - Acesso Completo"
    else:
        st.error("Plano não selecionado corretamente.")
        return ""

    # Gerar o link de pagamento
    payment_link = create_payment_preference(email, price, description, selected_plan)

    if payment_link:
        st.success("Link de pagamento gerado com sucesso!")
        # A chave será gerada e enviada por email APÓS a confirmação do pagamento
        # (não antes, como estava acontecendo)
        return payment_link
    else:
        st.error("Erro ao gerar o link de pagamento.")
        return ""

# ============================================================
# COMPONENTES DE INTERFACE
# ============================================================
def show_plan_cards():
    st.markdown("""
    <div style='text-align: center; margin: 30px 0;'>
        <h2 style='color: gold;'>🎉 Bem-vindo ao Sistema de Conteúdo Premium!</h2>
        <p style='color: silver;'>Transforme qualquer conteúdo da internet em arquivos para assistir offline!</p>
        <p style='color: silver;'>⚡ Funcionalidades:</p>
      ✅ Download de vídeos do YouTube, Instagram, TikTok e mais
    - ✅ Conversão para MP3
    - ✅ Suporte a múltiplos formatos e qualidades
    - ✅ Interface simples e intuitiva
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
        <div style='background: #8B4513; border: 2px solid gold; border-radius: 10px; padding: 20px; margin: 10px;'>
            <h3>🏰 Plano Mensal</h3>
            <h2>R$ {PLANO_MENSAL_PRECO:.2f}</h2>
            <p>30 dias de acesso ilimitado</p>
            <div style='text-align: left;'>
                <p>✓ Downloads ilimitados</p>
                <p>✓ Qualidade 4K/1080p</p>
                <p>✓ Conversão para MP3</p>
                <p>✓ Suporte prioritário</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("💳 Assinar Mensal", key="btn_mensal", use_container_width=True):
            st.session_state.selected_plan = "Mensal"
            st.session_state.show_cadastro = True
            st.rerun()
    
    with col2:
        st.markdown(f"""
        <div style='background: #1e3c72; border: 2px solid gold; border-radius: 10px; padding: 20px; margin: 10px;'>
            <h3>👑 Plano Vitalício</h3>
            <h2>R$ {PLANO_VITALICIO_PRECO:.2f}</h2>
            <p>Acesso permanente</p>
            <div style='text-align: left;'>
                <p>🌟 Tudo do mensal +</p>
                <p>✓ Acesso vitalício</p>
                <p>✓ Suporte 24/7 VIP</p>
                <p>✓ Conteúdo exclusivo</p>
                <p>✓ Atualizações vitalícias</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("👑 Assinar Vitalício", key="btn_vitalicio", use_container_width=True):
            st.session_state.selected_plan = "Vitalício"
            st.session_state.show_cadastro = True
            st.rerun()
    
    st.markdown("""
<div style='background: #2c3e50; padding: 20px; border-radius: 15px; margin: 20px 0;'>
    <h3 style='color: white; text-align: center;'>🎁 RECURSOS EXCLUSIVOS</h3>
    <div style='display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;'>
        <div style='background: #34495e; padding: 15px; border-radius: 8px; text-align: center;'>
            <h4 style='color: gold; margin: 0;'>📥 ILIMITADO</h4>
            <p style='color: white; margin: 5px 0 0;'>Downloads sem restrições</p>
        </div>
        <div style='background: #34495e; padding: 15px; border-radius: 8px; text-align: center;'>
            <h4 style='color: gold; margin: 0;'>🎬 4K/1080p</h4>
            <p style='color: white; margin: 5px 0 0;'>Máxima qualidade</p>
        </div>
        <div style='background: #34495e; padding: 15px; border-radius: 8px; text-align: center;'>
            <h4 style='color: gold; margin: 0;'>🎵 MP3</h4>
            <p style='color: white; margin: 5px 0 0;'>Conversão para áudio</p>
        </div>
        <div style='background: #34495e; padding: 15px; border-radius: 8px; text-align: center;'>
            <h4 style='color: gold; margin: 0;'>⚡ RÁPIDO</h4>
            <p style='color: white; margin: 5px 0 0;'>Velocidade máxima</p>
        </div>
        <div style='background: #34495e; padding: 15px; border-radius: 8px; text-align: center;'>
            <h4 style='color: gold; margin: 0;'>🛡️ SEGURO</h4>
            <p style='color: white; margin: 5px 0 0;'>Sem bloqueios</p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

def show_test_drive_option():
    st.markdown("---")
    
    st.markdown("""
    <div style='background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%); 
                padding: 20px; border-radius: 15px; margin: 20px 0; 
                border: 2px solid #ff9f43; text-align: center;'>
        <h3 style='color: white; margin: 0;'>🚀 EXPERIMENTE POR 24H POR APENAS R$ 2,00!</h3>
        <p style='color: white; margin: 5px 0;'>Acesso completo a TODOS os recursos premium para testar</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if st.button("🔥 TESTAR AGORA - R$ 2,00", key="btn_test_drive", 
                    use_container_width=True, type="primary"):
            st.session_state.selected_plan = "TestDrive"
            st.session_state.show_cadastro = True
            st.rerun()
    
    st.markdown("""
    <div style='text-align: center; margin: 15px 0;'>
        <p style='color: #95a5a6;'>🎯 <strong>Como funciona:</strong>
        <p>1. <strong>**Escolha**</strong>- seu plano de acesso</p>
        <p>2. <strong>**Pague**</strong>- de forma segura via Mercado Pago</p>
        <p>3. <strong>**Receba**</strong>- sua chave de acesso por email</p>
        <p>4. <strong>**Faça login**</strong>- e comece a baixar!</p>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# Config
# ============================================================
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "").strip()

def detect_ffmpeg_path():
    # Primeiro tenta encontrar no PATH
    p = shutil.which("ffmpeg")
    if p:
        return p
    
    # Verifica locais comuns no Streamlit Cloud
    common_paths = [
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            return path
            
    return None
FFMPEG_PATH = detect_ffmpeg_path()        

# ============================================================
# Notícias
# ============================================================
def news_search_all_web(query: str, limit: int = 15) -> List[Dict]:
    results: List[Dict] = []
    if not FEEDPARSER_OK:
        return results
    from urllib.parse import quote
    feeds = [
        f"https://news.google.com/rss/search?q={quote(query)}&hl=pt-BR&gl=BR&ceid=BR:pt-419",
        f"https://www.bing.com/news/search?q={quote(query)}&format=rss",
    ]
    seen = set()
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            if feed.bozo:
                continue
            for e in feed.entries:
                title = (e.get("title") or "").strip()
                link = (e.get("link") or "").strip()
                if not title or not link:
                    continue
                key = (title.lower(), link.lower())
                if key in seen:
                    continue
                seen.add(key)
                results.append({
                    "title": title,
                    "url": clean_url(link),
                    "source": (e.get("source") or {}).get("title") or e.get("source") or "",
                    "published": e.get("published") or e.get("updated") or "",
                    "desc": (e.get("summary") or "").strip(),
                })
        except Exception:
            continue
    return results[:limit]

# ============================================================
# YouTube
# ============================================================
def youtube_search(query: str, max_results: int = 15) -> List[Dict]:
    items: List[Dict] = []
    if YOUTUBE_API_KEY:
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {"part": "snippet","q": query,"type": "video","maxResults": max_results,"key": YOUTUBE_API_KEY}
        try:
            r = requests.get(url, params=params, timeout=20); r.raise_for_status()
            for it in r.json().get("items", []):
                vid = it["id"]["videoId"]
                sn = it.get("snippet", {})
                items.append({"video_id": vid,"title": sn.get("title"),"thumb": (sn.get("thumbnails", {}) or {}).get("medium", {}).get("url"),"channel": sn.get("channelTitle"),"url": f"https://www.youtube.com/watch?v={vid}"})
            return items
        except Exception:
            pass
    if not YTDLP_OK:
        return items
    ydl_opts = {"quiet": True,"skip_download": True,"extract_flat": True,"ignoreerrors": True,"noplaylist": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            for e in (info.get("entries") or [])[:max_results]:
                if not e:
                    continue
                items.append({"video_id": e.get("id"),"title": e.get("title"),"thumb": ((e.get("thumbnails") or [{}])[-1].get("url")) if e.get("thumbnails") else None,"channel": e.get("channel") or e.get("uploader"),"url": e.get("url") or e.get("webpage_url") or (f"https://www.youtube.com/watch?v={e.get('id')}" if e.get("id") else None)})
    except Exception:
        pass
    return items                    

# ============================================================
# ATUALIZAR A FUNÇÃO MANUAL_PAYMENT_CHECK COM CONTAINERS
# ============================================================
def manual_payment_check():
    """Botão manual para verificar pagamento COM VERIFICAÇÃO REAL"""
    
    # Criar um container dedicado para as mensagens
    message_container = st.container()
    
    # Usar key única baseada no timestamp
    unique_key = f"verify_mp_btn_{time.time()}"
    
    if st.button("🔄 Verificar Status com Mercado Pago", type="primary", key=unique_key):
        if not st.session_state.pending_payments:
            with message_container:
                st.warning("Não há pagamentos pendentes para verificar.")
            return
            
        with message_container:
            st.info("Consultando Mercado Pago...⏳")
        
        # Usar um container específico para os resultados
        results_container = st.container()
        
        with results_container:
            for i, (payment_id, payment_info) in enumerate(list(st.session_state.pending_payments.items())):
                email = payment_info["email"]
                plan = payment_info["plan"]
                
                # VERIFICAÇÃO REAL COM API
                is_paid, message, actual_payment_id = check_mp_payment_status(payment_id)
                
                # Criar colunas para cada resultado
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    if is_paid:
                        st.success(f"✅ {message} - {email}")
                    else:
                        st.warning(f"⏳ {message} - {email}")
                
                with col2:
                    if is_paid:
                        # Key única para cada botão de gerar chave
                        if st.button(f"🎯 Gerar", key=f"gen_{i}_{payment_id}"):
                            generate_and_activate_key(email, plan, payment_id)
                    else:
                        st.button("🔄", key=f"refresh_{i}_{payment_id}", disabled=True)

# ============================================================
# ATUALIZAR A FUNÇÃO GENERATE_AND_ACTIVATE_KEY
# ============================================================
def generate_and_activate_key(email, plan, payment_id):
    """Gera e ativa a chave para um pagamento confirmado"""
    try:
        # Usar um container para as mensagens de geração
        gen_container = st.container()
        
        with gen_container:
            st.info("Gerando sua chave de acesso...⏳")
        
        # Gerar chave apenas se o pagamento foi aprovado
        key_data = generate_user_key(email, plan)
        
        if save_user_key(email, key_data):
            if send_key_via_email(email, key_data["key"], plan):
                with gen_container:
                    st.success(f"🎉 Chave gerada e enviada para: {email}")
                    st.info(f"Sua chave: **{key_data['key']}**")
                
                # Remover pagamento pendente
                st.session_state.pending_payments.pop(payment_id, None)
                
                # Fazer login automaticamente
                st.session_state.user_email = email
                st.session_state.user_key = key_data["key"]
                st.session_state.key_valid = True
                
                # Adicionar pequeno delay para visualização
                time.sleep(2)
                st.rerun()
            else:
                with gen_container:
                    st.error("❌ Erro ao enviar email.")
        else:
            with gen_container:
                st.error("❌ Erro ao salvar chave.")
            
    except Exception as e:
        with gen_container:
            st.error(f"❌ Erro ao gerar chave: {e}")

# ============================================================
# ATUALIZAR A FUNÇÃO SHOW_PENDING_PAYMENTS
# ============================================================
def show_pending_payments():
    """Mostra pagamentos pendentes de forma organizada"""
    if st.session_state.pending_payments:
        st.markdown("---")
        st.subheader("📋 Pagamentos Pendentes")
        
        # Container para os pagamentos
        payments_container = st.container()
        
        with payments_container:
            for payment_id, payment_info in st.session_state.pending_payments.items():
                email = payment_info["email"]
                plan = payment_info["plan"]
                created = payment_info["created_at"]
                
                # Formatar data
                try:
                    created_dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                    created_str = created_dt.strftime("%d/%m/%Y %H:%M")
                except:
                    created_str = created
                
                st.markdown(f"""
                **Email:** {email}  
                **Plano:** {plan}  
                **Solicitado em:** {created_str}  
                **Status:** ⏳ Aguardando confirmação
                """)
                
                # Container para cada verificação individual
                check_container = st.container()
                
                with check_container:
                    if st.button(f"🔍 Verificar {email}", key=f"check_{payment_id}"):
                        is_paid, message, actual_id = check_mp_payment_status(payment_id)
                        
                        if is_paid:
                            st.success(f"✅ {message}")
                            generate_and_activate_key(email, plan, payment_id)
                        else:
                            st.warning(f"⏳ {message}")
            
            # Container para o botão de verificar todos
            #all_container = st.container()
            
            #with all_container:
                #st.markdown("---")
                #if st.button("🔄 Verificar Todos os Pagamentos", key="check_all_btn"):
                   # manual_payment_check()

# ============================================================
# ATUALIZAR A FUNÇÃO REGISTER_EMAIL PARA USAR CONTAINERS
# ============================================================
def register_email():
    st.subheader("📋 Finalizar Cadastro")
    
    email = st.text_input("Digite seu email:", placeholder="seu.email@exemplo.com")
    
    # Container para mensagens de pagamento
    payment_container = st.container()
    
    if st.button("Confirmar e Pagar", type="primary"):
        if not email or not is_valid_email(email):
            with payment_container:
                st.error("Por favor, insira um email válido.")
            return
        
        # Testar conexão com Mercado Pago primeiro
        if not test_mp_connection():
            with payment_container:
                st.error("Não foi possível conectar ao Mercado Pago. Tente novamente.")
            return
        
        # Gerar o link de pagamento com base no plano escolhido
        payment_link = create_payment_based_on_plan(email)
        
        if payment_link:
            with payment_container:
                st.success("✅ Redirecionando para pagamento!")
                st.markdown(f"""
                <div style="text-align: center; margin: 20px 0;">
                    <a href="{payment_link}" target="_blank" style="background-color: #009ee3; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">💳 Realizar Pagamento</a>
                </div>
                """, unsafe_allow_html=True)
            
            # Container para verificação manual
            verify_container = st.container()
            
            with verify_container:
                st.markdown("---")
                st.info("""
                **💡 Após realizar o pagamento:**
                1. Complete o pagamento no Mercado Pago
                2. Volte para esta página  
                3. Seus pagamentos aparecerão abaixo para verificação
                """)
                
                # Botão com key única
                if st.button("🔄 Verificar Meu Pagamento", type="secondary", key=f"manual_check_{email}"):
                    # Mostrar os pagamentos pendentes
                    show_pending_payments()
        else:
            with payment_container:
                st.error("❌ Erro ao gerar link de pagamento.")
                
def key_login_ui():
    st.sidebar.subheader("🔑 Acesso com Chave")
    
    if st.session_state.get("key_valid"):
        st.sidebar.success(f"✅ Acesso ativo")
        st.sidebar.info(f"Email: {st.session_state.get('user_email')}")
        
        status, key_data = check_key_status(st.session_state.user_email)
        st.sidebar.info(f"Status: {status}")
        
        # Botão para testar credenciais do Zoho
        #if st.sidebar.button("📧 Testar Configuração de Email", key="test_email_config"):
          #test_zoho_credentials()
        
        col1, col2 = st.sidebar.columns(2)
        
        with col2:
            if st.button("📋 Ver Status", use_container_width=True):
                status, key_data = check_key_status(st.session_state.user_email)
                st.sidebar.info(f"Status atual: {status}")
        
        if st.sidebar.button("🚪 Sair", use_container_width=True):
            for k in ["key_valid", "user_key", "user_email"]:
                st.session_state.pop(k, None)
            st.rerun()
        return
    
    email_input = st.sidebar.text_input("E-mail", value=st.session_state.get("user_email", ""))
    key_input = st.sidebar.text_input("Chave de Acesso", type="password")

    if st.sidebar.button("✅ Validar Chave"):
        if not email_input.strip() or not key_input.strip():
            st.sidebar.error("Informe email e chave.")
            return

        key_data = load_user_key(email_input.strip())
        if not key_data or key_data.get('key') != key_input.strip():
            st.sidebar.error("Chave inválida ou expirada.")
            return

        expiry_date = key_data.get("expiry_date")
        if expiry_date:
            expiry = datetime.fromisoformat(expiry_date)
            if expiry < datetime.now():
                st.sidebar.error("Chave expirada. Renove para continuar usando.")
                return

        st.session_state.user_key = key_input.strip()
        st.session_state.user_email = email_input.strip()
        st.session_state.key_valid = True
        st.sidebar.success("Acesso liberado!")
        st.rerun()
    
    # BOTÃO DE TESTE DE EMAIL TAMBÉM PARA USUÁRIOS NÃO LOGADOS
    st.sidebar.markdown("---")
    if st.sidebar.button("⚙️ Testar Configuração de Email", key="test_email_guest"):
        test_zoho_credentials()

# ============================================================
# SISTEMA DE DOWNLOAD (yt-dlp)
# ============================================================
class YDLLogger:
    def __init__(self):
        self.lines = []
    def debug(self, msg): self.lines.append(str(msg))
    def warning(self, msg): self.lines.append("WARN: "+str(msg))
    def error(self, msg): self.lines.append("ERR: "+str(msg))

def extract_audio_from_video(video_path: str, audio_path: str) -> bool:
    try:
        cmd = [
            'ffmpeg', '-i', video_path, 
            '-vn', '-acodec', 'pcm_s16le', 
            '-ar', '16000', '-ac', '1', 
            '-y', audio_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except Exception as e:
        st.error(f"Erro ao extrair áudio: {e}")
        return False

def transcribe_with_whisper(audio_path: str) -> str:
    """Transcreve áudio usando Whisper"""
    try:
        import whisper
        # Carregar o modelo (usando o modelo base para equilibrar velocidade/precisão)
        model = whisper.load_model("base")
        
        # Transcrever o áudio
        result = model.transcribe(audio_path, language="pt", task="transcribe")
        
        return result["text"]
    except ImportError:
        return "Erro: Whisper não está instalado. Use: pip install openai-whisper"
    except Exception as e:
        return f"Erro na transcrição com Whisper: {e}"

def transcribe_video(video_path: str) -> Tuple[bool, str]:
    try:
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
            temp_audio_path = temp_audio.name
        
        if not extract_audio_from_video(video_path, temp_audio_path):
            return False, "Falha ao extrair áudio"
        
        # Mostrar barra de progresso
        st.info("Transcrevendo áudio com Whisper...")
        
        # Usar Whisper para transcrição
        transcription = transcribe_with_whisper(temp_audio_path)
        
        try:
            os.unlink(temp_audio_path)
        except:
            pass
        
        return True, transcription
        
    except Exception as e:
        return False, f"Erro na transcrição: {e}"

def run_ytdlp(url: str, dest: str, fmt_choice: str, quality_choice: str) -> Tuple[bool, str, str]:
    # Configurar hooks de progresso
    progress_hook = DownloadProgressHook()
    
    ydl_opts = {
        "outtmpl": os.path.join(dest, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "nocheckcertificate": True,
        "progress_hooks": [progress_hook.hook],
    }
    
    if fmt_choice == "audio (mp3)":
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": '192'
            }]
        })
    else:
        target_map = {
            "best": "bestvideo+bestaudio/best",
            "1080p": "bv[height<=1080]+ba/b",
            "720p": "bv[height<=720]+ba/b", 
            "480p": "bv[height<=480]+ba/b",
            "360p": "bv[height<=360]+ba/b"
        }
        ydl_opts.update({
            "format": target_map.get(quality_choice, "bestvideo+bestaudio/best"),
            "merge_output_format": "mp4",
        })
    
    try:
        logger = YDLLogger()
        ydl_opts["logger"] = logger
        
        # Criar barra de progresso
        progress_hook.progress_bar = st.progress(0)
        progress_hook.status_text = st.empty()
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            return True, f"Download concluído: {os.path.basename(filename)}", "".join(logger.lines)
    except Exception as e:
        return False, f"Erro: {e}", ""

# ============================================================
# INTERFACE PRINCIPAL - ATUALIZADA
# ============================================================
def main():
# Inicializar todas as variáveis de sessão primeiro
    if 'key_valid' not in st.session_state:
        st.session_state.key_valid = False
    if 'download_path' not in st.session_state:
        st.session_state.download_path = os.path.join(os.path.expanduser("~"), "Downloads")
    if 'selected_plan' not in st.session_state:
        st.session_state.selected_plan = None
    if 'show_cadastro' not in st.session_state:
        st.session_state.show_cadastro = False
    if 'video_results' not in st.session_state:
        st.session_state.video_results = []
    if 'news_results' not in st.session_state:
        st.session_state.news_results = []
    if 'last_query' not in st.session_state:
        st.session_state.last_query = ""
    if 'selected_videos' not in st.session_state:
        st.session_state.selected_videos = set()
    if 'progress_bus' not in st.session_state:
        st.session_state.progress_bus = queue.Queue()
    if 'pending_payments' not in st.session_state:
        st.session_state.pending_payments = {}
        
        
    # Inicializar downloads gratuitos
    init_free_downloads()
    
    check_payment_status()
    # MOSTRAR BOTÃO MANUAL SE HOUVER PAGAMENTOS PENDENTES
    if st.session_state.pending_payments:
        st.info(f"📋 Há {len(st.session_state.pending_payments)} pagamento(s) pendente(s)")
            
    # MOSTRAR PAGAMENTOS PENDENTES
    show_pending_payments()    
    
    with st.sidebar:
        st.title("⚙️ Configurações")
        key_login_ui()
        
        if st.session_state.get("key_valid"):
            st.markdown("---")
            st.subheader("📂 Pasta de Downloads")
            
            st.info(f"Pasta atual: `{st.session_state.download_path}`")
            
            # Opção simples para mudar pasta também no sidebar
            new_path = st.text_input("Alterar pasta:", 
                                   value=st.session_state.download_path,
                                   key="sidebar_folder_input")
            
            if new_path != st.session_state.download_path:
                if os.path.isdir(new_path):
                    st.session_state.download_path = new_path
                    st.success("✅ Pasta atualizada!")
                    st.rerun()
                else:
                    st.error("❌ Pasta não encontrada!")


    if st.session_state.get("key_valid"):
        show_main_interface()
    else:
        show_welcome_screen()

def show_main_interface():
    st.title("🎬 Sistema de Download Premium")
    
    tab1, tab2, tab3 = st.tabs(["📥 Download por Link", "📰 Notícias", "🔍 Pesquisar Vídeos"])
    
    with tab1:
        st.subheader("Download Direto")
        links_text = st.text_area("Cole os links aqui (um por linha):", height=100)
        
        col1, col2 = st.columns(2)
        with col1:
            fmt_choice = st.selectbox("Formato", ["mp4", "audio (mp3)"])
        with col2:
            quality_choice = st.selectbox("Qualidade", ["best", "1080p", "720p", "480p", "360p"])
        
        if st.button("🚀 Iniciar Downloads", type="primary") and links_text.strip():
            links = [link.strip() for link in links_text.split('\n') if link.strip()]
            
            for i, link in enumerate(links):
                # Container para cada download individual
                with st.container():
                    st.write(f"**Download {i+1}/{len(links)}:** {link}")
                    
                    with st.status(f"Baixando {i+1}/{len(links)}...", state="running"):
                        success, message, logs = run_ytdlp(
                            link, 
                            st.session_state.download_path, 
                            fmt_choice, 
                            quality_choice
                        )
                        
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
    
    with tab2:
        query = st.text_input(
            "Digite o tema da pesquisa", 
            value=st.session_state.last_query,
            placeholder="ex.: eleições 2025, IA generativa, agronegócio…",
            key="search_query"
        )
        
        if st.button("Pesquisar", key="search_btn") and query.strip():
            st.session_state.last_query = query.strip()
            with st.spinner("Buscando notícias e vídeos…"):
                st.session_state.news_results = news_search_all_web(st.session_state.last_query, 15)
                st.session_state.video_results = youtube_search(st.session_state.last_query, 15)
                if not st.session_state.news_results: 
                    st.warning("Nenhuma notícia encontrada.")
                if not st.session_state.video_results: 
                    st.warning("Nenhum vídeo encontrado.")
            st.toast("Resultados atualizados.")
            
        if st.session_state.news_results:
            st.subheader("Notícias Encontradas")
            for art in st.session_state.news_results:
                st.markdown(f"**[{art.get('title','(sem título)')}]({art.get('url','')})**")
                st.write(f"*Resumo*: {BeautifulSoup(art.get('desc',''),'html.parser').get_text()}")
                meta = " · ".join([x for x in [art.get("source", "").strip(), art.get("published", "").strip()] if x])
                if meta:
                    st.caption(f"**Fonte e Data**: {meta}")
                st.write("---")
        else:
            st.info("Pesquise um tema para ver notícias.")
                
    with tab3:
        fmt_choice = st.selectbox("Formato", ["mp4", "audio (mp3)"], key="videos_format")
        quality_choice = st.selectbox("Qualidade (alvo)", ["best", "1080p", "720p", "480p", "360p"], key="videos_quality")
        parallel = st.checkbox("Baixar em paralelo (experimental)", value=False, key="parallel_videos")
        
        if st.session_state.video_results:
            cols = st.columns(3)
            for i, v in enumerate(st.session_state.video_results):
                with cols[i % 3]:
                    if v.get("thumb"): 
                        st.image(v["thumb"], use_container_width=True)
                    st.markdown(f"**[{v.get('title','(sem título)')}]({v['url']})**")
                    if st.checkbox("Selecionar", key=f"sel_{i}"): 
                        st.session_state.selected_videos.add(i)
                    else: 
                        st.session_state.selected_videos.discard(i)
            
            if st.button("Baixar selecionados") and st.session_state.selected_videos:
                indices = list(st.session_state.selected_videos)
                st.session_state.selected_videos = set()
                
                while not st.session_state.progress_bus.empty():
                    try: 
                        st.session_state.progress_bus.get_nowait()
                    except queue.Empty: 
                        break
                
                holders = {idx: {'bar': st.progress(0), 'txt': st.empty()} for idx in indices}
                
                def make_hook(idx, bus):
                    def _hook(d):
                        if d.get('status') == 'downloading':
                            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                            downloaded = d.get('downloaded_bytes', 0)
                            if total:
                                bus.put((idx, int(downloaded / total * 100)))
                    return _hook
                
                max_workers = 3 if parallel else 1
                with ThreadPoolExecutor(max_workers=max_workers) as ex:
                    futs = [ex.submit(
                        run_ytdlp, 
                        st.session_state.video_results[idx]['url'],
                        st.session_state.download_path,
                        fmt_choice, 
                        quality_choice,
                        False
                    ) for idx in indices]
                    
                    pending = set(futs)
                    while pending:
                        while True:
                            try:
                                idx, pct = st.session_state.progress_bus.get_nowait()
                                holders[idx]['bar'].progress(min(pct, 100))
                                holders[idx]['txt'].text(f"{st.session_state.video_results[idx]['title']} — {pct}%")
                            except queue.Empty:
                                break
                        
                        done = [f for f in list(pending) if f.done()]
                        for f in done:
                            try:
                                ok, msg, logs, transcription = f.result()
                                if ok: 
                                    st.success(msg)
                                else: 
                                    st.error(msg)
                            except Exception as e:
                                st.exception(e)
                            pending.remove(f)
                        
                        time.sleep(0.1)
        else:
            st.info("Pesquise um tema para ver vídeos.")

def show_welcome_screen():
    st.title("🚀 Sistema de Conteúdo Premium")
    st.markdown("""
    ## 📦 Tudo o que você precisa em um só lugar!
    
    **Download ilimitado de vídeos, músicas e conteúdo de qualquer plataforma**
    """)
    
    init_free_downloads()
    
    show_free_downloads_ui()
    
    show_plan_cards()
    show_test_drive_option()
    
    #st.markdown("---")
    #if st.button("⚙️ Testar Configuração de Email", key="test_email_main"):
        #test_zoho_credentials()
    
    if st.session_state.get('show_cadastro') and st.session_state.get('selected_plan'):
        register_email()

    # Rodapé
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; font-size: 0.9em;'>
        Sistema de Conteúdo Premium © 2024 | 
        <a href='#' style='color: #666;'>Termos de Uso</a> | 
        <a href='#' style='color: #666;'>Política de Privacidade</a>
    </div>
    """, unsafe_allow_html=True)    

# ============================================================
# SISTEMA DE DOWNLOAD - CORRIGIDO
# ============================================================
def download_media(url: str, download_path: str = None):
    if not download_path:
        download_path = st.session_state.get('download_path', os.path.join(os.path.expanduser("~"), "Downloads"))
    
    if not os.path.exists(download_path):
        os.makedirs(download_path)
    
    try:
        ydl_opts = {
            'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'format': 'best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'noplaylist': True,
            'progress_hooks': [lambda d: download_progress_hook(d)],
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return True, filename, info.get('title', 'arquivo')
    except Exception as e:
        return False, str(e), None

def download_progress_hook(d):
    if d['status'] == 'downloading':
        progress = float(d['_percent_str'].replace('%', '').strip())
        if 'progress_bar' in st.session_state:
            st.session_state.progress_bar.progress(progress / 100)

# ============================================================
# EXECUÇÃO PRINCIPAL
# ============================================================
if __name__ == "__main__":
    main()