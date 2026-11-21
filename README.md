# Gerenciador de E-mails

Aplicativo Android (Python + Kivy) que organiza a caixa de entrada do Gmail.

## O que o aplicativo faz

- Conecta à sua conta Google pelo Google Play Services, com acesso **somente leitura** (`gmail.readonly`).
- Sincroniza as mensagens da caixa de entrada pelo botão de sincronizar (a primeira vez baixa as 50 mais recentes).
- Classifica cada e-mail automaticamente em: Acadêmico, Trabalho, Financeiro, Compras, Marketing e Outros.
- Guarda tudo no aparelho (SQLite), sem servidor próprio.
- Permite pesquisar por remetente, assunto ou conteúdo, ver as categorias e ler as mensagens.

## Instalar o APK

O aplicativo já vem compilado (`bin/emailmanager-1.0.0.apk`), então não é preciso compilar nada.

1. Envie o `emailmanager-1.0.0.apk` para o Google Drive (pelo computador ou pelo celular).
2. No celular Android, abra o Drive e baixe o arquivo.
3. Abra o arquivo baixado e, se o Android pedir, permita a instalação de apps de fontes desconhecidas para o Drive ou para o navegador.
4. Toque em **Instalar**.

O aparelho precisa ter Google Play Services.

## Configurar o Google Cloud

Para usar com a sua conta, crie o seu próprio projeto no [Google Cloud Console](https://console.cloud.google.com/). Assim você não precisa pedir para ser adicionado a ninguém. Se algum menu estiver com nome diferente, procure o equivalente.

Primeiro, crie um projeto (seletor de projetos no topo → **Novo projeto**) e selecione-o.

### 1. Ativar a Gmail API

**APIs e serviços → Biblioteca →** pesquise **Gmail API → Ativar**.

### 2. Configurar a tela de consentimento

**APIs e serviços → Tela de permissão OAuth** (ou **Google Auth Platform**) → **Começar**:

- Nome do app: `Gerenciador de E-mails`
- E-mail de suporte e de contato: o seu
- Público-alvo: **Externo**

### 3. Adicionar o escopo

**Acesso a dados** (ou **Escopos**) → **Adicionar ou remover escopos** → marque `https://www.googleapis.com/auth/gmail.readonly` → **Atualizar** → **Salvar**.

### 4. Cadastrar usuário de teste

**Público-alvo** → **Usuários de teste** → **Add users** → informe o Gmail que será usado no aparelho → **Salvar**.

### 5. SHA-1 do APK

O SHA-1 do APK fornecido é (é só copiar, não precisa gerar nada):

```
A5:F7:0F:7B:9F:DB:75:FC:AA:28:6F:7C:91:61:97:D3:89:8B:C3:7E
```

Esse valor só vale para o APK que foi enviado junto. Se você usar outro APK, o Google dará erro de desenvolvedor (código 10).

### 6. Criar o cliente OAuth

**APIs e serviços → Credenciais → Criar credenciais → ID do cliente OAuth**:

- Tipo de aplicativo: **Android**
- Nome do pacote: `org.emailmanager.emailmanager`
- Impressão digital SHA-1: o valor do passo anterior (`A5:F7:0F:7B...`)


## Usar

1. Abra o app, vá em **Configurações** e toque em **Conectar conta Google**.
2. Escolha a conta que você cadastrou como usuário de teste.
3. Se aparecer "O Google não verificou este app", toque em **Continuar → Acessar Email Manager** (esperado em projetos em teste).

Se aparecer erro de desenvolvedor ou código 10, o SHA-1 cadastrado não bate com o APK instalado. Se aparecer "acesso bloqueado", a conta não está nos usuários de teste.

## Limitações

- Funciona somente em Android.
- Somente leitura: não responde, arquiva nem apaga e-mails.
- Sincronização manual, sem atualização em segundo plano.
- Anexos não são baixados.
- `gmail.readonly` é um escopo restrito do Google: o modo de teste serve para uso pessoal e avaliação, mas publicar para o público exige a verificação OAuth do Google.
