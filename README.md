# Gerenciador de E-mails

Aplicativo Android acadêmico, desenvolvido em Python + Kivy, que organiza e permite pesquisar a caixa de entrada do Gmail.

## O que o aplicativo faz

- Conecta à sua conta Google pelo Google Play Services, com acesso **somente leitura**.
- Sincroniza as mensagens da caixa de entrada.
- Classifica cada e-mail automaticamente em: Acadêmico, Trabalho, Financeiro, Compras, Marketing e Outros.
- Permite pesquisar por remetente, assunto ou conteúdo e ler as mensagens.
- Sincroniza as mensagens da caixa de entrada pelo botão de sincronizar (a primeira vez baixa as 50 mais recentes).
- Guarda tudo no aparelho (SQLite), sem servidor próprio.
- Permite pesquisar por remetente, assunto ou conteúdo, ver as categorias e ler as mensagens.

## Instalar o APK

O aplicativo já vem compilado na pasta (`bin/`).

1. Baixe o arquivo [aqui](https://github.com/ThewsDev/trabalho-integrador/raw/main/bin/emailmanager-1.0.0.apk).
2. No celular Android, toque no arquivo baixado para abri-lo.
3. Se o Android pedir, permita a instalação de apps de fontes desconhecidas.
4. Toque em **Instalar**.

> O aparelho precisa ter Google Play Services.

### Primeiro acesso
 
1. Abra o app, vá em **Configurações** (ícone da engrenagem) e toque em **Conectar conta Google**.
2. Se aparecer "O Google não verificou este app", toque em **Avançado → Acessar Gerenciador de E-mails**.
3. Após a autorização, o app baixa automaticamente as 50 mensagens mais recentes da caixa de entrada.

> O app pede apenas permissão de **somente leitura**: ele não envia, apaga nem altera e-mails na sua conta Gmail.

### Navegação (barra inferior)
 
| Ícone | Tela | O que faz |
|-------|------|-----------|
| 🏠 | **Início** | Mostra o total de mensagens, a quantidade de categorias e as 5 mensagens mais recentes |
| 📁 | **Categorias** | Lista as categorias (Acadêmico, Trabalho, Financeiro, Compras, Marketing e Outros) com a contagem de e-mails de cada uma |
| 🔍 | **Pesquisar** | Busca por remetente, assunto ou conteúdo, com resultados na hora |
| ⚙️ | **Configurações** | Conexão da conta, banco de dados local e informações do app |

### Funções dos botões
 
| Botão | Onde fica | O que faz |
|-------|-----------|-----------|
| 🔄 **Atualizar** | Canto superior direito (Início, Caixa de entrada, Categorias e Configurações) | Sincroniza com o Gmail e traz as mensagens novas. Também remove as apagadas e atualiza o status de lido/não lido |
| **Ver todos** | Início, ao lado de "Mensagens recentes" | Abre a Caixa de entrada completa |
| **Abrir** | Em cada cartão de Categorias | Abre a Caixa de entrada filtrada só por aquela categoria |
| **← Voltar** | Tela de leitura da mensagem | Volta para a lista de onde você veio, mantendo o filtro de categoria |
| **Conectar conta Google** | Configurações (quando desconectado) | Abre o seletor de contas do Google para autorizar o acesso de leitura |
| **Desconectar conta** | Configurações (quando conectado) | Remove a conta do app e apaga os e-mails salvos no aparelho (pede confirmação) |
| **Apagar e-mails armazenados** | Configurações | Apaga apenas a cópia local dos e-mails. Os e-mails no Gmail não são afetados (pede confirmação) |
 
> Ao tocar em qualquer mensagem, ela abre na tela de leitura (somente visualização) e é marcada como lida no app.

## Privacidade

- Os e-mails ficam armazenados **apenas no aparelho** do usuário.
- O projeto não possui servidor próprio e não envia dados a terceiros.
- O aplicativo não envia, apaga nem altera e-mails na conta Gmail.
- O acesso pode ser removido a qualquer momento em [myaccount.google.com/permissions](https://myaccount.google.com/permissions).

Detalhes completos na **[Política de Privacidade](https://thewsdev.github.io/trabalho-integrador/privacy)**.

## Limitações

- Funciona somente em Android.
- Somente leitura: não responde, arquiva nem apaga e-mails.
- Sincronização manual, sem atualização em segundo plano.
- Anexos não são baixados.
- Não é garantido que conecte a contas institucionais
