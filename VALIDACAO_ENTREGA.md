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

## Complemento: execução com Docker em 02/11/2026

A configuração Docker foi acrescentada após a verificação original, sem alterar o código do agente, da API ou da CLI. O registro acima continua identificando a clonagem validada em 01/11. Os resultados abaixo correspondem à construção e execução locais da nova imagem.

Ambiente: Docker Desktop no Windows, engine Linux **29.8.2**, Compose **5.5.1**, imagem `python:3.12-slim` resolvida para Python **3.12.16** em Linux/amd64. O Ollama e o `qwen3:14b` já instalados no host foram reutilizados por `http://host.docker.internal:11434`. Não foi necessário alterar o endereço de escuta do Ollama neste computador.

| Etapa | Resultado observado |
| --- | --- |
| `docker compose config --quiet` | Configuração aceita |
| `docker compose build` | Imagem construída com as dependências travadas |
| `docker build --target test -t emporio-test .` e `docker run --rm emporio-test` | **64 testes passaram dentro do contêiner**, em aproximadamente 4 segundos |
| `docker compose up -d --wait` | Aplicação iniciou, importou automaticamente a base e ficou saudável |
| Privilégios e conteúdo da imagem | UID 10001; `.env` e diretório de testes ausentes da imagem de execução |
| `python -m pip check` no contêiner | Nenhuma incompatibilidade encontrada |
| Acesso ao Ollama pelo contêiner | `/api/tags` retornou HTTP 200 |
| Acesso pelo host | Página, saúde, JavaScript, Swagger, OpenAPI e manual retornaram HTTP 200 |
| Publicação de porta | `127.0.0.1:8765` encaminhada à porta 8765 do contêiner |
| Consulta real pela API | Ohana CK-20 no PIX: R$ 439,20, original R$ 549,00, desconto de 20%, sem acúmulo de PIX |
| Fontes e execução | Produto 121, promoção 14 e seção 6.2; duas chamadas ao modelo, aproximadamente 19,9 segundos nessa execução |
| Exclusão da conversa de teste | HTTP 204 |

O registro auxiliar dessa chamada fica em `runtime/docker-validation.json`, ignorado no Git. A duração é uma medição isolada, não um benchmark comparativo. A bateria real de 14 cenários não foi repetida: o núcleo do agente não mudou, e o teste adicional verificou o caminho contêiner → Ollama e a resposta pela API.

A execução com Docker foi verificada neste computador com Docker Desktop e contêineres Linux. Linux com Docker Engine, macOS, aceleração de GPU dentro de um contêiner e inferência remota continuam sem verificação própria. O healthcheck confirma inicialização da API/base, sem inferência. Não há volume persistente, e o banco derivado é reconstruído quando o contêiner é recriado. O `.env` local foi ajustado para o endereço do host acessível pelo Docker; a execução Python direta requer restaurar o endereço local indicado no README.
