from flask import Flask, render_template, request, jsonify, send_from_directory
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

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FinancialEmailClassifier:
    def __init__(self):
        self.financial_patterns = {
            'status_request': {
                'keywords': ['status', 'andamento', 'situação', 'atualização', 'progresso', 'prazos', 'quando', 'previsão', 'cronograma'],
                'phrases': ['qual o status', 'gostaria de saber o andamento', 'como está', 'tem previsão', 'prazo para'],
                'category': 'Produtivo',
                'priority': 'alta'
            },
            'document_sharing': {
                'keywords': ['anexo', 'documento', 'arquivo', 'envio', 'segue', 'planilha', 'relatório', 'comprovante'],
                'phrases': ['segue anexo', 'em anexo', 'documento solicitado', 'conforme solicitado'],
                'category': 'Produtivo',
                'priority': 'media'
            },
            'technical_support': {
                'keywords': ['erro', 'problema', 'não funciona', 'falha', 'bug', 'sistema', 'acesso', 'login', 'senha'],
                'phrases': ['não consigo acessar', 'sistema está fora', 'erro ao tentar', 'problema técnico'],
                'category': 'Produtivo',
                'priority': 'alta'
            },
            'financial_inquiry': {
                'keywords': ['saldo', 'extrato', 'cobrança', 'fatura', 'pagamento', 'valor', 'taxa', 'juros', 'desconto'],
                'phrases': ['consultar saldo', 'verificar cobrança', 'dúvida sobre', 'esclarecimento financeiro'],
                'category': 'Produtivo',
                'priority': 'alta'
            },
            'case_follow_up': {
                'keywords': ['protocolo', 'ticket', 'chamado', 'caso', 'solicitação', 'pedido', 'acompanhamento'],
                'phrases': ['protocolo número', 'acompanhar caso', 'seguimento do chamado', 'ticket aberto'],
                'category': 'Produtivo',
                'priority': 'media'
            },
            'greetings': {
                'keywords': ['natal', 'ano novo', 'páscoa', 'feliz', 'parabéns', 'aniversário', 'festa', 'comemoração'],
                'phrases': ['feliz natal', 'boas festas', 'feliz ano novo', 'parabéns pelo', 'desejo sucesso'],
                'category': 'Improdutivo',
                'priority': 'baixa'
            },
            'gratitude': {
                'keywords': ['obrigado', 'obrigada', 'agradeço', 'grato', 'grata', 'agradecimento'],
                'phrases': ['muito obrigado', 'agradeço pela', 'grato pela atenção'],
                'category': 'Improdutivo',
                'priority': 'baixa'
            },
            'irrelevant': {
                'keywords': ['receita', 'culinária', 'futebol', 'novela', 'fofoca', 'piada', 'meme'],
                'phrases': ['você viu o jogo', 'receita de bolo', 'como fazer'],
                'category': 'Improdutivo',
                'priority': 'baixa'
            }
        }
    
    def extract_text_from_pdf(self, pdf_file):
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            return text
        except Exception as e:
            logger.error(f"Erro ao extrair PDF: {e}")
            return ""

    def preprocess_text(self, text):
        text = text.lower()
        text = re.sub(r'[^\w\s\.\,\!\?\-\@\(\)]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        
        stop_words = {'de', 'da', 'do', 'das', 'dos', 'a', 'o', 'as', 'os', 'um', 'uma', 'uns', 'umas', 'para', 'por', 'com', 'sem', 'em', 'na', 'no', 'nas', 'nos'}
        words = text.split()
        filtered_words = [word for word in words if word not in stop_words and len(word) > 2]
        
        return ' '.join(filtered_words)

    def detect_language(self, text):
        try:
            return detect(text)
        except LangDetectException:
            return 'unknown'

    def classify_email(self, text):
        text_processed = self.preprocess_text(text)
        text_lower = text.lower()
        
        category_scores = {}
        detected_type = None
        max_score = 0
        
        for email_type, config in self.financial_patterns.items():
            score = 0
            
            for keyword in config['keywords']:
                if keyword in text_lower:
                    score += text_lower.count(keyword) * 5
            
            for phrase in config['phrases']:
                if phrase in text_lower:
                    score += 10
            
            category_scores[email_type] = score
            
            if score > max_score:
                max_score = score
                detected_type = email_type
        
        if detected_type and max_score > 0:
            category = self.financial_patterns[detected_type]['category']
            priority = self.financial_patterns[detected_type]['priority']
        else:
            productive_indicators = len(re.findall(r'\?|solicit|precis|dúvid|problem|ajud|inform|requer|contato', text_lower))
            unproductive_indicators = len(re.findall(r'olá|oi|bom dia|boa tarde|boa noite|tudo bem|abraço|saudações|oi|prazer|espero que', text_lower))
            
            if productive_indicators > unproductive_indicators:
                category = "Produtivo"
                priority = "media"
                detected_type = "general_produtivo"
            else:
                category = "Improdutivo"
                priority = "baixa"
                if any(k in text_lower for k in self.financial_patterns['greetings']['keywords'] + self.financial_patterns['greetings']['phrases'] + ['oi', 'olá']):
                    detected_type = "greetings"
                elif any(k in text_lower for k in self.financial_patterns['gratitude']['keywords'] + self.financial_patterns['gratitude']['phrases']):
                    detected_type = "gratitude"
                else:
                    detected_type = "irrelevant"
        
        logger.info(f"Classificação: {category} - Tipo: {detected_type} - Prioridade: {priority}")
        
        return category, detected_type, priority, category_scores

    def generate_professional_response(self, category, email_type, priority):
        responses = {
            'status_request': {
                'subject': 'Re: Atualização de Status - Protocolo em Andamento',
                'body': '''Prezado(a) Cliente,
Agradecemos seu contato solicitando atualização sobre o andamento de sua solicitação.
Informamos que sua demanda está sendo processada por nossa equipe técnica especializada. Nossa previsão atual é de conclusão em até 48 horas úteis.
Assim que houver novas atualizações, entraremos em contato imediatamente através dos canais cadastrados.
Para acompanhar o status em tempo real, acesse nossa central do cliente ou entre em contato através do protocolo gerado.
Permanecemos à disposição para esclarecimentos adicionais.
Atenciosamente,
Equipe de Atendimento Especializado'''
            },
            'document_sharing': {
                'subject': 'Re: Documentos Recebidos - Confirmação de Recebimento',
                'body': '''Prezado(a) Cliente,
Confirmamos o recebimento da documentação enviada.
Nossa equipe iniciará a análise dos documentos nas próximas 24 horas úteis. Caso seja necessário algum documento adicional ou esclarecimento, entraremos em contato através dos canais cadastrados.
O prazo estimado para análise completa é de 2 a 3 dias úteis.
Agradecemos pela colaboração e pontualidade no envio das informações solicitadas.
Atenciosamente,
Departamento de Análise Documental'''
            },
            'technical_support': {
                'subject': 'Re: Suporte Técnico - Resolução Prioritária',
                'body': '''Prezado(a) Cliente,
Recebemos sua solicitação de suporte técnico e classificamos como PRIORIDADE ALTA.
Nossa equipe técnica especializada foi notificada e iniciará o diagnóstico imediatamente. 
Ações já tomadas:
• Ticket técnico #TEC-[NÚMERO] foi aberto
• Equipe de TI foi acionada
• Monitoramento ativo iniciado
Previsão de resolução: até 4 horas úteis
Status: EM ANDAMENTO
Você receberá atualizações a cada 2 horas até a completa resolução.
Para urgências, utilize nosso canal prioritário: [TELEFONE-URGENCIA]
Atenciosamente,
Central de Suporte Técnico'''
            },
            'financial_inquiry': {
                'subject': 'Re: Esclarecimentos Financeiros - Informações Solicitadas',
                'body': '''Prezado(a) Cliente,
Recebemos sua consulta sobre questões financeiras relacionadas à sua conta.
Nossas informações financeiras são processadas com máxima segurança e precisão. Para fornecer dados específicos e atualizados sobre sua situação, nossa equipe especializada realizará uma análise detalhada.
Prazo para resposta completa: até 24 horas úteis
Os esclarecimentos serão enviados através de canal seguro para o e-mail cadastrado em sua conta.
Para consultas urgentes, recomendamos acesso ao Internet Banking ou contato através de nossos canais oficiais.
Atenciosamente,
Departamento Financeiro'''
            },
            'case_follow_up': {
                'subject': 'Re: Acompanhamento de Protocolo - Status Atualizado',
                'body': '''Prezado(a) Cliente,
Agradecemos seu contato para acompanhamento do protocolo em questão.
Status atual: EM PROCESSAMENTO
Fila de prioridade: NORMAL
Tempo estimado restante: 24-48h úteis
Nossa equipe especializada está trabalhando na resolução de sua demanda com a máxima atenção aos detalhes e qualidade de serviço.
Você receberá notificação automática assim que houver alteração no status ou quando a solicitação for concluída.
Para consultas sobre este protocolo, sempre mencione o número de referência em futuras comunicações.
Atenciosamente,
Central de Acompanhamento'''
            },
            'greetings': {
                'subject': 'Re: Agradecemos suas Felicitações',
                'body': '''Prezado(a) Cliente,
Agradecemos suas cordiais felicitações!
É muito gratificante receber mensagens como a sua, que demonstram a parceria e confiança em nossos serviços.
Aproveitamos para reafirmar nosso compromisso em continuar oferecendo excelência no atendimento e soluções financeiras que atendam suas expectativas.
Desejamos a você e sua família momentos de muita alegria e prosperidade.
Cordialmente,
Equipe de Relacionamento'''
            },
            'gratitude': {
                'subject': 'Re: Agradecemos seu Feedback',
                'body': '''Prezado(a) Cliente,
Ficamos muito felizes em receber seu agradecimento!
Seu reconhecimento é fundamental para nossa equipe e nos motiva a continuar buscando sempre a excelência em nossos serviços.
É uma satisfação poder atendê-lo(a) e contribuir positivamente para suas necessidades financeiras.
Permanecemos sempre à disposição para futuros atendimentos.
Cordialmente,
Equipe de Atendimento'''
            },
            'irrelevant': {
                'subject': 'Re: Sua Mensagem foi Recebida',
                'body': '''Olá,
Sua mensagem foi recebida. Ficamos à disposição para ajudar com qualquer solicitação futura.
Atenciosamente,
Equipe de Atendimento'''
            },
            'general_produtivo': {
                'subject': 'Re: Sua Mensagem Foi Recebida',
                'body': '''Prezado(a) Cliente,
Agradecemos seu contato conosco.
Sua mensagem foi recebida e será analisada por nossa equipe competente dentro de 24 horas úteis.
Caso sua solicitação seja urgente, recomendamos contato através de nossos canais prioritários ou acesso direto ao Internet Banking.
Retornaremos com uma resposta completa assim que a análise for concluída.
Atenciosamente,
Central de Atendimento'''
            },
            'language_error': {
                'subject': 'Re: Mensagem Recebida',
                'body': '''Prezado(a) Cliente,
Sua mensagem foi recebida.
Por favor, envie sua mensagem em português para que possamos processá-la corretamente.
Atenciosamente,
Equipe de Atendimento'''
            }
        }

        base_response = responses.get(email_type, responses['general_produtivo'])

        if priority == 'alta':
            body = base_response['body'] + '''
⚠️ ATENÇÃO: Esta solicitação foi classificada como ALTA PRIORIDADE e receberá tratamento diferenciado em nossos processos internos.'''
        else:
            body = base_response['body']
        
        return {
            'subject': base_response['subject'],
            'body': body,
            'priority': priority
        }

classifier = FinancialEmailClassifier()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_email():
    try:
        start_time = datetime.now()
        email_text = ""
        
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

        if not email_text or len(email_text.strip()) < 3: # Reduzi para 3 caracteres
            return jsonify({"error": "Texto do email muito curto ou vazio."}), 400
        
        # --- NOVA LÓGICA DE DETECÇÃO DE IDIOMA ---
        is_portuguese = False
        common_portuguese_greetings = ['olá', 'oi', 'bom dia', 'boa tarde', 'boa noite', 'tudo bem']
        
        # Primeira verificação: se o texto for curto, checamos por saudações comuns
        text_lower = email_text.lower()
        if len(email_text.split()) <= 4:
            if any(greeting in text_lower for greeting in common_portuguese_greetings):
                is_portuguese = True
            else:
                try:
                    language = classifier.detect_language(email_text)
                    if language == 'pt':
                        is_portuguese = True
                except:
                    pass # Se a detecção falhar, a variável continua False
        else: # Para textos maiores, confiamos mais no langdetect
            try:
                language = classifier.detect_language(email_text)
                if language == 'pt':
                    is_portuguese = True
            except:
                pass

        if not is_portuguese:
            response_data = classifier.generate_professional_response(category='Improdutivo', email_type='language_error', priority='baixa')
            return jsonify({
                "category": "Improdutivo",
                "email_type": "language_error",
                "priority": "baixa",
                "suggested_response": response_data,
                "processing_time": 0,
                "word_count": len(email_text.split()),
                "classification_details": {"method": "Language Detection", "algorithm": "langdetect", "confidence": "Alta"}
            })

        category, email_type, priority, scores = classifier.classify_email(email_text)
        response_data = classifier.generate_professional_response(category, email_type, priority)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        logger.info(f"Email processado em {processing_time:.2f}s - Categoria: {category} - Tipo: {email_type} - Prioridade: {priority}")

        return jsonify({
            "category": category,
            "email_type": email_type,
            "priority": priority,
            "confidence_scores": scores,
            "suggested_response": {
                "subject": response_data['subject'],
                "body": response_data['body']
            },
            "processing_time": round(processing_time, 2),
            "word_count": len(email_text.split()),
            "classification_details": {
                "method": "NLP Pattern Matching",
                "algorithm": "Financial Domain Specific Rules",
                "confidence": "Alta" if max(scores.values()) > 5 else "Média"
            }
        })

    except Exception as e:
        logger.error(f"Erro no processamento: {e}")
        return jsonify({"error": f"Erro interno: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "OK", 
        "service": "Financial Email Classifier",
        "version": "1.0.0",
        "uptime": "Active"
    })

@app.route('/stats', methods=['GET'])
def get_stats():
    return jsonify({
        "supported_formats": [".txt", ".pdf"],
        "max_file_size": "16MB",
        "categories": ["Produtivo", "Improdutivo"],
        "email_types": list(classifier.financial_patterns.keys()),
        "average_processing_time": "< 1 segundo",
        "nlp_features": ["Stop words removal", "Pattern matching", "Domain-specific classification"]
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)