from flask import Flask, render_template, request, jsonify
import re
import logging
from datetime import datetime
import os
import PyPDF2
import io
from werkzeug.utils import secure_filename
from langdetect import detect, LangDetectException

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Criar pasta uploads se não existir
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FinancialEmailClassifier:
    def __init__(self):
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
        """Pré-processa o texto removendo caracteres especiais e stop words"""
        if not text:
            return ""
        
        # Converter para minúsculas
        text = text.lower()
        
        # Remover caracteres especiais mantendo acentos
        text = re.sub(r'[^\w\s\.\,\!\?\-\@\(\)áéíóúàèìòùâêîôûãõç]', ' ', text)
        
        # Normalizar espaços
        text = re.sub(r'\s+', ' ', text)
        
        # Stop words em português
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
        
        # Palavras/frases comuns em português
        portuguese_indicators = [
            'olá', 'oi', 'bom dia', 'boa tarde', 'boa noite', 'obrigado', 'obrigada',
            'por favor', 'com licença', 'desculpa', 'desculpe', 'tudo bem', 'como vai',
            'prezado', 'prezada', 'caro', 'cara', 'senhor', 'senhora', 'atenciosamente',
            'cordialmente', 'aguardo', 'retorno', 'informação', 'solicitação'
        ]
        
        # Para textos curtos, verificar palavras específicas
        if len(text.split()) <= 5:
            return any(indicator in text_lower for indicator in portuguese_indicators)
        
        # Para textos maiores, usar detecção de idioma
        try:
            detected_lang = self.detect_language(text)
            if detected_lang == 'pt':
                return True
        except:
            pass
        
        # Fallback: verificar presença de palavras portuguesas
        portuguese_count = sum(1 for indicator in portuguese_indicators if indicator in text_lower)
        return portuguese_count >= 2

    def classify_email(self, text):
        """Classifica o email em categorias"""
        if not text or len(text.strip()) < 3:
            return "Improdutivo", "empty_content", "baixa", {}
        
        text_processed = self.preprocess_text(text)
        text_lower = text.lower()
        
        category_scores = {}
        detected_type = None
        max_score = 0
        
        # Calcular scores para cada tipo de email
        for email_type, config in self.financial_patterns.items():
            score = 0
            
            # Pontuação por keywords
            for keyword in config['keywords']:
                if keyword in text_lower:
                    score += text_lower.count(keyword) * 3
            
            # Pontuação por frases completas (peso maior)
            for phrase in config['phrases']:
                if phrase in text_lower:
                    score += 8
            
            category_scores[email_type] = score
            
            if score > max_score:
                max_score = score
                detected_type = email_type
        
        # Se encontrou padrão específico
        if detected_type and max_score >= 3:
            category = self.financial_patterns[detected_type]['category']
            priority = self.financial_patterns[detected_type]['priority']
        else:
            # Classificação baseada em indicadores gerais
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
        
        logger.info(f"Classificação: {category} - Tipo: {detected_type} - Prioridade: {priority} - Score: {max_score}")
        
        return category, detected_type, priority, category_scores

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

# Instanciar o classificador
classifier = FinancialEmailClassifier()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_email():
    try:
        start_time = datetime.now()
        email_text = ""
        
        # Processar arquivo ou texto direto
        if 'file' in request.files and request.files['file'].filename != '':
            file = request.files['file']
            filename = secure_filename(file.filename)
            
            if filename.lower().endswith('.pdf'):
                email_text = classifier.extract_text_from_pdf(file)
            elif filename.lower().endswith('.txt'):
                email_text = file.read().decode('utf-8')
            else:
                return jsonify({"error": "Formato de arquivo não suportado. Use .txt ou .pdf"}), 400
                
        elif request.is_json:
            data = request.get_json()
            email_text = data.get('email_text', '')
        else:
            email_text = request.form.get('email_text', '')

        # Validar entrada
        if not email_text or len(email_text.strip()) < 3:
            return jsonify({"error": "Texto do email muito curto ou vazio."}), 400
        
        # Verificar se está em português
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
                "suggested_response": response_data,
                "processing_time": 0.1,
                "word_count": len(email_text.split()),
                "message": "Email detectado em idioma diferente do português"
            })

        # Classificar email
        category, email_type, priority, scores = classifier.classify_email(email_text)
        response_data = classifier.generate_professional_response(category, email_type, priority)
        
        # Calcular tempo de processamento
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # Calcular confiança
        max_score = max(scores.values()) if scores else 0
        confidence = "Alta" if max_score >= 8 else "Média" if max_score >= 3 else "Baixa"
        
        logger.info(f"Email processado: {category} - {email_type} - {priority} - Confiança: {confidence}")

        return jsonify({
            "category": category,
            "email_type": email_type.replace('_', ' ').title(),
            "priority": priority.title(),
            "confidence": confidence,
            "confidence_scores": scores,
            "suggested_response": {
                "subject": response_data['subject'],
                "body": response_data['body']
            },
            "processing_time": round(processing_time, 3),
            "word_count": len(email_text.split()),
            "classification_details": {
                "method": "NLP Pattern Matching",
                "algorithm": "Financial Domain Specific Rules",
                "patterns_matched": len([k for k, v in scores.items() if v > 0])
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
        "service": "Financial Email Classifier",
        "version": "2.0.0",
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
        "average_processing_time": "< 0.5 segundos",
        "nlp_features": [
            "Portuguese language detection",
            "Stop words removal", 
            "Pattern matching", 
            "Domain-specific classification",
            "Priority assignment"
        ]
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)