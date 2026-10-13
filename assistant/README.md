# Assistant personnel et business

Un agent **orchestrateur** qui reçoit tes demandes et délègue à des **sous-agents**.

## Fonctionnement

- **Sous-agents prédéfinis** (`AGENTS` dans `orchestrator.py`) : `veille`, `business`, `redaction`. L'orchestrateur les appelle via l'outil `Task`.
- **Sous-agents à la volée** : l'orchestrateur peut appeler `spawn_subagent` avec un rôle, des instructions, une tâche et une liste d'outils. Seuls `WebSearch` et `WebFetch` sont autorisés pour ces agents.
- **Garde-fou** : aucune action sortante (mail, publication, dépense, suppression) n'est exécutée sans ta validation.

## Lancer

```bash
cd assistant
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...   # ta clé API
python orchestrator.py
```

## À faire ensuite

- Brancher tes outils réels : agenda, mails, comptes business. Ils s'ajoutent comme serveurs MCP.
- Ajouter une mémoire persistante (fichier ou SQLite) entre les sessions.
- Ajouter une interface (bot Telegram, page web) pour lui parler depuis ton téléphone.
