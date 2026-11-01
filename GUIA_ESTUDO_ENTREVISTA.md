# Guia de estudo e preparação para a entrevista — Artefact

**Data:** 01/11/2026. **Leitura complementar:** [PLANEJAMENTO.md](PLANEJAMENTO.md).

Este guia acompanha uma solução ainda planejada. A leitura dos materiais e a conferência inicial dos dados já foram feitas; o agente, seus testes e suas conversas ainda serão implementados. A direção atual inclui LangChain para modelos/ferramentas, execução local pelo Ollama e um chat web simples sobre API Python. As falas abaixo devem ser adaptadas ao que realmente funcionar na versão entregue.

Você já tem experiência com Python, LLMs e ferramentas. O foco será entender as decisões específicas deste projeto, acompanhar um fluxo no código e sustentar os limites da solução. Não é necessário preparar uma aula sobre todas as tecnologias de agentes.

**Para começar:** leia as seções 1, 4 e 6. Depois da implementação, use a seção 10 para ensaiar e a seção 15 como revisão curta. As outras seções servem de apoio às perguntas de aprofundamento.

## 1. A ideia que você precisa conseguir explicar

O problema da loja é o volume de perguntas repetidas. O protótipo ajuda a responder essas perguntas consultando os materiais da operação. A parte de linguagem entende o pedido e organiza a resposta; a aplicação consulta dados, aplica regras e limita o que pode ser acessado.

Uma explicação curta da proposta:

> “Vou construir um agente em Python com quatro ferramentas e um chat web simples. Para preço, estoque e pedidos, ele consulta dados estruturados. Para regras da loja, recupera trechos do manual. LangChain conecta os modelos e as ferramentas, e a configuração permite começar local pelo Ollama. O backend concentra as regras e também pode ser usado por uma CLI de apoio.”

Depois da implementação, trocar o futuro pelo passado apenas nas partes comprovadas.

## 2. O que cada parte fará

| Parte | Responsabilidade | Exemplo |
| --- | --- | --- |
| Chat web | Receber mensagem e apresentar o atendimento | Histórico, carregamento e fontes |
| API Python | Ligar a página ao mesmo núcleo do agente | Validar uma mensagem recebida por HTTP |
| CLI | Apoiar execução e diagnóstico do núcleo | Testar “quanto custa o Takamine GD20?” pelo terminal |
| Histórico da sessão | Guardar contexto de conversa | Entender que “e no PIX?” se refere ao produto anterior |
| LLM | Interpretar pedido e selecionar ferramenta | Identificar uma pergunta de preço |
| Factory do modelo | Selecionar a integração LangChain pela configuração | Instanciar `ChatOllama` ou `ChatOpenAI` conforme o `.env` |
| Contrato da ferramenta | Definir entradas permitidas | Um ID de produto válido e uma forma de pagamento conhecida |
| Validação local | Rejeitar argumentos inválidos | Orçamento negativo ou limite exagerado |
| Repositório de dados | Executar consultas e filtros | Encontrar o produto e suas promoções |
| Regras de preço | Calcular valores | Aplicar 5% no PIX apenas quando permitido |
| Recuperação de políticas | Encontrar a regra relevante | Seção 6.2 sobre descontos não cumulativos |
| Agente/orquestrador | Conduzir o fluxo entre essas partes | Executar a ferramenta, devolver resultado ao modelo e encerrar |

Na entrevista, uma boa resposta conecta cada parte ao problema que resolve. Se não conseguir justificar um módulo em uma frase, conferir se ele precisa existir separado.

## 3. Conceitos aplicados ao desafio

### 3.1 Function calling

O modelo pode solicitar uma função com argumentos estruturados. A aplicação verifica a solicitação e executa o código permitido. Aqui isso dará acesso controlado ao catálogo, aos pedidos e às políticas.

Um schema ajuda a manter o formato dos argumentos. Ainda assim, regras como “este pedido pertence ao cliente da sessão” precisam ser verificadas pela aplicação. Veja o [protocolo oficial de function calling](https://developers.openai.com/api/docs/guides/function-calling).

No plano atualizado, as ferramentas tipadas são vinculadas ao modelo com `bind_tools`. O loop lê as chamadas de um `AIMessage`, executa somente as funções autorizadas e acrescenta `ToolMessage` com o ID correto. É a parte de LangChain que você deve conseguir seguir no código, conforme as referências de [modelos](https://docs.langchain.com/oss/python/langchain/models) e [mensagens](https://docs.langchain.com/oss/python/langchain/messages).

**O que demonstrar:** onde estão as quatro ferramentas registradas e onde uma chamada inválida deixa de ser executada.

### 3.2 RAG e recuperação de políticas

RAG é uma abordagem em que informações recuperadas de uma fonte ajudam a gerar a resposta. No projeto proposto, a fonte documental é o manual. A implementação começa com busca textual em seções revisadas, sem embeddings.

Por exemplo, “posso devolver?” precisa recuperar condições de devolução, e não apenas um parágrafo que contenha a palavra “produto”. É importante trazer as exceções e preservar a indicação de seção e página.

**O que demonstrar:** uma pergunta, os trechos encontrados e como eles sustentam a resposta. Se o trecho correto não vier, o problema está na recuperação antes de estar na redação.

### 3.3 Dados estruturados e documentos

| Pergunta | Fonte apropriada | Por quê |
| --- | --- | --- |
| “Tem esse violão em estoque?” | Produto por ID, status e quantidade | Exige uma condição objetiva |
| “Quais custam até R$ 1.000?” | Filtro sobre preço final e disponibilidade | Exige comparação numérica |
| “Meu pedido já foi enviado?” | Pedido filtrado pelo cliente da sessão | Exige controle de acesso e status |
| “O PIX acumula com promoção?” | Manual, seção 6.2, e regra de preço | Exige interpretação de política e cálculo |
| “Posso devolver?” | Manual e informações adicionais do cliente | A base de pedidos não contém todos os fatos necessários |

Usar uma única busca de texto para todos esses casos perderia filtros e relações importantes. A proposta combina os dois tipos de consulta conforme a informação necessária.

### 3.4 Determinismo nas regras

O cálculo de um desconto deve produzir o mesmo resultado para as mesmas entradas. O texto da resposta pode variar sem que o preço varie.

No Ohana CK-20, a base fornece R$ 549,00 e promoção ativa de 20%. O resultado calculado é R$ 439,20. O manual não permite acumular mais 5% de PIX nesse preço. Essa verificação será feita em código e em teste, com um exemplo real de conversa.

**O que demonstrar:** o cálculo em `pricing.py` proposto e o teste que evita desconto cumulativo. Não explicar essa garantia apenas como uma instrução no prompt.

### 3.5 Memória de conversa

A memória ajuda a resolver referências como “esse modelo”. Ela não torna o estoque ou o preço lembrado uma informação atualizada. A proposta é lembrar o produto e consultar novamente os fatos necessários.

**Limite planejado:** memória durante uma sessão local. Ao reiniciar a conversa, o contexto é limpo. Não afirmar que o protótipo reconhece o cliente ao voltar em outro dia.

### 3.6 Alucinação, falha e ausência de dados

Uma informação convincente pode estar sem suporte na fonte. Neste desafio, isso pode aparecer como código de rastreio inventado, desconto acumulado, prazo de entrega garantido ou devolução aprovada sem data de recebimento.

A proposta reduz esse risco com ferramentas, regras determinísticas, recuperação de fonte e testes. Ainda será necessário observar as respostas do modelo real. Não existe evidência, nesta preparação, de que o risco foi eliminado.

### 3.7 Modelo local e configuração modular

Llama é o modelo e Ollama é o executor local proposto. A preferência atual é começar local e selecionar a integração LangChain em `llm.py`. O computador já possui Ollama e `qwen3:14b`; o `llama3.1:8b` é o candidato Llama a preparar e validar. Não foram executados testes do agente com nenhum deles.

O `.env` selecionará `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL` e `LLM_API_KEY`. A factory criará `ChatOllama` ou `ChatOpenAI`. No perfil nativo Ollama, a URL será `http://localhost:11434`, sem `/v1`, e não é necessário preencher a chave. Mudar de modelo no mesmo executor normalmente altera `LLM_MODEL`; mudar para a API remota altera também destino e credencial. Reiniciar a aplicação carrega a configuração. Os exemplos completos estão na seção 4.7 do planejamento.

**Como explicar a decisão:**

> “Comecei local para aproveitar o computador disponível. Usei as integrações de modelos do LangChain e uma factory pequena para selecionar o provedor pelo ambiente. As consultas e as regras continuam independentes dessa escolha. Cada modelo precisa passar pelos mesmos cenários de avaliação.”

Usar o passado somente depois da implementação. Não confundir ausência de cobrança por uma API com ausência de custo de hardware, energia ou tempo.

As integrações de [ChatOllama](https://docs.langchain.com/oss/python/integrations/chat/ollama) e [ChatOpenAI](https://docs.langchain.com/oss/python/integrations/chat/openai) permitem usar a interface de modelos LangChain. Parâmetros específicos ficam na factory. As regras de preço e acesso continuam no projeto. A troca não garante a mesma qualidade, os mesmos recursos ou o mesmo tempo de resposta.

**O que demonstrar:** a configuração lida, o modelo efetivamente utilizado e o mesmo teste de preço/acesso funcionando após a troca, se essa segunda combinação tiver sido executada. Não afirmar que a alternativa remota foi validada apenas porque existe um exemplo de `.env`.

### 3.8 O que LangChain resolve e o que o projeto controla

| Responsabilidade | Onde fica na proposta |
| --- | --- |
| Conectar com Ollama ou OpenAI | Integração LangChain selecionada pela factory |
| Representar mensagens e chamadas | Tipos comuns do LangChain |
| Selecionar provedor pelo `.env` | Configuração e factory da aplicação |
| Decidir quais funções podem executar | Registro e validação no loop da aplicação |
| Restringir pedido por cliente | Consulta no backend |
| Calcular desconto e arredondamento | Regra Python testada |
| Separar históricos por conversa | Sessões do backend |
| Comprovar qualidade | Testes, exemplos e relatório de avaliação |

LangChain reduz o trabalho de integração. A modularidade também depende de manter essas responsabilidades separadas no código. O plano utiliza o framework para modelos, mensagens e ferramentas, com loop explícito. Não depende de grafo LangGraph ou servidor MCP.

### 3.9 O caminho da mensagem no chat web

```text
Página HTML/JavaScript → API FastAPI → agente Python
                                      ↓
                           modelo LangChain e ferramentas
                                      ↓
Página com resposta e fontes ← resposta da API
```

A API recebe mensagem e identificador de conversa, mantém o histórico no servidor e chama o núcleo usado pela CLI. O cliente fictício da demonstração é configurado no backend. A página não recebe a chave do provedor nem escolhe um cliente arbitrário para consultar pedidos.

O modo técnico opcional mostra eventos reais e resumidos: ferramenta, status e duração medida. Fontes vêm das consultas executadas. A interface padrão mostra o atendimento; detalhes técnicos ficam na demonstração opcional, sem retornos brutos, dados pessoais ou instruções internas.

O chat terá carregamento e resposta completa em JSON. Streaming de tokens é uma melhoria futura. Duas conversas não devem compartilhar histórico. Os IDs de conversa organizam o protótipo e não representam autenticação de produção.

## 4. Um fluxo de produto, passo a passo

Pergunta planejada para demonstração: **“Quanto custa o Ohana CK-20? E se eu pagar no PIX?”**

1. O chat web envia a mensagem à API, que chama o mesmo núcleo usado pela CLI.
2. O modelo solicita a busca do produto.
3. A aplicação valida os argumentos e consulta o catálogo.
4. A consulta encontra o produto 121, preço de tabela de R$ 549,00, `active`, estoque 6.
5. A aplicação encontra a promoção ativa de 20% e calcula R$ 439,20.
6. Para explicar a regra comercial, o agente consulta a seção de promoções do manual quando necessário.
7. A resposta apresenta preço original, desconto e preço final, sem desconto PIX adicional.
8. Se a pergunta for dividida em dois turnos, o histórico resolve o produto referido e o preço é consultado novamente.

**Explicação para ensaiar após implementar:**

> “A regra de dinheiro fica em Python. O modelo recebe o valor calculado e explica a condição ao cliente. O caso do PIX testa se o agente combina o dado do produto com a restrição do manual.”

**Perguntas que você deve conseguir responder:**

- Onde ocorre o cálculo?
- Qual fonte informa o percentual ativo?
- Qual fonte impede a cumulatividade?
- O que acontece se a promoção ficar inativa após reconstruir a base?
- O filtro de orçamento usa qual preço quando a forma de pagamento não é informada?

## 5. Um fluxo de pedido, passo a passo

Na demonstração local, configurar o cliente fictício 2 e consultar o pedido 8.

1. A identidade é fixada pela configuração de demonstração da aplicação Python, inclusive quando a mensagem vem do navegador.
2. O modelo informa somente `order_id=8` à ferramenta.
3. O código consulta com duas condições: pedido 8 e cliente da sessão 2.
4. A base informa `shipped`, previsão de 28/02/2026 e código de rastreio preenchido.
5. Usando a data de execução, a resposta sinaliza que a previsão registrada já passou, quando for o caso.
6. O agente não afirma que consultou a transportadora nem calcula uma nova chegada sem fonte.

Se a pessoa pedir um pedido de outro cliente, o backend deve devolver uma resposta genérica sem os dados. Instruir o modelo a preservar privacidade ajuda no comportamento, mas o filtro de acesso é a barreira que precisa funcionar.

**Limitação a declarar:** escolher um cliente por uma configuração de demonstração não autentica uma pessoa real. Esse mecanismo permite testar isolamento local; uma aplicação real precisaria de identidade confiável.

## 6. As decisões mais prováveis de serem questionadas

As respostas abaixo são argumentos para a arquitetura proposta. Confirmar que cada decisão foi mantida no projeto final antes de usá-la.

| Pergunta | Resposta a desenvolver |
| --- | --- |
| “Por que uma interface tão simples?” | Uma tela com histórico, fontes e carregamento demonstra o fluxo completo dentro do prazo. API e CLI usam o mesmo núcleo. |
| “Por que manter a CLI?” | Facilita diagnosticar o núcleo e executar o agente independentemente da interface web. |
| “Por que SQLite?” | A base é pequena e relacional. Um arquivo local permite filtros e joins sem administrar um servidor. |
| “Por que não um agente SQL livre?” | Quatro funções atendem às operações necessárias. A aplicação controla as consultas e o acesso aos pedidos. |
| “Por que LangChain?” | A troca de provedores é uma preferência explícita. Integrações e mensagens comuns reduzem código de adaptação; as regras continuam sob controle da aplicação. |
| “Por que não adicionar LangGraph?” | O fluxo cabe em um loop limitado. Um grafo pode ajudar se surgirem ramificações, retomadas ou intervenção humana que justifiquem mais estado. |
| “Por que busca textual em vez de embeddings?” | O manual tem oito páginas. A primeira alternativa é simples de inspecionar; a decisão será avaliada nas perguntas de políticas. |
| “Isso é RAG mesmo sem vetor?” | A resposta usa informação recuperada do manual. Nesta implementação, a recuperação proposta é textual, sem índice vetorial. |
| “Por que esse modelo?” | A preferência é local pelo hardware disponível. Suporte às ferramentas, qualidade e latência precisam ser comprovados nos testes; não dizer que é o melhor sem comparação. |
| “Como troca de modelo?” | O `.env` seleciona modelo, provedor e endereço; `llm.py` instancia a integração LangChain. Reiniciar carrega a mudança. Novas combinações exigem validar compatibilidade. |
| “Por que FastAPI e JavaScript simples?” | O backend permanece em Python e a página demonstra consumo de API. O frontend fica dentro do orçamento de duas horas. |
| “Por que não passar todos os CSVs ao modelo?” | Filtros, cálculos e relações ficam mais controlados na aplicação, e a tabela inteira de clientes não precisa ser exposta. |
| “Você usa todos os arquivos?” | O plano usa as tabelas pelas relações que ajudam catálogo e pedidos; o enunciado permite selecionar dados. Explicar o uso real final de cada uma. |
| “Por que não guardar todo o histórico?” | A continuidade necessária cabe na sessão. Persistência traria retenção de dados e mais trabalho sem requisito definido. |
| “Como sabe que o preço está certo?” | Conferência da origem, cálculo com `Decimal`, testes numéricos e conversa demonstrativa. Mostrar o teste executado. |
| “Como trata políticas conflitantes?” | Registra a divergência, documenta a interpretação e pede confirmação quando a fonte não permite uma resposta segura. |
| “Como funciona em tempo real?” | A consulta ocorre durante a conversa contra a base local importada. Isso não significa atualização em tempo real no sistema da loja. |
| “O que faria com mais tempo?” | Primeiro avaliaria falhas reais de recuperação e atendimento. Para operação real, priorizaria identidade, integração com dados atuais e observabilidade. |

## 7. Os achados dos dados que merecem ser lembrados

Você não precisa decorar todo o catálogo. Vale entender estes casos porque eles explicam decisões concretas:

| Achado | O que ele ensina |
| --- | --- |
| 65 produtos e nove categorias cadastradas | Uma tabela de categorias não garante que haja produto disponível em todas |
| Produto 96 ativo, estoque zero | Status sozinho não indica disponibilidade |
| Produto 136 descontinuado, estoque 13 | Estoque sozinho também não indica disponibilidade |
| Produto 130 `coming_soon`, estoque 2 | É necessário definir a regra de venda do protótipo |
| Quatro promoções ativas, sem datas de validade | O indicador é utilizável no snapshot; datas de campanha não podem ser inferidas |
| Takamine GD20 com promoção inativa | Nome de campanha não autoriza desconto |
| Doze pedidos sem rastreio e sem previsão | Campo vazio é ausência de informação, não valor a completar por imaginação |
| Totais dos pedidos 3 e 20 diferentes dos preços atuais | Dados históricos não devem ser recalculados usando o catálogo atual |
| Sem data de recebimento ou canal de compra nos pedidos | Não é possível concluir elegibilidade de devolução apenas pela tabela |
| Parcelamento e contatos divergentes no manual | Documentar suposições faz parte do trabalho de engenharia |

Os números vêm da conferência registrada no planejamento, não de testes do agente. Se os dados forem alterados para experimentar uma regra, fazer isso em uma fixture ou cópia temporária e preservar os originais.

## 8. Como estudar enquanto implementa

Após cada bloco, abrir o código correspondente e responder em voz alta:

1. Qual problema esta parte resolve?
2. Quais entradas recebe e quais saídas produz?
3. Qual decisão importante está aqui?
4. Qual erro pode acontecer e como é tratado?
5. Que evidência mostra que funciona?

Se uma resposta depender apenas de “a biblioteca faz isso”, investigar o suficiente para explicar o comportamento usado pelo projeto. Não é necessário dominar detalhes internos que a aplicação não utiliza.

### Roteiro de leitura do próprio código

| Ordem | Arquivo proposto | O que procurar |
| --- | --- | --- |
| 1 | `web/app.js`, `api.py` e `__main__.py` | Entrada pela página/API e entrada alternativa pela CLI |
| 2 | `agent.py` e `llm.py` | Loop, mensagens e ferramentas LangChain separados da seleção do provedor |
| 3 | `tools.py` | Ferramentas registradas e validação |
| 4 | `repository.py` | Consulta de produto e filtro de pedido por cliente |
| 5 | `pricing.py` | Promoção, PIX, centavos e conflitos |
| 6 | `policies.py` | Seções recuperadas, sinônimos e fontes |
| 7 | `ingest.py` | Conversão dos arquivos e preservação dos dados |
| 8 | `tests/` | Casos que sustentam as afirmações da apresentação |

Atualizar os caminhos se a organização mudar. O importante é conseguir seguir uma mensagem até a consulta e voltar à resposta.

## 9. Como validar sem depender de uma resposta bonita

Dividir a verificação em três perguntas:

| Pergunta | Evidência necessária |
| --- | --- |
| A consulta ou regra funciona sozinha? | Teste determinístico de preço, filtro, relação ou acesso |
| O agente chamou a ferramenta apropriada? | Registro da execução ou teste controlado de orquestração |
| A resposta respeita o que foi consultado? | Revisão da conversa real e comparação com os dados/trechos |
| A experiência web preserva o comportamento? | Fontes, isolamento de conversa e recuperação de falhas |

Uma resposta correta isolada pode esconder que a ferramenta não foi usada. Uma ferramenta correta pode ser seguida de uma resposta com desconto inventado. Essas verificações complementam uma à outra.

Para recuperação, conferir o trecho antes da resposta. Para pedido, conferir o filtro antes de avaliar a simpatia do texto. Para dinheiro, conferir o valor exato antes da formatação.

Não levar para a entrevista uma taxa de acerto, latência ou custo sem registrar como ela foi medida. Se houver apenas uma bateria pequena, dizer quantos casos foram executados e quais limitações permaneceram.

Consolidar a avaliação em `examples/avaliacao.md`: entrada, ferramenta/regra esperada, resultado observado e passou/falhou. Registrar modelo, provedor e versão do projeto. O relatório complementa as cinco transcrições e deve incluir falhas reais encontradas, quando houver.

## 10. Roteiro de apresentação de 5–7 minutos

| Tempo | Conteúdo | Evidência a mostrar |
| --- | --- | --- |
| 0:00–0:45 | Problema da loja, requisitos e recorte dos dois dias | Resumo no README |
| 0:45–1:30 | Arquitetura, papel do LangChain e regras da aplicação | Diagrama, factory e quatro ferramentas |
| 1:30–3:00 | Demonstração no chat web de produto e PIX em promoção | Conversa real do Ohana, valor, fonte e modo técnico |
| 3:00–4:00 | Demonstração de política com informação faltante | Devolução sem recebimento informado |
| 4:00–5:00 | Caso de dados que motivou uma decisão | Produto ativo sem estoque ou pedido com previsão antiga |
| 5:00–6:00 | Testes, avaliação, instalação e uso de IA | Relatório de casos, README e histórico |
| 6:00–7:00 | Limitações e próximo passo prioritário | Fronteira entre protótipo e operação real |

### Abertura para adaptar depois da execução

> “O protótipo atende perguntas de catálogo, pedidos e políticas usando os materiais fornecidos. O chat web chama uma API Python e quatro ferramentas. Usei LangChain para integrar o modelo local e permitir trocar de provedor pela configuração. Minha principal preocupação foi garantir que preço, estoque e regras viessem de fontes verificáveis, com testes e exemplos de execução.”

Só manter essa fala se as quatro capacidades realmente estiverem funcionando. Se algum ponto tiver sido simplificado, dizer qual e por quê.

### Demonstração principal

Mostrar uma conversa curta no navegador, abrir o modo técnico opcional e depois a regra de preço. Isso explica frontend, API, interpretação, ferramenta, consulta, cálculo e resposta em um exemplo. Se o modo técnico não tiver sido entregue, usar o registro do terminal.

Como segunda conversa, perguntar sobre devolução sem informar o recebimento. Explicar que pedir uma informação necessária é uma resposta adequada quando a base não sustenta uma conclusão.

Levar também os exemplos capturados da versão final. Se o servidor local ou a API falhar ao vivo, apresentar a transcrição identificada como execução anterior e explicar a indisponibilidade atual. Não simular uma execução em tempo real.

## 11. Perguntas de aprofundamento

**“Como você reduziria alucinações?”**

Explicar as fontes, as ferramentas limitadas, as regras de preço e os testes. Em seguida, reconhecer que uma instrução não garante comportamento e que a resposta real precisa de avaliação.

**“Um usuário consegue trocar de cliente pedindo no chat?”**

O identificador autorizado deve vir da aplicação e entrar no filtro do backend. Mostrar onde isso ocorre. Na aplicação, a seleção local é apenas contexto de demonstração, sem autenticação real.

**“Você treinou o modelo nos dados da loja?”**

Na proposta, não há treinamento ou fine-tuning. O sistema consulta o snapshot e recupera o manual durante a execução.

**“O que acontece se o PDF mudar?”**

Reextrair, revisar as seções afetadas, reconstruir o índice e executar os casos de regressão. Não dizer que basta atualizar o arquivo se o projeto não detecta e refaz esse processo automaticamente.

**“E se o cliente escrever ‘violao’ sem acento ou usar outro termo?”**

Explicar a normalização e os sinônimos implementados. Apresentar um teste real. Se a busca falhar em paráfrases, registrar o problema e avaliar uma recuperação mais robusta.

**“O protótipo pode registrar uma reclamação ou cancelar pedido?”**

O escopo planejado é consulta e orientação. Só é correto dizer que uma ação foi realizada se existir uma ferramenta que a execute e um resultado que a confirme.

**“O que LangChain não garante?”**

Ele não garante que o modelo chamará a ferramenta certa, que todo modelo suporta as mesmas opções ou que uma consulta está autorizada. Mostrar as validações no código e os casos do relatório. A factory padroniza a escolha da integração, não elimina a necessidade de testes.

**“O navegador pode escolher qualquer cliente?”**

O contexto de cliente da demonstração fica no servidor. A API recebe mensagem e conversa, sem uma identidade arbitrária enviada pela página. Separar sessões evita misturar históricos, mas a aplicação continua sendo um protótipo local sem autenticação de produção.

**“Como controlou o custo?”**

Apontar o limite do loop, os poucos trechos recuperados, o modelo configurável e os dados efetivamente enviados. Se houver medição de tokens ou custo, mostrar as condições. Sem medição, descrever as medidas de controle sem anunciar economia comprovada.

**“Por que você aceitou algumas ambiguidades?”**

O enunciado orienta assumir interpretações razoáveis e documentá-las. Mostrar um exemplo em que a interpretação foi possível e outro, como o frete de exatamente R$ 500, em que a fonte exige confirmação.

## 12. Como falar sobre o uso de IA

O próprio desafio pede transparência sobre assistentes de código. Até esta etapa, o uso comprovado foi Codex para analisar os materiais, conferir os CSVs e preparar os dois documentos.

Após implementar, completar uma descrição fiel, por exemplo:

> “Usei Codex para [atividades realmente realizadas]. Revisei [partes realmente revisadas] e validei com [testes e execuções realmente feitos]. A escolha de escopo e as limitações estão documentadas. Consigo mostrar como uma mensagem percorre o código até a consulta e a resposta.”

Não decorar esse texto sem preencher as evidências. Uma boa preparação inclui identificar uma sugestão da IA que você modificou, uma decisão que confirmou nos dados e uma limitação que preferiu declarar.

## 13. Registro de decisões e evidências

Preencher durante a implementação. Esta tabela está intencionalmente sem resultados: o projeto ainda não foi executado.

| Etapa | Decisão realmente tomada | Verificação executada e resultado | Evidência/commit | Limitação conhecida |
| --- | --- | --- | --- | --- |
| Dados e importação | A registrar | A executar | A registrar | A registrar |
| Busca de políticas | A registrar | A executar | A registrar | A registrar |
| Preços e disponibilidade | A registrar | A executar | A registrar | A registrar |
| Acesso a pedidos | A registrar | A executar | A registrar | A registrar |
| Agente e modelo | A registrar | A executar | A registrar | A registrar |
| Configuração local/remota | A registrar | A executar | A registrar | A registrar |
| API e chat web | A registrar | A executar | A registrar | A registrar |
| Relatório de avaliação | A registrar | A executar | A registrar | A registrar |
| Histórico da sessão | A registrar | A executar | A registrar | A registrar |
| Falhas e limites | A registrar | A executar | A registrar | A registrar |
| Cinco conversas | A registrar | A executar | A registrar | A registrar |
| Instalação limpa | A registrar | A executar | A registrar | A registrar |

Para um problema encontrado, acrescentar uma anotação curta:

```text
Sintoma observado:
Causa identificada:
Alteração realizada:
Como verifiquei a correção:
O que ainda não resolvi:
```

Esse registro ajuda a explicar o raciocínio de engenharia com um exemplo verdadeiro, além de apresentar a arquitetura final.

## 14. Ensaio de segunda-feira

Reservar duas horas, conforme o planejamento:

1. **30 minutos:** acompanhar no código uma consulta de produto e uma política, sem pular a ferramenta.
2. **20 minutos:** conferir os casos de dados e as ambiguidades que foram realmente tratados.
3. **20 minutos:** apresentar em voz alta o roteiro de 5–7 minutos e identificar pontos confusos.
4. **20 minutos:** responder às perguntas de decisões técnicas com o README fechado.
5. **20 minutos:** repetir as duas demonstrações principais e preparar as transcrições de apoio.
6. **10 minutos:** atualizar este guia para refletir exatamente o que foi entregue.

O objetivo do ensaio é conseguir explicar causa e consequência: qual problema motivou a escolha, como ela aparece no código e que teste ou execução mostra seu efeito.

## 15. Folha de revisão antes da entrevista

- **Problema:** reduzir perguntas repetitivas da equipe de atendimento.
- **Recorte:** protótipo Python com API, chat web simples e CLI de apoio.
- **LangChain:** integrações de modelos, mensagens e ferramentas; loop explícito para controlar a execução.
- **Modelo:** preferência local via ChatOllama; factory seleciona a integração pelo `.env` entre combinações validadas.
- **Ferramentas propostas:** `search_products`, `get_product`, `get_order_status`, `search_policies`.
- **Decisão principal:** fontes estruturadas para fatos operacionais; manual para regras.
- **Caso de dinheiro:** Ohana CK-20, R$ 549,00, 20%, R$ 439,20, sem acumular PIX.
- **Caso de disponibilidade:** produto 96 ativo com estoque zero.
- **Caso de histórico:** valores dos pedidos não são recalculados pelo catálogo atual.
- **Caso de informação ausente:** devolução precisa de dados de recebimento e canal de compra.
- **Limite operacional:** snapshot local, sem consulta real à transportadora.
- **Limite de identidade:** cliente local de demonstração, sem autenticação de produção.
- **Qualidade a comprovar:** regras testadas, ferramentas observadas, sessões separadas e respostas reais revisadas no relatório de avaliação.
- **Uso de IA:** descrição transparente e coerente com o trabalho realizado.
- **Próximo passo:** escolhido por uma limitação observada, sem lista de tecnologias decorativa.

Antes de usar esta folha, corrigir qualquer item que não tenha sido mantido na implementação final.
