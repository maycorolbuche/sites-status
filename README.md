# Status dos Sites

Painel estático de disponibilidade e integridade, com checagens a cada 15 minutos
pelo GitHub Actions. A branch `main` guarda o código e a configuração. A
`dist` é atualizada como um snapshot e o mesmo workflow publica o painel no
GitHub Pages.

## Configurar o GitHub

1. Em **Settings → Pages → Build and deployment → Source**, selecione
   **GitHub Actions**.
2. Em **Settings → Actions → General → Workflow permissions**, habilite
   **Allow GitHub Actions to create and approve pull requests**. O workflow
   abre as propostas de hash. O merge é feito pelo responsável pelo site.
3. Em **Settings → Secrets and variables → Actions**, crie os secrets
   `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`. O bot precisa poder enviar mensagens ao grupo.
4. Em **Actions → Monitorar sites e publicar painel**, execute **Run workflow**
   na `main` ou aguarde a próxima rodada. A `dist` é criada automaticamente
   e precisa permitir atualizações do workflow, inclusive substituição de seu snapshot.

## Cadastrar e aprovar sites

Edite `sites.json` na `main`. Cada entrada tem `id` estável, `name`, `url`
e `hash`. Comece com `"hash": null`. A primeira checagem bem-sucedida abre
um PR por site e envia o link ao Telegram. Revise o site antes de mesclar o
PR. O PR mantém a hash capturada originalmente enquanto estiver aberto.

Em alterações posteriores, o Telegram informa a nova hash e, quando há
referência registrada, as seções que mudaram. Para aprovar, substitua o valor
de `hash` no arquivo. O painel fica verde quando a checagem encontra a hash
atual ou uma hash substituída há menos de 90 dias. A hash atual permanece válida
enquanto estiver configurada.

O monitor verifica título, texto, cabeçalhos e destinos de links e recursos
do HTML retornado pelo servidor. Por padrão, lê `main` ou, se ausente, `body`.
Use `"selector": "#conteudo"` para delimitar a área e `"ignore": [".contador"]`
para excluir regiões que mudam legitimamente. Cada seletor aceita uma tag,
um ID ou uma classe. O monitor não executa JavaScript nem verifica arquivos
que a página não entrega. Mudanças nas regras de captura podem exigir uma nova
aprovação. Cadastre páginas públicas, pois pequenos trechos normalizados
são guardados na branch `dist` para compor as diferenças do Telegram.

O painel calcula disponibilidade a partir das checagens feitas nos últimos
90 dias. Uma alteração com resposta HTTP bem-sucedida conta como site
disponível. Dias sem medições ficam cinza. O cron roda aos minutos 02, 17, 32
e 47 e o painel sinaliza dados desatualizados após 35 minutos.

## Rodar localmente

Com Python 3.11 ou superior, execute `python3 monitor/run.py` para checar os
sites e gerar `.build/public` sem gravar branches, abrir PRs ou enviar mensagens.
Use `python3 -m http.server --directory .build/public` para abrir o painel em
`http://localhost:8000`.
