# SKILLS.md — `meal-planner-agent/`

Recettes paramétriques pour les tâches récurrentes sur l'agent `meal-planner-agent`.
Pour les tâches cross-repo, voir `../SKILLS.md` à la racine du workspace.

Format : chaque skill est identifiée `SK-MPA##` (MPA = Meal Planner Agent).

---

## SK-MPA01 — Ajouter un tool MCP exposé par l'agent

**Contexte :** exposer une nouvelle capacité de l'agent (suggestion sur un horizon plus long, scoring custom, etc.).

### Étapes

1. `adapters/input/fastmcp/tools/<sujet>_tools.py` — ajouter la méthode `@mcp.tool()` avec une **docstring orientée agent** (le LLM consommateur la lit pour décider).

2. Si le tool nécessite un nouveau schéma I/O, le définir dans `adapters/input/schemas/`.

3. Vérifier l'enregistrement dans `adapters/input/fastmcp/register.py` → `register_tools()`.

4. Câbler le service applicatif si la logique métier n'est pas triviale (ne pas mettre la logique dans le tool MCP).

5. Test : `tests/units/adapters/input/fastmcp/test_<sujet>_tools.py`.

### Validation

```bash
make test-unit
uv run python main_mcp_http.py
# Inspecter les tools (cf. ../recipe/SKILLS.md SK-R07).
```

---

## SK-MPA02 — Étendre le contrat MCP avec `recipe/` ou `meal-planner/`

**Contexte :** appeler un nouveau tool MCP exposé par un backend.

### Étapes

1. Vérifier que le tool existe côté backend (`../recipe/SKILLS.md` SK-R07 pour l'inspection).

2. Identifier le client MCP côté agent — typiquement dans `adapters/output/` ou `infrastructure/`. Ajouter une méthode publique qui encapsule l'appel `_call("<tool_name>", {...})`.

3. Le **nom du tool** doit correspondre **exactement** à celui exposé côté backend.

4. Test : `tests/units/adapters/output/...` avec un faux serveur MCP ou un mock.

### Validation

```bash
./start_services.sh up recipe meal-planner meal-planner-agent
uv run python main_cli.py "<prompt qui exerce le nouveau tool>"
```

Vérifier le `AgentRun` produit (status `success`, métadonnées attendues).

---

## SK-MPA03 — Changer le modèle LLM (cloud / local)

**Contexte :** basculer entre Anthropic, OpenAI, et un LLM local (LM Studio / Ollama).

### Étapes

1. Éditer `config.yaml`, section `lm` :

   ```yaml
   lm:
     planner:
       provider: anthropic              # anthropic | openai
       model_name: claude-haiku-4-5-20251001
       api_key: ${ANTHROPIC_API_KEY}    # fallback ; valeur cible via Vault
       # Pour un LLM local :
       # provider: openai
       # base_url: http://127.0.0.1:1234/v1
       # api_key: lm-studio
   ```

2. Pour un LLM local : vérifier que le serveur tourne (`curl http://127.0.0.1:1234/v1/models`).

3. Pour Anthropic : valeur du token via Vault (cf. `docs/vault.md`).

### Validation

```bash
uv run python main_cli.py "<prompt simple>"
```

Vérifier la durée et le contenu du `AgentRun` ; le modèle utilisé doit apparaître dans les métadonnées.

---

## SK-MPA04 — Ajuster la stratégie de scoring / filtrage des candidats

**Contexte :** l'agent propose trop / pas assez certains types de recettes ; ajuster la logique de pré-sélection ou de scoring.

### Étapes

1. Identifier le composant de scoring dans `application/services/` ou `domain/models/planner_agent.py` (logique pure et testable).

2. Si la modification change le **comportement attendu** (ex. exclure les recettes trop récentes), la documenter dans une entrée journal explicite.

3. Tests : ajouter des cas qui couvrent la nouvelle règle, en particulier les cas limites (zéro candidat, candidats égaux, exclusions multiples).

### Validation

```bash
make test-unit
make coverage
uv run python main_cli.py "<prompt>"
```

---

## SK-MPA05 — Consulter et trier les `AgentRun`

**Contexte :** diagnostiquer un échec ou comprendre une suggestion passée.

### Via REST

```bash
curl -fsS http://127.0.0.1:8016/agent-runs | jq '.[0:5]'
curl -fsS http://127.0.0.1:8016/agent-runs/<uuid> | jq
```

### Via MongoDB

```javascript
db["agent_runs"].find({ status: "failed" }).sort({ created_at: -1 }).limit(10)
db["agent_runs"].find({ "metadata.elapsed_ms": { $gt: 5000 } })
```

### Champs utiles

| Champ | Contenu |
|---|---|
| `status` | `pending`, `running`, `success`, `failed`, `cancelled` |
| `raw_input` | Texte / contexte soumis à l'agent |
| `output` | Résultat (ex. liste de `SuggestionResult`) |
| `error` | Message d'erreur si `status=failed` |
| `metadata.elapsed_ms` | Durée d'exécution |
| `metadata.model` | Modèle LLM utilisé |
| `metadata.tokens_*` | Si disponibles selon le provider |

---

## SK-MPA06 — Diagnostiquer un agent qui échoue

**Contexte :** `AgentRun` en `status=failed` ou suggestions vides.

### Étapes

1. Lire `error` et la stack si présente.

2. Vérifier que les services consommés répondent en MCP :

   ```bash
   ./start_services.sh status
   curl -fsS http://127.0.0.1:8001/mcp        # recipe MCP
   curl -fsS http://127.0.0.1:8011/mcp        # meal-planner MCP
   ```

3. Vérifier la config LLM : token, base_url, modèle existant côté provider.

4. Si timeout : augmenter le timeout dans `config.yaml` ou réduire la taille du prompt.

5. Si parsing structuré échoue : vérifier que les schémas pydantic-ai n'ont pas changé et que le LLM choisi sait produire du structured output.

### Validation

Un nouveau `AgentRun` en `status=success`.

---

## SK-MPA07 — Restaurer ou exporter la base MongoDB locale

**Contexte :** repartir d'un état connu pour les `AgentRun`.

Voir `../SKILLS.md` SK-W03. Base par défaut : `meal-planner-agent` (cf. `config/adapters/output/mongodb.yaml`).
