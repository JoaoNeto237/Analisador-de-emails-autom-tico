document.addEventListener('DOMContentLoaded', () => {
    // Elementos DOM
    const tabs = document.querySelectorAll('.tab');
    const tabContents = document.querySelectorAll('.tab-content');
    const form = document.getElementById('email-form');
    const analyzeButton = document.getElementById('analyze-button');
    const resultsSection = document.getElementById('results');
    const emailTextarea = document.getElementById('email-text');
    const charCount = document.getElementById('char-count');
    const fileInput = document.getElementById('file-input');
    const fileInfo = document.getElementById('file-info');
    const fileName = document.getElementById('file-name');
    const removeFileBtn = document.getElementById('remove-file');
    const copyBtn = document.getElementById('copy-response');

    // Alternância entre abas
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            tab.classList.add('active');
            document.getElementById(tab.dataset.tab).classList.add('active');
            
            // Limpar conteúdo ao trocar de aba
            if (tab.dataset.tab === 'text-direct') {
                clearFileSelection();
            } else {
                emailTextarea.value = '';
                updateCharCount();
            }
        });
    });

    // Contador de caracteres
    if (emailTextarea && charCount) {
        emailTextarea.addEventListener('input', updateCharCount);
        
        function updateCharCount() {
            const count = emailTextarea.value.length;
            charCount.textContent = count.toLocaleString();
            
            // Mudança de cor baseada no tamanho
            if (count > 5000) {
                charCount.style.color = '#e74c3c';
            } else if (count > 2000) {
                charCount.style.color = '#f39c12';
            } else {
                charCount.style.color = '#27ae60';
            }
        }
        
        updateCharCount(); // Inicializar
    }

    // Gerenciamento de arquivo
    if (fileInput) {
        fileInput.addEventListener('change', handleFileSelection);
    }

    if (removeFileBtn) {
        removeFileBtn.addEventListener('click', clearFileSelection);
    }

    function handleFileSelection(e) {
        const file = e.target.files[0];
        if (file) {
            showFileInfo(file);
        }
    }

    function showFileInfo(file) {
        if (fileName && fileInfo) {
            fileName.textContent = `${file.name} (${formatFileSize(file.size)})`;
            fileInfo.style.display = 'flex';
            
            // Esconder área de drop
            const dropArea = document.getElementById('drop-area');
            if (dropArea) {
                dropArea.style.display = 'none';
            }
        }
    }

    function clearFileSelection() {
        if (fileInput) {
            fileInput.value = '';
        }
        if (fileInfo) {
            fileInfo.style.display = 'none';
        }
        
        // Mostrar área de drop
        const dropArea = document.getElementById('drop-area');
        if (dropArea) {
            dropArea.style.display = 'block';
        }
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Envio do formulário
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        try {
            await analyzeEmail();
        } catch (error) {
            showError(`Erro na análise: ${error.message}`);
            console.error('Erro:', error);
        }
    });

    async function analyzeEmail() {
        // Validar entrada
        if (!validateInput()) return;

        // Configurar UI para loading
        setLoadingState(true);
        hideResults();

        const formData = new FormData(form);
        let requestBody = formData;
        let headers = {};
        
        // Preparar requisição baseada na aba ativa
        const isTextDirect = document.querySelector('.tab[data-tab="text-direct"]').classList.contains('active');
        
        if (isTextDirect) {
            const emailText = emailTextarea.value.trim();
            requestBody = JSON.stringify({ email_text: emailText });
            headers['Content-Type'] = 'application/json';
        }

        try {
            const response = await fetch('/analyze', {
                method: 'POST',
                body: requestBody,
                headers: headers
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `Erro ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            displayResults(data);
            
        } catch (error) {
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                showError('Erro de conexão. Verifique sua internet e tente novamente.');
            } else {
                showError(error.message);
            }
            throw error;
        } finally {
            setLoadingState(false);
        }
    }

    function validateInput() {
        const isTextDirect = document.querySelector('.tab[data-tab="text-direct"]').classList.contains('active');
        
        if (isTextDirect) {
            const text = emailTextarea.value.trim();
            if (text.length < 3) {
                showError('Por favor, digite pelo menos 3 caracteres no email.');
                emailTextarea.focus();
                return false;
            }
            if (text.length > 10000) {
                showError('Texto muito longo. Máximo de 10.000 caracteres.');
                return false;
            }
        } else {
            if (!fileInput.files.length) {
                showError('Por favor, selecione um arquivo.');
                return false;
            }
            
            const file = fileInput.files[0];
            const maxSize = 16 * 1024 * 1024; // 16MB
            
            if (file.size > maxSize) {
                showError('Arquivo muito grande. Máximo de 16MB.');
                return false;
            }
            
            const allowedTypes = ['.txt', '.pdf'];
            const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
            
            if (!allowedTypes.includes(fileExtension)) {
                showError('Formato de arquivo não suportado. Use .txt ou .pdf');
                return false;
            }
        }
        
        return true;
    }

    function setLoadingState(isLoading) {
        analyzeButton.disabled = isLoading;
        
        const btnText = analyzeButton.querySelector('.btn-text');
        const btnLoading = analyzeButton.querySelector('.btn-loading');
        
        if (btnText && btnLoading) {
            btnText.style.display = isLoading ? 'none' : 'inline-flex';
            btnLoading.style.display = isLoading ? 'inline-flex' : 'none';
        }
    }

    function displayResults(data) {
        // Atualizar elementos dos resultados
        updateElement('category', data.category);
        updateElement('email_type', data.email_type);
        updateElement('processing_time', `${data.processing_time}s`);
        updateElement('word_count', data.word_count);
        updateElement('confidence', data.confidence || 'Média');
        
        // Atualizar badge de categoria
        const categoryBadge = document.getElementById('category-badge');
        if (categoryBadge) {
            categoryBadge.className = `category-badge ${data.category.toLowerCase()}`;
        }
        
        // Atualizar badge de prioridade
        const priorityElement = document.getElementById('priority-badge');
        if (priorityElement) {
            priorityElement.textContent = data.priority;
            priorityElement.className = `priority-${data.priority.toLowerCase()}`;
        }
        
        // Atualizar resposta sugerida
        updateElement('response_subject', data.suggested_response.subject);
        updateElement('response_body', data.suggested_response.body);
        
        // Mostrar seção de resultados com animação
        showResults();
        
        // Log para debug
        console.log('Resultados recebidos:', data);
    }

    function updateElement(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    }

    function showResults() {
        resultsSection.style.display = 'block';
        resultsSection.scrollIntoView({ 
            behavior: 'smooth', 
            block: 'start' 
        });
        
        // Animação de entrada
        resultsSection.style.opacity = '0';
        resultsSection.style.transform = 'translateY(20px)';
        
        requestAnimationFrame(() => {
            resultsSection.style.transition = 'all 0.5s ease';
            resultsSection.style.opacity = '1';
            resultsSection.style.transform = 'translateY(0)';
        });
    }

    function hideResults() {
        if (resultsSection) {
            resultsSection.style.display = 'none';
        }
    }

    function showError(message) {
        // Criar ou atualizar elemento de erro
        let errorElement = document.getElementById('error-message');
        
        if (!errorElement) {
            errorElement = document.createElement('div');
            errorElement.id = 'error-message';
            errorElement.style.cssText = `
                background: linear-gradient(135deg, #ff6b6b 0%, #ee5a52 100%);
                color: white;
                padding: 15px 20px;
                border-radius: 10px;
                margin: 15px 0;
                display: flex;
                align-items: center;
                gap: 10px;
                box-shadow: 0 4px 15px rgba(255, 107, 107, 0.3);
                animation: slideDown 0.3s ease;
            `;
            form.appendChild(errorElement);
        }
        
        errorElement.innerHTML = `
            <i class="fas fa-exclamation-triangle"></i>
            <span>${message}</span>
            <button onclick="this.parentElement.remove()" style="
                background: none;
                border: none;
                color: white;
                font-size: 1.2rem;
                cursor: pointer;
                margin-left: auto;
            ">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        // Auto-remover após 5 segundos
        setTimeout(() => {
            if (errorElement && errorElement.parentNode) {
                errorElement.remove();
            }
        }, 5000);
    }

    // Funcionalidade de copiar resposta
    if (copyBtn) {
        copyBtn.addEventListener('click', async () => {
            try {
                const subject = document.getElementById('response_subject').textContent;
                const body = document.getElementById('response_body').textContent;
                const fullResponse = `Assunto: ${subject}\n\n${body}`;
                
                await navigator.clipboard.writeText(fullResponse);
                
                // Feedback visual
                const originalIcon = copyBtn.innerHTML;
                copyBtn.innerHTML = '<i class="fas fa-check"></i>';
                copyBtn.style.background = 'rgba(40, 167, 69, 0.3)';
                
                setTimeout(() => {
                    copyBtn.innerHTML = originalIcon;
                    copyBtn.style.background = 'rgba(255, 255, 255, 0.2)';
                }, 2000);
                
            } catch (err) {
                console.error('Erro ao copiar:', err);
                showError('Erro ao copiar para a área de transferência');
            }
        });
    }

    // Atalhos de teclado
    document.addEventListener('keydown', (e) => {
      
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            if (!analyzeButton.disabled) {
                form.dispatchEvent(new Event('submit'));
            }
        }
        
        if (e.key === 'Escape') {
            hideResults();
            const errorElement = document.getElementById('error-message');
            if (errorElement) {
                errorElement.remove();
            }
        }
    });

    // Validação em tempo real para textarea
    if (emailTextarea) {
        emailTextarea.addEventListener('input', (e) => {
            const text = e.target.value;
            const isValid = text.length >= 3 && text.length <= 10000;
            
            // Atualizar estilo baseado na validação
            if (text.length > 0) {
                if (isValid) {
                    emailTextarea.style.borderColor = '#28a745';
                } else {
                    emailTextarea.style.borderColor = '#dc3545';
                }
            } else {
                emailTextarea.style.borderColor = '#e9ecef';
            }
        });
    }

    // Animação CSS para erros
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideDown {
            from {
                opacity: 0;
                transform: translateY(-10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .result-card {
            animation: fadeInUp 0.6s ease forwards;
        }
        
        .result-card:nth-child(2) {
            animation-delay: 0.1s;
        }
        
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
    `;
    document.head.appendChild(style);

    // Inicialização
    console.log('Sistema de classificação de emails inicializado com sucesso!');
    
    // Verificar se há exemplos na URL
    const urlParams = new URLSearchParams(window.location.search);
    const exemplo = urlParams.get('exemplo');
    
    if (exemplo && emailTextarea) {
        const exemplos = {
            'status': 'Olá, gostaria de saber o status da minha solicitação de protocolo #12345. Já faz uma semana desde que enviei os documentos e não recebi nenhuma atualização. Podem me informar quando terei uma resposta? Obrigado.',
            'suporte': 'Bom dia, estou com problema para acessar o sistema. Aparece erro de login e não consigo entrar na minha conta. Podem me ajudar a resolver esse problema técnico?',
            'natal': 'Feliz Natal para toda a equipe! Desejo um ano novo cheio de prosperidade e sucesso para todos. Obrigado pelo excelente atendimento durante todo o ano.',
            'agradecimento': 'Muito obrigado pela atenção e pelo excelente atendimento recebido. Vocês são uma equipe fantástica e estou muito satisfeito com o serviço.'
        };
        
        if (exemplos[exemplo]) {
            // Mudar para aba de texto direto
            document.querySelector('.tab[data-tab="text-direct"]').click();
            emailTextarea.value = exemplos[exemplo];
            updateCharCount();
        }
    }
});