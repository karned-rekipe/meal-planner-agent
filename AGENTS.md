# AGENTS.md — `meal-planner-agent/`

Document d'entrée pour tout agent de codage qui intervient sur ce repo.
Lecture obligatoire avant toute modification.

Pour le contexte global du projet et les conventions transverses, voir `../AGENTS.md` à la racine du workspace.

---

## 1. Rôle

`meal-planner-agent/` est l'**agent IA** du domaine planification. Il transforme une demande (langage naturel ou contexte structuré) en suggestions de recettes pour des slots de repas. Il **ne possède aucune entité métier propre** — il délègue toute persistance des plans à `meal-planner/` via MCP.

Responsabilités :

- composer un contexte de suggestion (`SuggestionContext`) à partir des préférences du tenant et des recettes éligibles ;
- appeler un LLM pour produire des `SuggestionResult` argumentés (score + raisons) ;
- exposer le résultat via REST, MCP, et CLI ;
- persister un `AgentRun` (traçabilité de chaque exécution).

## 2. Stack et ports

| Élément | Valeur |
|---|---|
| Langage | Python 3.13 |
| Gestionnaire deps | `uv` |
| Framework de base | `arclith` |
| LLM | pydantic-ai (Anthropic / OpenAI / local via base_url) |
| Web | FastAPI |
| MCP | FastMCP |
| Stockage `AgentRun` | MongoDB (port `5971` en local) ; `memory` / `duckdb` pour les tests |
| API REST | `8016` |
| MCP HTTP | `8014` |
| Sources MCP consommées | `recipe/` (MCP `8001`) et `meal-planner/` (MCP `8011`) |

**Ne jamais changer ces ports** sans mettre à jour `start_services.sh` et `gwel/vite.config.ts`.

## 3. Architecture locale

Architecture hexagonale (mêmes principes que `agent-recipe-creator/`) :

```
domain/
  models/
    agent_run.py             # AgentRun — entité de traçabilité
    planner_agent.py         # CandidateRecipe, SuggestionContext, SuggestionResult (dataclasses immuables)
  ports/
    output/
      agent_run_repository.py

application/                 # Services + use cases (orchestration de la suggestion)

adapters/
  input/
    fastapi/                 # REST :8016 — agent_run_router, planner_agent_router, admin
    fastmcp/                 # MCP :8014 — tools, prompts, resources
    schemas/                 # Schémas pydantic in/out
  output/
    mongodb/repositories/    # AgentRunRepository prod
    memory/repositories/     # AgentRunRepository tests
    duckdb/repositories/

infrastructure/              # DI, logging
config/                      # YAML : LLM, MCP clients (recipe + meal-planner), DB
tests/units/

main.py                      # Entry point unique (MODE env var)
main_api.py                  # Lancement REST seul (utilise main.app)
main_mcp_http.py             # Lancement MCP HTTP seul
main_mcp_sse.py              # Lancement MCP SSE seul
main_mcp_stdio.py            # Lancement MCP stdio (pour intégration locale type Claude Desktop)
main_cli.py                  # CLI (pratique pour tester sans frontend)
```

### Modes de lancement

Comme les backends, `main.py` accepte la variable `MODE` (`api`, `mcp_http`, `mcp_sse`, `all`). Les `main_*.py` sont des points d'entrée dédiés à un mode spécifique.

## 4. Règles de développement

### Règles transverses (rappel — voir `../AGENTS.md` §4)

- Architecture hexagonale stricte. `domain/` ne dépend que de `arclith` + `pydantic`. Pas de framework HTTP, pas de client LLM dans `domain/`.
- Toute interaction avec un autre service Rekipe passe par **MCP** (jamais d'appel HTTP direct).
- L'agent **ne persiste rien d'autre que `AgentRun`**. Les plans, slots et suggestions retenues sont écrits dans `meal-planner/` via MCP.

### Règles spécifiques à ce repo

- **Toute exécution = un `AgentRun`** : status (`pending` → `running` → `success` / `failed` / `cancelled`), input brut, output, métadonnées (durée, modèle, tokens). Sert de pierre Rosetta pour debug.
- **LLM configurable via `config.yaml`** (provider Anthropic / OpenAI / local). Ne jamais hardcoder un modèle dans le code.
- **`SuggestionContext` est immuable** (frozen dataclass) — toute modification produit un nouvel objet. Garde la traçabilité des inputs propre.
- **Tests ≥ 80 %** : `make coverage`.
- **Pre-commit** : `make precommit`.
- **Aucun secret** dans `config/*.yaml`. Vault uniquement.

### Qualité

```bash
make lint typecheck security complexity
make test test-unit test-e2e
make coverage
make quality
make precommit
```

## 5. Commandes utiles

### Lancement local manuel

```bash
uv sync --group dev
# API + MCP simultanés
uv run python main_api.py
uv run python main_mcp_http.py
# CLI rapide
uv run python main_cli.py "<prompt>"
```

(Préférer `./start_services.sh up meal-planner-agent` depuis la racine.)

### Inspecter les tools MCP exposés

Voir `../recipe/SKILLS.md` SK-R07 pour la commande générique (transposable à ce repo en remplaçant le chemin de `register_tools`).

### Consulter les runs

```bash
# Via REST
curl -fsS http://127.0.0.1:8016/agent-runs | jq '.[0:5]'
curl -fsS http://127.0.0.1:8016/agent-runs/<uuid> | jq

# Directement Mongo
mongosh "mongodb://127.0.0.1:5971/meal-planner-agent" --eval \
  'db["agent_runs"].find({ status: "failed" }).sort({ created_at: -1 }).limit(5)'
```

## 6. Fichiers à lire en premier

1. `main.py` + `main_api.py` + `main_mcp_http.py` — entry points.
2. `domain/models/planner_agent.py` — `CandidateRecipe`, `SuggestionContext`, `SuggestionResult`.
3. `domain/models/agent_run.py` — entité de traçabilité.
4. `application/services/` — orchestration.
5. `adapters/input/fastapi/routers/planner_agent_router.py` — entrée REST principale.
6. `adapters/input/fastmcp/tools/planner_agent_tools.py` — entrée MCP principale.
7. `adapters/input/fastmcp/register.py` — câblage MCP.
8. `infrastructure/container.py` — DI globale.
9. `config/` — configuration LLM et clients MCP.

Pour ajouter une fonctionnalité, lire en plus :

- `docs/agent.md` — fonctionnement détaillé de l'agent.
- `docs/new-entity.md` — guide d'ajout d'entité (similaire aux backends, mais ici la plupart des nouvelles capacités sont des **tools MCP** ou des **nœuds**, pas des entités).
- `docs/http-conventions.md` — conventions partagées.
- `docs/vault.md` — secrets.

## 7. Règle du journal — rappel

Toute modification non triviale doit être consignée dans `journal/YYYY-MM-DD-slug.md` à la **racine du workspace**. Voir `../AGENTS.md` §6 et `../journal/README.md`.

Cas spécifiques à ce repo qui exigent une entrée journal :

- changement de modèle LLM par défaut ou de provider ;
- évolution de la stratégie de scoring ou de filtrage des candidates ;
- ajout / retrait d'un tool MCP appelé par l'agent ;
- changement du contrat avec `meal-planner/` ou `recipe/` (côté MCP consommé) ;
- changement de port (REST, MCP).

## 8. Hors scope

- La **persistance des plans de repas** : ce repo ne persiste rien d'autre que `AgentRun`. Tout le reste passe par `meal-planner/` via MCP.
- Le **catalogue de recettes** : il vit dans `recipe/`. Cet agent le consomme via MCP, jamais via accès direct à la base.
- Le **frontend** : `gwel/`.
