# youtube-downloader

Este arquivo README fornece instruções detalhadas sobre como utilizar a biblioteca `pyinstaller` para gerar um executável do projeto `youtube-downloader`. Este projeto permite que você baixe vídeos do YouTube, conteúdo do Instagram e muito mais, utilizando as bibliotecas `pytube`, `pywebio` e `instaloader`.

## Pré-requisitos

Antes de começar, certifique-se de que você tem Python 3.10 ou superior instalado em seu sistema. Além disso, você precisará ter o `poetry` instalado para gerenciar as dependências do projeto. Você pode instalar o `poetry` seguindo as instruções disponíveis em [Poetry: Dependency Management for Python](https://python-poetry.org/docs/).

## Instalação

Para instalar as dependências do projeto, incluindo `pyinstaller`, navegue até o diretório do projeto e execute o seguinte comando:

```bash
poetry install
```

Este comando instala todas as dependências listadas no arquivo `pyproject.toml`, preparando o ambiente para a geração do executável.

## Gerando o Executável com PyInstaller

Após instalar todas as dependências, você pode gerar o executável do seu projeto utilizando o `pyinstaller`. O `pyinstaller` analisa seu código Python e cria um executável que pode ser distribuído e executado sem a necessidade de instalar o Python ou as dependências do projeto.

### Passo a Passo

1. **Ative o ambiente virtual criado pelo poetry**:

    ```bash
    poetry shell
    ```

2. **Gere o executável do projeto**:

    Utilize o comando `pyinstaller` seguido do nome do script Python que serve como ponto de entrada do seu projeto. Por exemplo, se o ponto de entrada for `main.py` dentro do pacote `youtube_downloader`, o comando seria:

    ```bash
    pyinstaller --onefile --noconsole video_downloader.py
    ```

    A opção `--onefile` instrui o `pyinstaller` a criar um único arquivo executável. Se o seu projeto depende de arquivos estáticos ou outros recursos, você pode precisar adicionar opções adicionais para incluí-los no executável.

3. **Localize o executável gerado**:

    Após a conclusão do processo, o `pyinstaller` cria uma pasta `dist` no diretório do projeto. Dentro desta pasta, você encontrará o executável do seu projeto.

## Executando o Executável

Para executar o programa, simplesmente navegue até a pasta `dist` e execute o arquivo gerado. No Windows, você pode dar um duplo clique no arquivo. No Linux e no macOS, você pode precisar tornar o arquivo executável com o comando `chmod +x nome_do_executável` e então executá-lo a partir do terminal com `./nome_do_executável`.

## Conclusão

Você agora tem um executável do seu projeto `youtube-downloader` que pode ser facilmente distribuído e executado em sistemas que não possuem o Python instalado. Isso facilita o compartilhamento do seu projeto com usuários finais, permitindo-lhes utilizar suas funcionalidades sem se preocupar com a instalação de dependências.

Para mais informações sobre como utilizar o `pyinstaller`, consulte a [documentação oficial do PyInstaller](https://www.pyinstaller.org/documentation.html).

---

