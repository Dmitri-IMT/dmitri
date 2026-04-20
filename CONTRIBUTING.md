# Contributing

## Git Workflow

- **Branch naming**:
  - `feature/nome-da-feature` (ex: `feature/auth-jwt`)
  - `fix/nome-do-bug` (ex: `fix/cors-supabase`)
  - `docs/nome-da-doc` (ex: `docs/dev-setup`)
  - `chore/nome-do-chore` (ex: `chore/A-06`)

- **Pull Requests**:
  - 1- Crie um PR do seu branch para `main`
  - 2- Preencha o template de PR (se existir)
  - 3- Aguarde aprovação de pelo menos 1 reviewer
  - 4- O CI deve passar antes do merge

## Commit Messages (Conventional Commits)

### Commit Message Header

```text
<type>(<scope>): <short summary>
  │       │             │
  │       │             └─⫸ Summary in present tense. Not capitalized. No period at the end.
  │       │
  │       └─⫸ Commit Scope (optional): backend|frontend|infra|docs|...|hardware-agent
  │
  └─⫸ Commit Type: build|ci|docs|feat|fix|perf|refactor|test
```
**Commit Type:**
- `build`: Changes that affect the build system or external dependencies (example scopes: gulp, broccoli, npm)
- `ci`: Changes to our CI configuration files and scripts (examples: Github Actions, Docker)
- `docs`: Documentation only changes
- `feat`: A new feature
- `fix`: A bug fix
- `perf`: A code change that improves performance
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `test`: Adding missing tests or correcting existing tests

### Commit Message Body
Just as in the summary, use the imperative, present tense: "fix" not "fixed" nor "fixes".

Explain the motivation for the change in the commit message body. This commit message should explain why you are making the change. You can include a comparison of the previous behavior with the new behavior in order to illustrate the impact of the change.

**Exemplo completo:**
```
feat(backend): implementar persistência com SQLModel + Supabase

Substitui o banco local por PostgreSQL via Supabase
Adiciona SQLModel 0.0.21 como ORM único (tabela + schema)
Configura asyncpg + Alembic para migrações
Mantém idempotência no endpoint POST /scans

Closes #42
```

## Como pegar uma issue

1. Vá para o Project Board
2. Atribua a issue para você (`Assign to me`)
3. Mova o card para **In Progress**
4. Crie o branch seguindo o padrão acima
