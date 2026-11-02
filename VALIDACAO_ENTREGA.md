# Verificação da entrega

Verificação realizada em **01/11/2026, às 21h40 (America/Sao_Paulo)**.

Repositório público: [RaFaSMK/artefact-ai-engineer-challenge](https://github.com/RaFaSMK/artefact-ai-engineer-challenge).

## Versão verificada

- Commit clonado para a verificação funcional: `83b3e7baff9462ab35f452995d3febaf8e875522`.
- Python: **3.12.14**, Windows.
- Modelo: **Ollama / qwen3:14b**.
- SHA-256 do núcleo de atendimento: `d58d80c4e0d5c30cf130d6aad52236988aa1657774f32ce8c585111dc09334e8`.

O commit que acrescenta este registro altera apenas documentação. O núcleo verificado é o mesmo identificado no [relatório de avaliação](examples/avaliacao.md).

## Procedimento e resultados

| Etapa | Verificação | Resultado |
| --- | --- | --- |
| Publicação | Repositório acessível, visibilidade `PUBLIC`, branch padrão `main` | Confirmado |
| Histórico | Commits anteriores preservados; novos commits acrescentados sem force-push | Confirmado |
| Clonagem | Nova cópia obtida do endereço público, em diretório separado | Concluída |
| Ambiente | Novo ambiente virtual; instalação do `requirements-lock.txt` e do projeto em modo editável | Concluída |
| Origem do pacote | Importação de `emporio` aponta para o checkout clonado | Confirmado |
| Configuração | `.env` criado a partir do exemplo publicado | Concluída |
| Ingestão | Banco reconstruído a partir dos arquivos clonados | 65 produtos, 20 pedidos, 28 seções; relações validadas |
| Testes | `python -m pytest -q` na clonagem | **64 passaram** |
| Dependências | `python -m pip check` | Nenhuma incompatibilidade encontrada |
| HTTP | Página, JavaScript, saúde, Swagger e esquema OpenAPI | Respostas válidas |
| Identidade | Corpo público da API não permite `customer_id` arbitrário | Confirmado |
| Modelo real | Pergunta sobre Ohana CK-20 e PIX pela API da cópia clonada | Resposta correta com fontes |
| Nova conversa | Exclusão do histórico de teste pela API | HTTP 204 |
| Estado do checkout | Depois da ingestão, dos testes e da chamada real | Árvore Git limpa; artefatos gerados ignorados |

Na consulta real pela clonagem, o assistente informou **R$ 439,20**, com preço original de **R$ 549,00**, desconto de **20%** e ausência de acúmulo com PIX. As fontes identificaram o produto 121, a promoção 14 e a seção 6.2 do manual. A resposta levou aproximadamente **5,9 segundos** nesse ambiente, usando duas chamadas ao modelo.

O serviço Ollama e o modelo já instalados no computador foram reutilizados. Checkout, ambiente Python, configuração e banco foram criados novamente. O Python 3.12 foi invocado pelo executável disponível no ambiente, equivalente ao requisito de versão indicado no README.

## Escopo do polimento

O módulo `responses.py` remove padrões conhecidos de ofertas de ação sem integração e trata expressões de atendimento em inglês observadas nos testes. Os testes preservam preços, negativas e nomes técnicos. As respostas entregues também são usadas no histórico, evitando reintroduzir uma frase removida em uma continuação.

A bateria real de **14 cenários** passou nos critérios definidos. Isso comprova as verificações descritas, sem representar uma medida geral de qualidade ou garantia de ausência de alucinações. Llama e execução remota com OpenAI continuam sem avaliação real.

## Próximas etapas do candidato

- Reproduzir as duas demonstrações principais e acompanhar os caminhos no código.
- Ensaiar a apresentação com o [guia de estudo](GUIA_ESTUDO_ENTREVISTA.md).
- Conferir o horário exato do processo no e-mail e definir a versão final a enviar.
- Enviar o link do repositório e respeitar a regra de não alterar o código após o prazo.
