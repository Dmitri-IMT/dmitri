# FastAPI

FastAPI é um framework web moderno para construção de APIs em Python, oferecendo facilidade de desenvolvimento, alta performance  e documentação com OpenAPI automatizada. A ferramenta fará parte de camada de backend da nossa aplicação, expondo endpoints que poderão ser consumidos pelo frontend e outros serviços. 

Um grande incentivo para utilizar a ferramenta é que ao desenvolver funções tipadas (como str, int, etc) o FastAPI irá validar o input, converter dados, e gerar a documentação de OpenAPI automaticamente, isso significa menos boilerplate e menos erros entre o que o frontend manda e o que o backend espera receber.

Como funciona:

Ao definir uma aplicação, será criado endpoints com "decoradores" como @app.get() ou @app.post(), e cada endpoint se torna uma rota HTTP que o frontend pode chamar. Quando um request chega, o FastAPI lê parametros do path, string, headers, arquivos, forms ou JSON do query, valida com a tipagem estabelecida no código, e retorna um output estruturado no formato JSON.

Se uma rota também usar libraries assíncronas, é possível declarar um async def e usar await, porém se utilizar código comum, é possível manter o esperado “def” do Python, e o framework vai rodar a operação da rota em um threadpool em vez de bloquear o loop do servidor diretamente. FastAPI também aceita WebSockets, que pode ser útil caso queiramos atualização on-time de informações no frontend.

Nosso scanner coleta dados de scripts que ferramentas de pentest, correlaciona os resultados com CVEs e algoritmos pré-programados, e publica esses dados em uma página web, o FastAPI é ótimo nesse caso por conta de sua arquitetura API-first, que pode expor endpoints REST e fazer updates na página em tempo real. 

## Comparação com Flask e Django

| Dimensão | Flask (WSGI) | FastAPI (ASGI) | Django REST Framework |
| --- | --- | --- | --- |
| Arquitetura central | Ciclo de requisição síncrono em WSGI  | Pilha ASGI assíncrona e não bloqueante | Baseado no ecossistema Django, tradicionalmente mais síncrono, com suporte assíncrono mais limitado no DRF github+1 |
| Requisições por segundo (simples) | Aproximadamente 2.000–3.000 rps | Aproximadamente 15.000–20.000 rps | Varia bastante conforme serializers, ORM, middlewares e desenho da aplicação  |
| Suporte assíncrono nativo | Limitado, com soluções menos naturais  | `async/await` como recurso de primeira classe | Parcial, ainda menos direto que no FastAPI |
| Validação de dados | Manual, normalmente com bibliotecas externas | Automática com Pydantic | Automática via serializers, mas geralmente mais verbosa  |
| Documentação pronta | Não vem pronta por padrão | Swagger e ReDoc gerados automaticamente | API navegável embutida e suporte a schema/documentação via ferramentas do DRF  |
| Maturidade do ecossistema | Muito maduro, com grande quantidade de extensões | Mais novo, mas em rápida expansão | Muito maduro, apoiado no ecossistema amplo do Django  |
| Curva de aprendizado | Mais suave para quem conhece Python síncrono | Um pouco mais íngreme, por causa de tipagem e async | Moderada a mais alta, por trazer mais convenções e estrutura  |

O maior impeditivo de utilizar frameworks como Django e Flask, é a falta de conhecimento do time diante dessas ferramentas. Diferentemente do FastAPI, que gera documentos OpenAPI e faz tipagem de dados automaticamente, os outros frameworks demandam bibliotecas externas e/ou código próprio. Nos baseando na facilidade de uso, tanto como na qualidade técnica da ferramenta, optaremos pelo FastAPI.

## Referências

BRATSLAVSKY, P. **FastAPI vs Flask 2025: Performance, Speed & When to Choose**. Disponível em: <https://strapi.io/blog/fastapi-vs-flask-python-framework-comparison>. Acesso em: 12 mar. 2026. 

CHRISTIE, T. **Django REST Framework**. Disponível em: <https://www.django-rest-framework.org/>. Acesso em: 12 mar. 2026. 

FASTAPI; RAMIREZ, S. **FastAPI**. Disponível em: <https://fastapi.tiangolo.com/>. Acesso em: 12 mar. 2026.