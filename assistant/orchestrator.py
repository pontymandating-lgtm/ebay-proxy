"""Assistant personnel et business : un orchestrateur qui délègue à des sous-agents.

Deux façons de créer des sous-agents :
- prédéfinis : déclarés dans AGENTS, l'orchestrateur les appelle via l'outil Task ;
- à la volée : l'orchestrateur appelle `spawn_subagent` avec un rôle, des
  instructions et une tâche ; un sous-agent éphémère est lancé et son résultat
  revient à l'orchestrateur.

Lancement : `python orchestrator.py` (variable ANTHROPIC_API_KEY requise).
"""
import asyncio

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
    create_sdk_mcp_server,
    query,
    tool,
)

ORCHESTRATOR_PROMPT = """Tu es l'assistant personnel et business de l'utilisateur.
Pour chaque demande :
1. Décide si tu peux répondre directement ou s'il faut déléguer.
2. Délègue au sous-agent prédéfini le plus adapté (outil Task).
3. Si aucun ne convient, crée un sous-agent à la volée avec spawn_subagent.
4. Synthétise les résultats en français, de façon concise.

Règle absolue : toute action sortante (envoyer un mail, publier une annonce,
engager une dépense, supprimer des données) est d'abord proposée à l'utilisateur
et n'est exécutée qu'après sa validation explicite."""

# Outils qu'un sous-agent à la volée peut recevoir. Volontairement restreint :
# pas de Bash ni d'écriture de fichiers, qui ne doivent pas être délégués sans contrôle.
DYNAMIC_TOOLS_ALLOWED = {"WebSearch", "WebFetch"}

AGENTS = {
    "veille": AgentDefinition(
        description="Recherche d'informations récentes et fiables sur un sujet, avec sources.",
        prompt="Tu fais de la veille. Cherche sur le web, croise les sources et cite-les.",
        tools=["WebSearch", "WebFetch"],
    ),
    "business": AgentDefinition(
        description="Analyse d'activité business : prix, marges, tendances, idées de développement.",
        prompt="Tu analyses l'activité business de l'utilisateur. Raisonne en chiffres, "
               "signale les hypothèses et ce qui manque pour conclure.",
        tools=["WebSearch", "WebFetch"],
    ),
    "redaction": AgentDefinition(
        description="Rédaction de mails, messages, annonces et documents.",
        prompt="Tu rédiges des textes clairs et adaptés au destinataire. Tu proposes "
               "une version, sans jamais l'envoyer toi-même.",
        tools=[],
    ),
}


async def run_agent(prompt: str, system_prompt: str, tools: list[str]) -> str:
    """Lance un sous-agent isolé et renvoie le texte de sa réponse."""
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        allowed_tools=tools,
        max_turns=10,
    )
    parts = []
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            parts.extend(b.text for b in message.content if isinstance(b, TextBlock))
    return "\n".join(parts)


@tool(
    "spawn_subagent",
    "Crée un sous-agent éphémère avec un rôle précis, lui confie une tâche et "
    "renvoie son résultat. Utilise-le quand aucun sous-agent prédéfini ne convient.",
    {"role": str, "instructions": str, "task": str, "tools": list},
)
async def spawn_subagent(args: dict) -> dict:
    tools = [t for t in args.get("tools", []) if t in DYNAMIC_TOOLS_ALLOWED]
    system_prompt = f"Rôle : {args['role']}\n\n{args['instructions']}"
    text = await run_agent(args["task"], system_prompt, tools)
    return {"content": [{"type": "text", "text": text or "(sous-agent sans réponse)"}]}


def build_options() -> ClaudeAgentOptions:
    dynamic_server = create_sdk_mcp_server(name="assistant", tools=[spawn_subagent])
    return ClaudeAgentOptions(
        system_prompt=ORCHESTRATOR_PROMPT,
        agents=AGENTS,
        allowed_tools=["Task", "mcp__assistant__spawn_subagent"],
        mcp_servers={"assistant": dynamic_server},
        max_turns=20,
    )


async def main() -> None:
    print("Assistant prêt. Tape ta demande (Ctrl+C pour quitter).")
    async with ClaudeSDKClient(options=build_options()) as client:
        while True:
            user_input = await asyncio.to_thread(input, "\n> ")
            if not user_input.strip():
                continue
            await client.query(user_input)
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            print(block.text)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        print("\nAu revoir.")
