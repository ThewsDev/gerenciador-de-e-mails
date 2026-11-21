# Gerenciador de E-mails

Aplicativo Android acadêmico, desenvolvido em Python + Kivy, que organiza e permite pesquisar a caixa de entrada do Gmail.

## O que o aplicativo faz

- Conecta à sua conta Google pelo Google Play Services, com acesso **somente leitura**.
- Sincroniza as mensagens da caixa de entrada.
- Classifica cada e-mail em: Acadêmico, Trabalho, Financeiro, Compras, Marketing e Outros.
- Permite pesquisar por remetente, assunto ou conteúdo e ler as mensagens.

## Instalar o APK

O aplicativo já vem compilado (`bin/emailmanager-1.0.0.apk`).

1. Envie o `emailmanager-1.0.0.apk` para o Google Drive.
2. No celular Android, abra o Drive e baixe o arquivo.
3. Abra o arquivo baixado e, se o Android pedir, permita a instalação de apps de fontes desconhecidas para o Drive ou para o navegador.
4. Toque em **Instalar**.

O aparelho precisa ter Google Play Services.

## Usar

1. Abra o app, vá no ícone de **Configurações** e toque em **Conectar conta Google**.
2. Escolha a conta que você cadastrou como usuário de teste.
3. Se aparecer "O Google não verificou este app", toque em **Continuar → Acessar Gerenciador de E-mails**.

## Privacidade

- Os e-mails ficam armazenados **apenas no aparelho** do usuário.
- O projeto não possui servidor próprio e não envia dados a terceiros.
- O aplicativo não envia, apaga nem altera e-mails na conta Gmail.
- O acesso pode ser removido a qualquer momento em [myaccount.google.com/permissions](https://myaccount.google.com/permissions).

Detalhes completos na [Política de Privacidade](https://thewsdev.github.io/trabalho-integrador/privacy).

## Limitações

- Funciona somente em Android.
- Somente leitura: não responde, arquiva nem apaga e-mails.
- Sincronização manual, sem atualização em segundo plano.
- Anexos não são baixados.
- Não é garantido que conecte a contas institucionais
