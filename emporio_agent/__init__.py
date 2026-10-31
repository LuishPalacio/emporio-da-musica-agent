"""Agente de atendimento da Empório da Música.

Este pacote contém toda a lógica do protótipo: carga dos dados da loja
(emporio_agent.database), as ferramentas que o modelo pode chamar
(emporio_agent.tools), a base de conhecimento de políticas
(emporio_agent.policy), a montagem do prompt de sistema/persona
(emporio_agent.prompts), o laço de orquestração com a API da Anthropic
(emporio_agent.agent), a persistência de conversas (emporio_agent.session)
e a interface de linha de comando (emporio_agent.cli).
"""

__version__ = "0.1.0"
