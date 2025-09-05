document.addEventListener('DOMContentLoaded', () => {
    const tabs = document.querySelectorAll('.tab');
    const tabContents = document.querySelectorAll('.tab-content');
    const form = document.getElementById('email-form');
    const analyzeButton = document.getElementById('analyze-button');
    const loadingIndicator = document.getElementById('loading-indicator');
    const resultsSection = document.getElementById('results');
    
    // Lógica para alternar entre as abas
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));
            
            tab.classList.add('active');
            document.getElementById(tab.dataset.tab).classList.add('active');
        });
    });

    // Lógica de envio do formulário
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Esconder resultados antigos
        resultsSection.style.display = 'none';
        
        // Mostrar indicador de carregamento e desabilitar o botão
        loadingIndicator.style.display = 'block';
        analyzeButton.disabled = true;

        const formData = new FormData(form);
        let requestBody = formData;
        
        // Se a aba de texto direto estiver ativa, prepare o JSON
        const isTextDirect = document.querySelector('.tab[data-tab="text-direct"]').classList.contains('active');
        if (isTextDirect) {
            const emailText = document.getElementById('email-text').value;
            if (!emailText.trim()) {
                alert('Por favor, digite o conteúdo do e-mail.');
                loadingIndicator.style.display = 'none';
                analyzeButton.disabled = false;
                return;
            }
            requestBody = JSON.stringify({ email_text: emailText });
        }

        try {
            const response = await fetch('/analyze', {
                method: 'POST',
                body: requestBody,
                headers: isTextDirect ? { 'Content-Type': 'application/json' } : {}
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Erro desconhecido ao processar e-mail.');
            }

            const data = await response.json();
            
            // Atualizar os resultados na interface
            document.getElementById('category').textContent = data.category;
            document.getElementById('email_type').textContent = data.email_type;
            document.getElementById('priority').textContent = data.priority;
            document.getElementById('processing_time').textContent = `${data.processing_time}s`;
            document.getElementById('response_subject').textContent = data.suggested_response.subject;
            document.getElementById('response_body').textContent = data.suggested_response.body;
            
            resultsSection.style.display = 'block';

        } catch (error) {
            alert(`Erro na análise: ${error.message}`);
            console.error(error);
        } finally {
            // Esconder indicador de carregamento e reabilitar botão
            loadingIndicator.style.display = 'none';
            analyzeButton.disabled = false;
        }
    });
});