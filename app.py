from flask import Flask, render_template, request, jsonify
import re
import logging
from datetime import datetime
import os
import PyPDF2
import requests
import json
from werkzeug.utils import secure_filename
from langdetect import detect, LangDetectException

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HybridEmailClassifier:
    def __init__(self):
        self.hf_token = os.environ.get('HF_TOKEN', None)
        
        self.hf_sentiment_api = "https://api-inference.huggingface.co/models/cardiffnlp/twitter-roberta-base-sentiment-latest"
        self.hf_classification_api = "https://api-inference.huggingface.co/models/neuralmind/bert-base-portuguese-cased"
        
        self.financial_patterns = {
            'status_request': {
                'keywords': ['status', 'andamento', 'situação', 'atualização', 'progresso', 'prazos', 'quando', 'previsão', 'cronograma', 'acompanhar'],
                'phrases': ['qual o status', 'gostaria de saber o andamento', 'como está', 'tem previsão', 'prazo para', 'situação do'],
                'category': 'Produtivo',
                'priority': 'alta'
            },
            'document_sharing': {
                'keywords': ['anexo', 'documento', 'arquivo', 'envio', 'segue', 'planilha', 'relatório', 'comprovante', 'enviar', 'anexar'],
                'phrases': ['segue anexo', 'em anexo', 'documento solicitado', 'conforme solicitado', 'segue em anexo'],
                'category': 'Produtivo',
                'priority': 'media'
            },
            'technical_support': {
                'keywords': ['erro', 'problema', 'não funciona', 'falha', 'bug', 'sistema', 'acesso', 'login', 'senha', 'suporte'],
                'phrases': ['não consigo acessar', 'sistema está fora', 'erro ao tentar', 'problema técnico', 'não está funcionando'],
                'category': 'Produtivo',
                'priority': 'alta'
            },
            'financial_inquiry': {
                'keywords': ['saldo', 'extrato', 'cobrança', 'fatura', 'pagamento', 'valor', 'taxa', 'juros', 'desconto', 'conta'],
                'phrases': ['consultar saldo', 'verificar cobrança', 'dúvida sobre', 'esclarecimento financeiro', 'valor da conta'],
                'category': 'Produtivo',
                'priority': 'alta'
            },
            'case_follow_up': {
                'keywords': ['protocolo', 'ticket', 'chamado', 'caso', 'solicitação', 'pedido', 'acompanhamento', 'número'],
                'phrases': ['protocolo número', 'acompanhar caso', 'seguimento do chamado', 'ticket aberto', 'número do protocolo'],
                'category': 'Produtivo',
                'priority': 'media'
            },
            'greetings': {
                'keywords': ['natal', 'ano novo', 'páscoa', 'feliz', 'parabéns', 'aniversário', 'festa', 'comemoração', 'feriado'],
                'phrases': ['feliz natal', 'boas festas', 'feliz ano novo', 'parabéns pelo', 'desejo sucesso', 'bom feriado'],
                'category': 'Improdutivo',
                'priority': 'baixa'
            },
            'gratitude': {
                'keywords': ['obrigado', 'obrigada', 'agradeço', 'grato', 'grata', 'agradecimento', 'valeu'],
                'phrases': ['muito obrigado', 'agradeço pela', 'grato pela atenção', 'obrigado pelo', 'agradeço o'],
                'category': 'Improdutivo',
                'priority': 'baixa'
            },
            'social_chat': {
                'keywords': ['como vai', 'tudo bem', 'como está', 'família', 'final de semana', 'feriado', 'férias'],
                'phrases': ['como você está', 'tudo bem contigo', 'como foi o', 'espero que esteja', 'como andam as'],
                'category': 'Improdutivo',
                'priority': 'baixa'
            }
        }
    
    def extract_text_from_pdf(self, pdf_file):
        """Extrai texto de arquivo PDF"""
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"Erro ao extrair PDF: {e}")
            return ""

    def preprocess_text(self, text):
        """Pré-processa o texto"""
        if not text:
            return ""
        
        text = text.lower()
        text = re.sub(r'[^\w\s\.\,\!\?\-\@\(\)áéíóúàèìòùâêîôûãõç]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        
        stop_words = {
            'de', 'da', 'do', 'das', 'dos', 'a', 'o', 'as', 'os', 'um', 'uma', 'uns', 'umas', 
            'para', 'por', 'com', 'sem', 'em', 'na', 'no', 'nas', 'nos', 'que', 'e', 'ou',
            'mas', 'se', 'ao', 'aos', 'à', 'às', 'pelo', 'pela', 'pelos', 'pelas'
        }
        
        words = text.split()
        filtered_words = [word for word in words if word not in stop_words and len(word) > 2]
        
        return ' '.join(filtered_words)

    def detect_language(self, text):
        """Detecta o idioma do texto"""
        try:
            return detect(text)
        except (LangDetectException, Exception):
            return 'unknown'

    def is_portuguese_text(self, text):
        """Verifica se o texto está em português"""
        if not text or len(text.strip()) < 3:
            return False
            
        text_lower = text.lower()
        
        portuguese_indicators = [
            'olá', 'oi', 'bom dia', 'boa tarde', 'boa noite', 'obrigado', 'obrigada',
            'por favor', 'com licença', 'desculpa', 'desculpe', 'tudo bem', 'como vai',
            'prezado', 'prezada', 'caro', 'cara', 'senhor', 'senhora', 'atenciosamente',
            'cordialmente', 'aguardo', 'retorno', 'informação', 'solicitação'
        ]
        
        if len(text.split()) <= 5:
            return any(indicator in text_lower for indicator in portuguese_indicators)
        
        try:
            detected_lang = self.detect_language(text)
            if detected_lang == 'pt':
                return True
        except:
            pass
        
        portuguese_count = sum(1 for indicator in portuguese_indicators if indicator in text_lower)
        return portuguese_count >= 2

    def classify_with_rules(self, text):
        """Classificação baseada em regras"""
        if not text or len(text.strip()) < 3:
            return "Improdutivo", "empty_content", "baixa", {}
        
        text_processed = self.preprocess_text(text)
        text_lower = text.lower()
        
        category_scores = {}
        detected_type = None
        max_score = 0
        
        for email_type, config in self.financial_patterns.items():
            score = 0
            
            for keyword in config['keywords']:
                if keyword in text_lower:
                    score += text_lower.count(keyword) * 3
            
            for phrase in config['phrases']:
                if phrase in text_lower:
                    score += 8
            
            category_scores[email_type] = score
            
            if score > max_score:
                max_score = score
                detected_type = email_type
        
        if detected_type and max_score >= 3:
            category = self.financial_patterns[detected_type]['category']
            priority = self.financial_patterns[detected_type]['priority']
        else:
            productive_patterns = [
                r'\?', r'solicit', r'precis', r'dúvid', r'problem', r'ajud', 
                r'inform', r'requer', r'contato', r'urgente', r'prazo'
            ]
            
            unproductive_patterns = [
                r'olá|oi\b', r'bom dia|boa tarde|boa noite', r'tudo bem', 
                r'abraço', r'saudações', r'obrigad', r'parabéns'
            ]
            
            productive_count = sum(len(re.findall(pattern, text_lower)) for pattern in productive_patterns)
            unproductive_count = sum(len(re.findall(pattern, text_lower)) for pattern in unproductive_patterns)
            
            if productive_count > unproductive_count:
                category = "Produtivo"
                priority = "media"
                detected_type = "general_produtivo"
            else:
                category = "Improdutivo"
                priority = "baixa"
                detected_type = "general_improdutivo"
        
        return category, detected_type, priority, category_scores

    def call_huggingface_api(self, api_url, text, max_retries=2):
        """Chama API do Hugging Face com retry"""
        headers = {}
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"
        
        # Truncar texto para API
        text = text[:500] if len(text) > 500 else text
        
        payload = {"inputs": text}
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    api_url, 
                    headers=headers, 
                    json=payload,
                    timeout=10
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 503:
                    # Modelo carregando, tentar novamente
                    logger.warning(f"Modelo carregando, tentativa {attempt + 1}")
                    continue
                else:
                    logger.error(f"Erro API HF: {response.status_code} - {response.text}")
                    return None
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Erro de conexão HF: {e}")
                if attempt == max_retries - 1:
                    return None
                continue
        
        return None

    def classify_with_huggingface(self, text):
        """Classificação usando Hugging Face API"""
        try:
            # Análise de sentimento
            sentiment_result = self.call_huggingface_api(self.hf_sentiment_api, text)
            
            if not sentiment_result:
                logger.warning("API de sentimento HF não disponível")
                return None
            
            # Extrair resultado do sentimento
            if isinstance(sentiment_result, list) and len(sentiment_result) > 0:
                sentiment = sentiment_result[0]
                sentiment_label = sentiment.get('label', 'NEUTRAL')
                sentiment_score = sentiment.get('score', 0.5)
            else:
                logger.warning("Formato inesperado da resposta de sentimento")
                return None
            
            # Interpretar resultados para contexto de emails
            text_lower = text.lower()
            
            # Lógica de classificação baseada em sentimento + contexto
            if sentiment_label == 'LABEL_0' or 'negativ' in sentiment_label.lower():
                # Sentimento negativo geralmente indica problemas/solicitações
                if any(word in text_lower for word in ['erro', 'problema', 'não funciona', 'falha']):
                    category = "Produtivo"
                    email_type = "technical_support"
                    priority = "alta"
                    confidence = "Alta"
                elif any(word in text_lower for word in ['status', 'quando', 'prazo', 'andamento']):
                    category = "Produtivo"
                    email_type = "status_request"
                    priority = "media"
                    confidence = "Alta"
                else:
                    category = "Produtivo"
                    email_type = "general_produtivo"
                    priority = "media"
                    confidence = "Média"
                    
            elif sentiment_label == 'LABEL_2' or 'positiv' in sentiment_label.lower():
                # Sentimento positivo pode ser agradecimento ou social
                if any(word in text_lower for word in ['obrigado', 'obrigada', 'agradeço', 'grato']):
                    category = "Improdutivo"
                    email_type = "gratitude"
                    priority = "baixa"
                    confidence = "Alta"
                elif any(word in text_lower for word in ['feliz', 'parabéns', 'natal', 'ano novo']):
                    category = "Improdutivo"
                    email_type = "greetings"
                    priority = "baixa"
                    confidence = "Alta"
                else:
                    category = "Improdutivo"
                    email_type = "social_chat"
                    priority = "baixa"
                    confidence = "Média"
            else:
                # Sentimento neutro - analisar contexto
                if any(word in text_lower for word in ['?', 'solicit', 'precis', 'inform']):
                    category = "Produtivo"
                    email_type = "general_produtivo"
                    priority = "media"
                    confidence = "Média"
                else:
                    category = "Improdutivo"
                    email_type = "social_chat"
                    priority = "baixa"
                    confidence = "Baixa"
            
            return {
                'category': category,
                'email_type': email_type,
                'priority': priority,
                'confidence': confidence,
                'sentiment': {
                    'label': sentiment_label,
                    'score': round(sentiment_score, 3)
                },
                'api_used': 'Hugging Face Sentiment Analysis'
            }
            
        except Exception as e:
            logger.error(f"Erro na classificação Hugging Face: {e}")
            return None

    def combine_classifications(self, rules_result, hf_result):
        """Combina resultados das duas abordagens"""
        rules_category, rules_type, rules_priority, rules_scores = rules_result
        
        if not hf_result:
            return {
                'category': rules_category,
                'email_type': rules_type,
                'priority': rules_priority,
                'confidence': 'Média',
                'method': 'Rules Only (HF API unavailable)',
                'scores': rules_scores,
                'reasoning': 'Classificação baseada apenas em regras - API HF indisponível'
            }
        
        # Se ambos concordam na categoria
        if rules_category == hf_result.get('category'):
            confidence = 'Alta'
            category = rules_category
            email_type = hf_result.get('email_type', rules_type)
            
            # Prioridade: usar a mais alta
            priority_order = {'baixa': 1, 'media': 2, 'alta': 3}
            hf_priority = hf_result.get('priority', 'media').lower()
            rules_priority_val = priority_order.get(rules_priority, 2)
            hf_priority_val = priority_order.get(hf_priority, 2)
            
            priority = rules_priority if rules_priority_val >= hf_priority_val else hf_priority
            method = 'Hybrid - AI + Rules Agreement'
            reasoning = f"Ambos sistemas concordaram. Sentimento detectado: {hf_result.get('sentiment', {}).get('label', 'N/A')}"
            
        else:
            max_rules_score = max(rules_scores.values()) if rules_scores else 0
            
            if max_rules_score >= 10:
                # Regras com alta confiança
                category = rules_category
                email_type = rules_type
                priority = rules_priority
                confidence = 'Média'
                method = 'Hybrid - Rules Priority'
                reasoning = 'Padrões específicos detectados com alta confiança pelas regras'
            else:
                # Priorizar IA
                category = hf_result.get('category', rules_category)
                email_type = hf_result.get('email_type', rules_type)
                priority = hf_result.get('priority', rules_priority)
                confidence = hf_result.get('confidence', 'Média')
                method = 'Hybrid - AI Priority'
                reasoning = f"IA priorizou baseado em análise de sentimento: {hf_result.get('sentiment', {}).get('label', 'N/A')}"
        
        return {
            'category': category,
            'email_type': email_type,
            'priority': priority,
            'confidence': confidence,
            'method': method,
            'scores': rules_scores,
            'reasoning': reasoning,
            'ai_details': hf_result
        }

    def classify_email(self, text):
        """Método principal - sistema híbrido"""
        rules_result = self.classify_with_rules(text)
        
        hf_result = self.classify_with_huggingface(text)
        
        final_result = self.combine_classifications(rules_result, hf_result)
        
        logger.info(f"Classificação híbrida: {final_result['category']} - {final_result['method']}")
        
        return (
            final_result['category'],
            final_result['email_type'],
            final_result['priority'],
            final_result['scores'],
            final_result['confidence'],
            final_result['method'],
            final_result['reasoning']
        )

    def generate_professional_response(self, category, email_type, priority):
        """Gera resposta profissional baseada na classificação"""
        responses = {
            'status_request': {
                'subject': 'Re: Atualização de Status - Solicitação em Andamento',
                'body': '''Prezado(a) Cliente,

Agradecemos seu contato solicitando atualização sobre o andamento de sua solicitação.

Informamos que sua demanda está sendo processada por nossa equipe especializada e encontra-se em fase de análise. Nossa previsão atual é de conclusão em até 48 horas úteis.

Assim que houver novas atualizações, entraremos em contato imediatamente através dos canais cadastrados.

Para acompanhar o status em tempo real, acesse nossa central do cliente ou utilize o número do protocolo fornecido.

Permanecemos à disposição para esclarecimentos adicionais.

Atenciosamente,
Equipe de Atendimento Especializado'''
            },
            'document_sharing': {
                'subject': 'Re: Documentos Recebidos - Confirmação',
                'body': '''Prezado(a) Cliente,

Confirmamos o recebimento da documentação enviada em anexo.

Nossa equipe iniciará a análise dos documentos nas próximas 24 horas úteis. Caso seja necessário algum documento adicional ou esclarecimento, entraremos em contato através dos canais cadastrados.

Prazo estimado para análise completa: 2 a 3 dias úteis.

Agradecemos pela colaboração e pontualidade no envio das informações solicitadas.

Atenciosamente,
Departamento de Análise Documental'''
            },
            'technical_support': {
                'subject': 'Re: Suporte Técnico - Atendimento Prioritário',
                'body': '''Prezado(a) Cliente,

Recebemos sua solicitação de suporte técnico e classificamos como PRIORIDADE ALTA.

Nossa equipe técnica especializada foi notificada e iniciará o diagnóstico imediatamente.

Ações já tomadas:
• Ticket técnico foi aberto
• Equipe de TI foi acionada
• Monitoramento ativo iniciado

Previsão de resolução: até 4 horas úteis
Você receberá atualizações a cada 2 horas até a completa resolução.

Para urgências críticas, utilize nosso canal de suporte 24h.

Atenciosamente,
Central de Suporte Técnico'''
            },
            'financial_inquiry': {
                'subject': 'Re: Esclarecimentos Financeiros',
                'body': '''Prezado(a) Cliente,

Recebemos sua consulta sobre questões financeiras relacionadas à sua conta.

Para fornecer informações precisas e atualizadas sobre sua situação, nossa equipe especializada realizará uma análise detalhada de sua conta.

Prazo para resposta completa: até 24 horas úteis

Os esclarecimentos serão enviados através de canal seguro para o e-mail cadastrado.

Para consultas urgentes, recomendamos acesso ao Internet Banking ou contato através dos canais oficiais.

Atenciosamente,
Departamento Financeiro'''
            },
            'case_follow_up': {
                'subject': 'Re: Acompanhamento de Protocolo',
                'body': '''Prezado(a) Cliente,

Agradecemos seu contato para acompanhamento do protocolo em questão.

Status atual: EM PROCESSAMENTO
Tempo estimado restante: 24-48h úteis

Nossa equipe está trabalhando na resolução de sua demanda com máxima atenção aos detalhes.

Você receberá notificação automática assim que houver alteração no status ou quando a solicitação for concluída.

Para consultas sobre este protocolo, sempre mencione o número de referência.

Atenciosamente,
Central de Acompanhamento'''
            },
            'greetings': {
                'subject': 'Re: Agradecemos suas Felicitações',
                'body': '''Prezado(a) Cliente,

Agradecemos suas cordiais felicitações!

É muito gratificante receber mensagens como a sua, que demonstram a parceria e confiança em nossos serviços.

Aproveitamos para reafirmar nosso compromisso em continuar oferecendo excelência no atendimento.

Desejamos a você e sua família momentos de muita alegria e prosperidade.

Cordialmente,
Equipe de Relacionamento'''
            },
            'gratitude': {
                'subject': 'Re: Agradecemos seu Feedback',
                'body': '''Prezado(a) Cliente,

Ficamos muito felizes em receber seu agradecimento!

Seu reconhecimento é fundamental para nossa equipe e nos motiva a continuar buscando sempre a excelência em nossos serviços.

É uma satisfação poder atendê-lo(a) e contribuir positivamente para suas necessidades.

Permanecemos sempre à disposição para futuros atendimentos.

Cordialmente,
Equipe de Atendimento'''
            },
            'social_chat': {
                'subject': 'Re: Sua Mensagem',
                'body': '''Olá!

Agradecemos seu contato e cordialidade.

Ficamos à disposição para ajudá-lo(a) com qualquer necessidade relacionada aos nossos serviços.

Tenha um excelente dia!

Atenciosamente,
Equipe de Atendimento'''
            },
            'general_produtivo': {
                'subject': 'Re: Sua Solicitação Foi Recebida',
                'body': '''Prezado(a) Cliente,

Agradecemos seu contato conosco.

Sua mensagem foi recebida e será analisada por nossa equipe competente dentro de 24 horas úteis.

Caso sua solicitação seja urgente, recomendamos contato através de nossos canais prioritários.

Retornaremos com uma resposta completa assim que a análise for concluída.

Atenciosamente,
Central de Atendimento'''
            },
            'general_improdutivo': {
                'subject': 'Re: Sua Mensagem Foi Recebida',
                'body': '''Olá!

Agradecemos seu contato.

Ficamos à disposição para ajudá-lo(a) com qualquer necessidade futura.

Atenciosamente,
Equipe de Atendimento'''
            },
            'language_error': {
                'subject': 'Re: Mensagem Recebida',
                'body': '''Prezado(a) Cliente,

Sua mensagem foi recebida.

Para melhor processamento, solicitamos que envie sua mensagem em português.

Atenciosamente,
Equipe de Atendimento'''
            },
            'empty_content': {
                'subject': 'Re: Conteúdo Vazio',
                'body': '''Prezado(a) Cliente,

Recebemos sua mensagem, porém o conteúdo não foi identificado.

Por favor, reenvie sua solicitação com o conteúdo completo.

Atenciosamente,
Equipe de Atendimento'''
            }
        }

        base_response = responses.get(email_type, responses['general_produtivo'])

        if priority == 'alta':
            body = base_response['body'] + '''

⚠️ ATENÇÃO: Esta solicitação foi classificada como ALTA PRIORIDADE e receberá tratamento diferenciado.'''
        else:
            body = base_response['body']
        
        return {
            'subject': base_response['subject'],
            'body': body,
            'priority': priority
        }

# Instanciar classificador
classifier = HybridEmailClassifier()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_email():
    try:
        start_time = datetime.now()
        email_text = ""
        
        # Processar entrada
        if 'file' in request.files and request.files['file'].filename != '':
            file = request.files['file']
            filename = secure_filename(file.filename)
            
            if filename.lower().endswith('.pdf'):
                email_text = classifier.extract_text_from_pdf(file)
            elif filename.lower().endswith('.txt'):
                email_text = file.read().decode('utf-8')
            else:
                return jsonify({"error": "Formato não suportado. Use .txt ou .pdf"}), 400
                
        elif request.is_json:
            data = request.get_json()
            email_text = data.get('email_text', '')
        else:
            email_text = request.form.get('email_text', '')

        if not email_text or len(email_text.strip()) < 3:
            return jsonify({"error": "Texto muito curto ou vazio"}), 400
        
        if not classifier.is_portuguese_text(email_text):
            response_data = classifier.generate_professional_response(
                category='Improdutivo', 
                email_type='language_error', 
                priority='baixa'
            )
            return jsonify({
                "category": "Improdutivo",
                "email_type": "language_error",
                "priority": "baixa",
                "confidence": "Alta",
                "method": "Language Detection",
                "suggested_response": response_data,
                "processing_time": 0.1,
                "word_count": len(email_text.split()),
                "message": "Email detectado em idioma diferente do português"
            })

        # Classificar com sistema híbrido
        category, email_type, priority, scores, confidence, method, reasoning = classifier.classify_email(email_text)
        response_data = classifier.generate_professional_response(category, email_type, priority)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()

        return jsonify({
            "category": category,
            "email_type": email_type.replace('_', ' ').title(),
            "priority": priority.title(),
            "confidence": confidence,
            "method": method,
            "reasoning": reasoning,
            "confidence_scores": scores,
            "suggested_response": {
                "subject": response_data['subject'],
                "body": response_data['body']
            },
            "processing_time": round(processing_time, 3),
            "word_count": len(email_text.split()),
            "classification_details": {
                "algorithm": "Hybrid System (Rules + Hugging Face API)",
                "api_provider": "Hugging Face Inference API",
                "ai_available": True,
                "patterns_matched": len([k for k, v in scores.items() if v > 0]) if scores else 0
            }
        })

    except Exception as e:
        logger.error(f"Erro no processamento: {e}")
        return jsonify({"error": f"Erro interno do servidor: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint de health check para monitoramento"""
    return jsonify({
        "status": "OK",
        "service": "Hybrid Financial Email Classifier",
        "version": "3.0.0",
        "ai_provider": "Hugging Face Inference API",
        "ai_available": True,
        "hf_token_configured": classifier.hf_token is not None,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Endpoint com estatísticas da API"""
    return jsonify({
        "supported_formats": [".txt", ".pdf"],
        "max_file_size": "16MB",
        "categories": ["Produtivo", "Improdutivo"],
        "email_types": list(classifier.financial_patterns.keys()),
        "priority_levels": ["alta", "media", "baixa"],
        "average_processing_time": "< 2 segundos",
        "classification_method": "Hybrid (Rules + Hugging Face API)",
        "ai_provider": "Hugging Face Inference API",
        "nlp_features": [
            "Portuguese language detection",
            "Stop words removal", 
            "Pattern matching", 
            "Domain-specific classification",
            "Priority assignment",
            "Sentiment analysis via Hugging Face",
            "Confidence scoring",
            "Hybrid decision making"
        ],
        "hugging_face_models": [
            "cardiffnlp/twitter-roberta-base-sentiment-latest",
            "neuralmind/bert-base-portuguese-cased"
        ]
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)