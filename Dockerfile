# Use a imagem base oficial do Python
FROM python:3.9-slim

# Variáveis de ambiente para a versão do Chrome
ENV CHROME_VERSION="126.0.6478.126"

# Instala as dependências do sistema, o Google Chrome e o ChromeDriver
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    # Dependências necessárias para o Chrome rodar
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    libdbus-1-3 \
    libxtst6 \
    libxss1 \
    libxrandr2 \
    xdg-utils \
    --no-install-recommends \
    # Baixa e instala o Google Chrome
    && wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && dpkg -i google-chrome-stable_current_amd64.deb \
    && apt-get -f install -y \
    # Baixa e instala o ChromeDriver
    && wget -q https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chromedriver-linux64.zip \
    && unzip chromedriver-linux64.zip \
    && mv chromedriver-linux64/chromedriver /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    # Limpa os arquivos baixados e o cache para reduzir o tamanho da imagem
    && rm google-chrome-stable_current_amd64.deb chromedriver-linux64.zip \
    && rm -rf /var/lib/apt/lists/*

# Defina o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copie o arquivo de requisitos para o diretório de trabalho
COPY requirements.txt .

# Instale as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copie o conteúdo da aplicação para o diretório de trabalho
COPY . .

# Exponha a porta em que a aplicação irá rodar
EXPOSE 80

# Comando para iniciar a aplicação
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80", "--workers=4", "--log-level", "debug"]
